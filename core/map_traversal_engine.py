import json
import math
import os
import threading
import time
import hashlib
import uuid
from collections import deque

from core.coverage_planner import CoveragePlan, MapSurveyor, atomic_json
from core.runtime_store import RuntimeStore


class MapTraversalEngine:
    """Observe a map, plan a sweep, then verify each leg with player coordinates."""

    PHASES = frozenset({
        "idle", "connecting", "surveying", "planned", "pinning", "walking", "verifying",
        "transition", "transition_return", "completed", "partial", "error",
        "stopping", "stopped", "paused", "stop_unverified"
    })
    MOVING = {"run", "walk", "move", "moving"}
    STOPPED = {"stand", "idle", "rest", "stay"}

    def __init__(self, controller, vision, glitch_detector, bypasser, sheet_sync):
        self.ctrl = controller
        self.vision = vision
        self.vision.adb_path = controller.adb_path
        self.vision.device_id = controller.device_id
        self.vision.controller = controller
        self.glitch_detector = glitch_detector
        self.bypasser = bypasser
        self.sheet_sync = sheet_sync
        self.is_running = False
        self.is_paused = False
        self.waiting_for_user_review = False
        self.current_incident = None
        self.worker_thread = None
        self.cb_status = None
        self.cb_glitch_alert = None
        self.cb_progress = None
        self.cb_route_progress = None
        self.route_phase = "idle"
        self.plan = None
        self.current_target = None
        self.current_map_idx = 0
        self.current_map_id = None
        self.current_map_name = "Chưa đọc map"
        self.visited_maps = set()
        self.pending_map_return = None
        self._last_source_position = None
        self._stop_cancel_sent = False
        self._stop_cancel_thread = None
        self._movement_may_be_active = False
        self._stop_event = threading.Event()
        self._last_publish = 0.0
        self._last_save = 0.0
        self._last_survey_render = 0.0
        self._survey_preview_rgb = None
        self._survey_observed_fraction = 0.0
        self._pause_ack = False
        self._needs_repin = False
        self._death_samples = 0
        self._stopped_proof = None
        self._player_identity = None
        self._mission_id = uuid.uuid4().hex
        self._leg = None
        self._map_results = {}
        self._revisits = []
        self._revisit_keys = set()
        self._verified_breadcrumbs = deque(maxlen=60)
        self._blocked_sectors = []
        self._state_lock = threading.RLock()
        self.store = sheet_sync.store if sheet_sync and hasattr(sheet_sync, "store") else RuntimeStore()
        root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.progress_path = os.path.join(root, "reports", "traversal_progress.json")
        self.route_directory = os.path.join(root, "reports", "routes")
        self.settings = controller.config.get("traversal", {})
        with open(os.path.join(root, "config", "phong_than_maps.json"), encoding="utf-8") as stream:
            self.catalog = json.load(stream)["maps"]

        # Existing UI calibration remains available as an explicit legacy option.
        link_rows = [
            ("Phong Thần đài", 0, 0), ("Diêu Trì", 0, 1), ("Tây Kỳ", 0, 2),
            ("Triều Ca", 0, 3), ("Sùng Thành doanh", 0, 4), ("Ngọc Hư cung", 0, 5),
            ("Xi Vưu Mộ", 0, 6), ("Sùng thành", 0, 7), ("Bắc Hải", 0, 8),
            ("Yến Sơn", 0, 9), ("Chân núi Côn Lôn", 0, 10),
            ("Tây Côn Lôn", 1, 3), ("Thủ Dương sơn", 1, 4), ("Du Hồn", 1, 5),
            ("Miêu Cương", 1, 6), ("Cự Lộc", 1, 7), ("Đồng Quan", 1, 8),
            ("Bồng Lai", 1, 9), ("Đông Doanh", 1, 10), ("Phương Trượng", 2, 4),
            ("Thanh Đồng sơn", 2, 5), ("Viễn Cổ", 2, 6), ("Khổn Tiên tầng 1", 2, 7),
            ("Khổn Tiên tầng 2", 2, 8), ("Khổn Tiên tầng 3", 2, 9),
            ("Khổn Tiên tầng 4", 2, 10), ("Khổn Tiên tầng 5", 2, 11),
            ("Đấu Trường", 2, 12)
        ]
        aliases = {"sùng thành": "ngoại sùng thành", "du hồn": "du hồn quan",
                   "đông doanh": "đông doanh đảo"}
        by_name = {item["name"].casefold(): item["id"] for item in self.catalog}
        self.ordered_maps = [
            {"id": by_name.get(aliases.get(name.casefold(), name.casefold())),
             "name": name, "page": page, "row_idx": row}
            for name, page, row in link_rows
        ]
        legacy = {item["id"]: item for item in self.ordered_maps if item["id"] is not None}
        self.ordered_maps = [{**item, "legacy_link": legacy.get(item["id"])} for item in self.catalog]
        if self.glitch_detector:
            self.glitch_detector.on_observation = self._record_observation
            self.glitch_detector.on_ready = self._incident_ready
        self.surveyor = MapSurveyor(
            controller, vision, self.settings, self._wait_active, self._notify_status,
            self._on_survey_progress
        )
        if bypasser is not None:
            self.bypasser = bypasser
            if hasattr(self.bypasser, "joystick_only"):
                self.bypasser.joystick_only = bool(self.settings.get("joystick_only", False))
        else:
            from core.obstacle_bypasser import ObstacleBypasser
            self.bypasser = ObstacleBypasser(controller, joystick_only=bool(self.settings.get("joystick_only", False)))

    def start(self):
        if self.worker_thread and self.worker_thread.is_alive():
            return False
        self.is_running = True
        self.is_paused = False
        self.waiting_for_user_review = False
        self._pause_ack = False
        self._needs_repin = False
        self._mission_id = uuid.uuid4().hex
        self.plan = None
        self.current_target = None
        self._leg = None
        self._bound = False
        self._death_samples = 0
        self._stopped_proof = None
        self._movement_may_be_active = False
        self._stop_event.clear()
        self._stop_cancel_sent = False
        self._phase("connecting")
        self._notify_status("Bắt đầu khảo sát theo vòng mở rộng từ mốc gốc.")
        if hasattr(self.vision, "start_background_telemetry"):
            self.vision.start_background_telemetry(poll_interval=0.06)
        self.worker_thread = threading.Thread(target=self._run_loop, daemon=True)
        self.worker_thread.start()
        return True

    def pause(self):
        if not self.is_running:
            return False
        self.is_paused = True
        self._pause_ack = False
        self._notify_status("Đang hủy di chuyển và kiểm tra đứng yên để tạm dừng.")

    def resume(self):
        if self.is_running and self.is_paused and not self._pause_ack:
            self._notify_status("Đang xác minh dừng; chưa phát lại lệnh di chuyển.")
            return False
        self.is_paused = False
        self._pause_ack = False
        self._notify_status("Tiếp tục chặng đang khảo sát.")
        return True

    def stop(self):
        was_running = self.is_running
        self.is_running = False
        self.waiting_for_user_review = False
        self._stop_event.set()
        if hasattr(self.vision, "stop_background_telemetry"):
            self.vision.stop_background_telemetry()
        if was_running:
            self._phase("stopping")
        self._notify_status("Đang dừng và lưu tiến độ hành trình.")
        if (getattr(self, "_bound", False) and self._movement_may_be_active
                and not self._stop_cancel_sent):
            self._stop_cancel_sent = True
            self._stop_cancel_thread = threading.Thread(
                target=self._send_stop_cancel, name="traversal-stop-cancel", daemon=True
            )
            self._stop_cancel_thread.start()

    def _send_stop_cancel(self):
        """Interrupt an active joystick/auto-path command as soon as Stop is pressed."""
        try:
            if hasattr(self.ctrl, "cancel_movement"):
                self.ctrl.cancel_movement()
            elif hasattr(self.ctrl, "swipe") and hasattr(self.ctrl, "joystick_center"):
                cx, cy = self.ctrl.joystick_center
                self.ctrl.swipe(cx, cy, cx+35, cy, duration_ms=150)
        except Exception as exc:
            self._notify_status(f"Lệnh hủy di chuyển tức thời gặp lỗi: {exc}")

    def _wait_active(self):
        if self.is_running and self.glitch_detector and self.glitch_detector.last_error:
            raise RuntimeError("Không lưu được bằng chứng: "+self.glitch_detector.last_error)
        while self.is_running and (self.is_paused or self.waiting_for_user_review):
            if not getattr(self, "_bound", False):
                self._stop_event.wait(0.2)
                continue
            if not self._pause_ack:
                self._cancel_and_verify()
                self._pause_ack = True
                self._needs_repin = True
                if self.plan and self.current_target and not self.current_target.get("review_job"):
                    self.plan.data["resume_target_id"] = self.current_target["id"]
                self._phase("paused")
                self._save_progress()
                self._notify_status("Đã xác minh nhân vật dừng; giữ nguyên chặng để tiếp tục.")
            self._stop_event.wait(0.2)
        return self.is_running

    def _cancel_and_verify(self):
        sample = self.vision.get_engine_telemetry()
        if sample.get("map_dialog_open") and sample.get("doing") not in self.STOPPED:
            self.ctrl.close_map_dialog(_cancel=True)
        if not (sample.get("map_dialog_open") and sample.get("doing_valid") and sample.get("doing") in self.STOPPED):
            if hasattr(self.ctrl, "cancel_movement"):
                self.ctrl.cancel_movement()
            elif hasattr(self.ctrl, "swipe") and hasattr(self.ctrl, "joystick_center"):
                cx, cy = self.ctrl.joystick_center
                self.ctrl.swipe(cx, cy, cx + 35, cy, duration_ms=150)
            elif hasattr(self.ctrl, "joystick_center"):
                self.ctrl.tap(*self.ctrl.joystick_center, jitter=False, delay=0)
        deadline = time.monotonic()+float(self.settings.get("stop_timeout", 12))
        previous_frame = None
        previous_position = None
        count = 0
        last_cancel = time.monotonic()
        while time.monotonic() < deadline:
            sample = self.vision.get_engine_telemetry()
            pos_age = sample.get("position_age")
            if pos_age is not None:
                fresh_stop = (sample.get("doing_valid") and sample.get("doing") in self.STOPPED and pos_age < 12.0)
                is_fresh = (sample["position_frame"] != previous_frame or fresh_stop)
            else:
                fresh_stop = sample.get("doing_valid") and sample.get("doing") in self.STOPPED
                is_fresh = (sample["position_frame"] != previous_frame)
            if self._valid_position(sample) and is_fresh:
                previous_frame = sample["position_frame"]
                stationary = (fresh_stop and previous_position is not None
                              and math.dist(previous_position, sample["position"]) <= 0.08)
                count = count+1 if stationary else 0
                previous_position = sample["position"]
                if count >= 2:
                    self._remember_stopped(sample)
                    self._movement_may_be_active = False
                    return sample
                if sample.get("doing") in {"run", "walk"} and time.monotonic() - last_cancel > 2.5:
                    if hasattr(self.ctrl, "cancel_movement"):
                        self.ctrl.cancel_movement()
                    elif hasattr(self.ctrl, "swipe") and hasattr(self.ctrl, "joystick_center"):
                        cx, cy = self.ctrl.joystick_center
                        self.ctrl.swipe(cx, cy, cx + 35, cy, duration_ms=150)
                    last_cancel = time.monotonic()
            time.sleep(0.15)
        raise RuntimeError("Đã gửi hủy chạy nhưng chưa xác minh đứng yên; không mở map hoặc báo đã dừng.")

    def _configure_profile(self):
        # Device-specific progress prevents one LD from inheriting another LD's visits.
        serial = str(self.ctrl.device_id or "unknown")+":"+str(getattr(self.ctrl, "device_fingerprint", "unknown"))
        sample = self.vision.get_engine_telemetry()
        profile = str(self.ctrl.config.get("profile_id") or (serial+":"+str(sample.get("player_identity") or "unidentified")))
        profile += ":"+str(getattr(self.ctrl, "game_build", None) or self.ctrl.config.get("game_build") or "unknown-build")
        key = hashlib.sha256(profile.encode("utf-8")).hexdigest()[:16]
        self.profile = key
        self.route_directory = os.path.join(os.path.dirname(self.progress_path), "routes", key)
        saved = self.store.load_checkpoint(f"mission:{key}") or {}
        self.visited_maps = set()
        for value in saved.get("visited_maps", []):
            try:
                self.visited_maps.add(int(value))
            except (TypeError, ValueError):
                continue
        self._map_results = saved.get("map_results", {})
        self.pending_map_return = saved.get("pending_map_return")
        if self.pending_map_return is not None:
            self.current_map_id = self.pending_map_return
            item = next((item for item in self.catalog if item["id"] == self.current_map_id), None)
            if item:
                self.current_map_name = item["name"]
        for item in self.catalog:
            self._map_results.setdefault(str(item["id"]), {"state": "pending", "name": item["name"]})
        self._reconcile_saved_completions()
        self._player_identity = saved.get("player_identity")
        self._revisits = saved.get("revisits", [])
        self._revisit_keys = {job["bug_key"] for job in self._revisits}

    def _reconcile_saved_completions(self):
        """Recheck legacy completed maps against their persisted, verified targets."""
        reopened = []
        for raw_map_id in list(self.visited_maps):
            try:
                map_id = int(raw_map_id)
            except (TypeError, ValueError):
                self.visited_maps.discard(raw_map_id)
                continue
            plan = CoveragePlan.load(self.route_directory, map_id, self.store)
            key = str(map_id)
            item = next((entry for entry in self.catalog if entry["id"] == map_id), None)
            result = dict(self._map_results.get(key, {}))
            result["name"] = result.get("name") or (item["name"] if item else f"Map {map_id}")
            if not plan or not plan.is_route_complete():
                self.visited_maps.discard(raw_map_id)
                if plan:
                    result["done"] = sum(point["state"] == "done" for point in plan.data["targets"])
                    result["total"] = len(plan.data["targets"])
                result.update({
                    "state": "partial",
                    "reason": "Tiến độ cũ chưa xác nhận đủ tất cả mốc; map sẽ được tiếp tục thay vì bỏ qua."
                })
                reopened.append(result["name"])
            else:
                result.update(plan.coverage())
                result["done"] = len(plan.data["targets"])
                result["total"] = len(plan.data["targets"])
                result["state"] = "complete" if plan.complete() else "route_complete"
                if result["state"] == "route_complete":
                    result["reason"] = "Đã tới đủ mốc tuyến; phạm vi quan sát hình ảnh chưa được hiệu chuẩn."
                else:
                    result["reason"] = ""
            self._map_results[key] = result
        if reopened:
            self._notify_status(
                "Đã mở lại tiến độ map cũ còn mốc chưa xác nhận: " + ", ".join(reopened) + "."
            )

    def _notify_status(self, message):
        print(f"[TraversalEngine] {message}")
        if self.cb_status:
            self.cb_status(message)

    def _save_progress(self):
        if self.plan:
            self.plan.save(self.route_directory, self.store)
        payload = {"version": 3, "mission_id": self._mission_id, "current_map_id": self.current_map_id,
                   "visited_maps": sorted(self.visited_maps), "map_results": self._map_results,
                   "phase": self.route_phase, "leg": self._leg, "player_identity": self._player_identity,
                   "revisits": list(self._revisits), "pending_map_return": self.pending_map_return}
        self.store.checkpoint(f"mission:{getattr(self, 'profile', 'unbound')}", payload)
        if self.plan:
            self.store.checkpoint(f"map:{getattr(self, 'profile', 'unbound')}:{self.current_map_id}",
                                  {"name": self.current_map_name, "phase": self.route_phase,
                                   "done": sum(p["state"] == "done" for p in self.plan.data["targets"]),
                                   "total": len(self.plan.data["targets"]), **self.plan.coverage()})
        atomic_json(self.progress_path, payload)
        self._last_save = time.monotonic()
        if hasattr(self.ctrl, "metrics"):
            self.store.checkpoint(f"metrics:{self._mission_id}", self.ctrl.metrics.snapshot())

    def _on_survey_progress(self, atlas, known, observed_fraction):
        self._survey_observed_fraction = observed_fraction
        now = time.monotonic()
        if now - self._last_survey_render < 0.5 and observed_fraction < 0.999:
            return
        self._last_survey_render = now
        self._survey_preview_rgb = MapSurveyor.render_survey_preview(atlas, known)
        self._publish()

    def _complete_target(self, target):
        """Publish a verified arrival before any optional corner inspection work."""
        target["state"] = "done"
        if self.plan.data.get("resume_target_id") == target["id"]:
            self.plan.data["resume_target_id"] = None
        self.plan.data["active_id"] = None
        self.plan.data["active_path"] = []
        self._publish(force=True)
        self._save_progress()

    def get_route_snapshot(self):
        points = self.plan.data["targets"] if self.plan else []
        active = self.current_target
        batches = max((point["batch"] for point in points), default=0) + 1
        done = sum(point["state"] == "done" for point in points)
        unresolved = sum(point["state"] in {"retry", "unreachable", "deferred"} for point in points)
        surveying = self.route_phase == "surveying"
        preview = (self._survey_preview_rgb if surveying else self.plan.render() if self.plan else None)
        observed_fraction = (self._survey_observed_fraction if surveying else
                             self.plan.data["observed_fraction"] if self.plan else 0)
        return {
            "map_name": self.current_map_name, "map_id": self.current_map_id,
            "phase": self.route_phase, "running": self.is_running,
            "pending_map_return": self.pending_map_return,
            "blocked_reason": self.plan.data.get("blocked_reason", "") if self.plan else "",
            "batch_idx": active["batch"] if active else 0, "batch_count": batches,
            "done": done, "total": len(points), "unresolved": unresolved,
            "observed_fraction": observed_fraction,
            "coverage": self.plan.coverage() if self.plan else {}, "leg": dict(self._leg or {}),
            "sheet": self.sheet_sync.summary() if self.sheet_sync and hasattr(self.sheet_sync, "summary") else {},
            "map_results": dict(self._map_results),
            "preview_rgb": preview,
            "checkpoints": [
                {"name": f"Vòng {point['batch']} · {point.get('purpose', 'khảo sát')} · "
                         f"({point['options'][0][0]:.1f}, {point['options'][0][1]:.1f})",
                 "state": point["state"]}
                for point in points
            ]
        }

    def _publish(self, force=False):
        if not force and time.monotonic() - self._last_publish < 1.0:
            return
        self._last_publish = time.monotonic()
        if self.cb_route_progress:
            self.cb_route_progress(self.get_route_snapshot())
        if self.cb_progress:
            total = len(self.catalog)
            suffix = ""
            if self.plan:
                done = sum(point["state"] == "done" for point in self.plan.data["targets"])
                suffix = f" — {done}/{len(self.plan.data['targets'])} ô khảo sát"
            self.cb_progress(len(self.visited_maps), total, self.current_map_name + suffix)

    def _phase(self, phase):
        if phase not in self.PHASES:
            raise ValueError(f"Trạng thái hành trình không hợp lệ: {phase}")
        previous = self.route_phase
        self.route_phase = phase
        if phase in {"pinning", "walking", "transition", "transition_return"}:
            self._movement_may_be_active = True
        if previous != phase:
            try:
                self.store.event(self._mission_id, "phase_changed", {
                    "from": previous, "to": phase, "map_id": self.current_map_id,
                    "target_id": (self.current_target or {}).get("id")
                })
            except Exception as exc:
                print(f"[TraversalEngine] Không ghi được sự kiện trạng thái: {exc}")
        self._publish(force=True)

    @staticmethod
    def _valid_position(telemetry):
        return (telemetry.get("in_game", True)
                and telemetry.get("position") is not None
                and len(telemetry["position"]) == 2
                and all(math.isfinite(value) for value in telemetry["position"])
                and telemetry.get("position_frame") is not None
                and telemetry.get("position_age", 0) < 15
                and telemetry.get("map_id")
                and telemetry.get("position_map_id") == telemetry.get("map_id"))

    @staticmethod
    def _is_position_loop(samples, cell_size=0.75, revisit_threshold=3,
                          min_samples=8, max_net_distance=1.5):
        if len(samples) < min_samples:
            return False
        counts = {}
        for _, position in samples:
            cell = (round(position[0] / cell_size), round(position[1] / cell_size))
            counts[cell] = counts.get(cell, 0) + 1
        return (len(counts) >= 2 and max(counts.values()) >= revisit_threshold
                and math.dist(samples[0][1], samples[-1][1]) <= max_net_distance)

    def _remember_stopped(self, telemetry):
        self._movement_may_be_active = False
        sequence = getattr(self.ctrl, "input_sequence", None)
        if sequence is not None:
            self._stopped_proof = {
                "sequence": sequence, "device": (self.ctrl.adb_path, self.ctrl.device_id),
                "map_id": telemetry["map_id"], "position": list(telemetry["position"]),
                "frame": telemetry["position_frame"], "at": time.monotonic()}

    def _can_reuse_stopped(self, telemetry):
        proof = self._stopped_proof
        if not proof or not self._valid_position(telemetry):
            return False
        return (getattr(self.ctrl, "input_sequence", None) == proof["sequence"]
                and (self.ctrl.adb_path, self.ctrl.device_id) == proof["device"]
                and telemetry["map_id"] == proof["map_id"]
                and telemetry["position_frame"] >= proof["frame"]
                and telemetry.get("doing_valid") and telemetry.get("doing") in self.STOPPED
                and not telemetry.get("auto_move")
                and math.dist(telemetry["position"], proof["position"]) <= 0.08
                and time.monotonic()-proof["at"] <= 3.0)

    def _wait_stopped(self):
        """Never open a map over a leg that is still moving."""
        previous_frame = None
        stopped_samples = 0
        last_fresh = time.monotonic()
        started = last_fresh
        previous_position = None
        while self._wait_active():
            telemetry = self.vision.get_engine_telemetry()
            if (self._valid_position(telemetry)
                    and telemetry["map_id"] == self.current_map_id):
                self._last_source_position = list(telemetry["position"])
            if not telemetry.get("in_game") or not self._valid_position(telemetry):
                if hasattr(self.ctrl, "check_and_recover_session"):
                    if self.ctrl.check_and_recover_session():
                        time.sleep(2.0)
                        continue
            if self._can_reuse_stopped(telemetry):
                self._movement_may_be_active = False
                return telemetry
            if self.route_phase not in {"surveying", "verifying", "transition_return"}:
                self._phase("verifying")
            if self._valid_position(telemetry):
                pos_age = telemetry.get("position_age")
                frame_changed = (telemetry["position_frame"] != previous_frame)
                if pos_age is not None:
                    fresh_stop = (telemetry.get("doing_valid") and telemetry.get("doing") in self.STOPPED and pos_age < 12.0)
                    is_fresh = frame_changed or fresh_stop
                    if pos_age < 12.0:
                        last_fresh = time.monotonic()
                else:
                    fresh_stop = telemetry.get("doing_valid") and telemetry.get("doing") in self.STOPPED
                    is_fresh = frame_changed or previous_position is None
                    if frame_changed:
                        last_fresh = time.monotonic()

                if is_fresh:
                    previous_frame = telemetry["position_frame"]
                    if (fresh_stop and previous_position is not None
                            and math.dist(previous_position, telemetry["position"]) <= 0.08):
                        stopped_samples += 1
                        if stopped_samples >= 2:
                            self._remember_stopped(telemetry)
                            return telemetry
                    else:
                        stopped_samples = 0
                    previous_position = telemetry["position"]
            if time.monotonic() - last_fresh > 15:
                raise RuntimeError("Dữ liệu vị trí không cập nhật; giữ nguyên các vùng chưa đi.")
            if time.monotonic()-started > 90:
                self._cancel_and_verify()
                raise RuntimeError("Chưa kết thúc di chuyển ngoài tuyến; đã hủy chạy để giữ tiến độ chính xác.")
            self._stop_event.wait(0.25)
        raise InterruptedError()

    def _synchronize_map(self, telemetry):
        identity = telemetry.get("player_identity")
        if identity is not None and self._player_identity is not None and identity != self._player_identity:
            raise RuntimeError("Nhân vật đã thay đổi; cần chọn hồ sơ khảo sát riêng.")
        if identity is not None:
            self._player_identity = identity
        self.current_map_id = telemetry["map_id"]
        self._last_source_position = list(telemetry["position"]) if self._valid_position(telemetry) else None
        item = next((item for item in self.catalog if item["id"] == self.current_map_id), None)
        self.current_map_name = item["name"] if item else f"Map {self.current_map_id}"
        for index, destination in enumerate(self.ordered_maps):
            if destination["id"] == self.current_map_id:
                self.current_map_idx = index
                break

    def _record_portal_avoidance(self):
        if not self.plan or not self._last_source_position:
            return
        if (self.current_target or {}).get("id") == "exit":
            return
        destination = (self._leg or {}).get("to") or (self.current_target or {}).get("destination")
        if not destination:
            return
        reason = "unexpected map transition; temporary portal avoidance"
        self.plan.note_obstacle(
            self._last_source_position, destination,
            duration=float(self.settings.get("portal_avoidance_seconds", 21600)),
            reason=reason, radius=int(self.settings.get("portal_avoidance_radius", 2))
        )
        self._notify_status(
            f"Đã đánh dấu vùng cổng gần ({self._last_source_position[0]:.1f}, "
            f"{self._last_source_position[1]:.1f}) để tránh đi vào lại khi map còn dang dở."
        )

    def _return_to_pending_map(self):
        """Return to a persisted unfinished source map and verify its map ID before resuming."""
        source_id = self.pending_map_return
        item = next((entry for entry in self.catalog if entry["id"] == source_id), None)
        if item is None:
            self._notify_status(f"Không tìm thấy map {source_id} trong danh mục; giữ tiến độ và dừng an toàn.")
            return False
        self.current_map_id = source_id
        self.current_map_name = item["name"]
        self._phase("transition_return")
        self._notify_status(f"Đang quay lại {item['name']} để hoàn thành phần map còn thiếu.")
        try:
            returned = self._navigate_world_slot(item, item)
        except InterruptedError:
            raise
        except Exception as exc:
            self._notify_status(f"Không thể xác minh đường quay lại {item['name']}: {exc}")
            returned = False
        if returned:
            sample = self._wait_stopped()
            if self._valid_position(sample) and sample["map_id"] == source_id:
                self._synchronize_map(sample)
                self.pending_map_return = None
                self._phase("planned")
                self._save_progress()
                self._notify_status(f"Đã quay lại {self.current_map_name}; tiếp tục các ô chưa đi.")
                return True
        self._phase("partial")
        self._save_progress()
        self._notify_status(
            f"Chưa xác minh được map {item['name']}; đã dừng để không khảo sát nhầm map. "
            "Tiến độ và yêu cầu quay lại đã được lưu."
        )
        return False

    def _handle_unexpected_map_change(self, telemetry):
        source_id = self.current_map_id
        if self._valid_position(telemetry) and telemetry["map_id"] == source_id:
            return True
        if not self._valid_position(telemetry):
            self.pending_map_return = source_id
            self._phase("partial")
            self._save_progress()
            self._notify_status(
                f"Chưa xác minh được map hiện tại sau khi nhân vật bị dịch chuyển; " 
                f"đã lưu yêu cầu quay lại {self.current_map_name} và dừng an toàn."
            )
            return False
        if source_id in self.visited_maps:
            self._synchronize_map(telemetry)
            self._save_progress()
            return True

        self.pending_map_return = source_id
        source_item = next((entry for entry in self.catalog if entry["id"] == source_id), None)
        if self.plan:
            active = self.current_target
            if active and active.get("id") != "exit":
                if active.get("review_job"):
                    active["review_job"]["state"] = "pending"
                else:
                    active["state"] = "retry"
                    active["reason"] = "Bị cổng chuyển map giữa chặng; tiếp tục lại sau khi quay về."
                    maximum = max(1, int(self.settings.get("max_target_attempts", 3)))
                    if active.get("attempts", 0) >= maximum:
                        active["attempts"] = maximum-1
                self.plan.data["active_id"] = None
                self.plan.data["active_path"] = []
            self._record_portal_avoidance()
            coverage = self.plan.coverage()
        else:
            coverage = {}
        self._map_results[str(source_id)] = {
            "name": source_item["name"] if source_item else self.current_map_name,
            "state": "partial",
            "reason": "Bị chuyển sang map khác trước khi hoàn thành; cần quay lại các ô còn thiếu.",
            **coverage
        }
        self.store.event(self._mission_id, "unexpected_map_transition", {
            "source_map_id": source_id, "destination_map_id": telemetry["map_id"],
            "source_position": self._last_source_position,
            "target": (self.current_target or {}).get("id")
        })
        self._save_progress()
        self._notify_status(
            f"Phát hiện sang {telemetry.get('map_name') or ('map '+str(telemetry['map_id']))} "
            f"khi {self.current_map_name} chưa xong; đang quay lại map cũ."
        )
        return self._return_to_pending_map()

    def _recover_pending_map_return(self):
        if self.pending_map_return is None:
            return True
        sample = self._wait_stopped()
        source_id = self.pending_map_return
        if self._valid_position(sample) and sample["map_id"] == source_id:
            self._synchronize_map(sample)
            self.pending_map_return = None
            self._phase("planned")
            self._save_progress()
            self._notify_status(f"Đã xác nhận đang ở lại {self.current_map_name}; tiếp tục map chưa hoàn thành.")
            return True
        return self._return_to_pending_map()

    def _ensure_screen_clear(self):
        if self.vision.get_engine_telemetry().get("map_dialog_open"):
            self.surveyor.close_map()

    @staticmethod
    def conservative_inspection_radius(samples):
        if not isinstance(samples, (list, tuple)) or len(samples) != 4:
            raise ValueError("Cần đo bán kính ở đúng 4 vị trí khác nhau trên map.")
        values = []
        for sample in samples:
            try:
                value = float(sample)
            except (TypeError, ValueError):
                raise ValueError("Cả 4 số đo phải là số trong đơn vị tọa độ game.")
            if not math.isfinite(value) or value <= 0 or value > 100:
                raise ValueError("Mỗi số đo phải nằm trong khoảng lớn hơn 0 đến 100 đơn vị game.")
            values.append(value)
        return min(values)

    def update_inspection_calibration(self, radius, confirmed, samples=None):
        if self.is_running:
            raise RuntimeError("Dừng nhiệm vụ trước khi thay đổi hiệu chuẩn phạm vi kiểm tra.")
        validated_samples = []
        if samples is not None:
            radius = self.conservative_inspection_radius(samples)
            validated_samples = [float(value) for value in samples]
        if confirmed and not validated_samples:
            raise ValueError("Cần nhập đủ 4 số đo thực tế trước khi xác nhận hiệu chuẩn.")
        try:
            radius = float(radius)
        except (TypeError, ValueError):
            raise ValueError("Bán kính phải là số trong đơn vị tọa độ game.")
        if not math.isfinite(radius) or radius < 0 or radius > 100:
            raise ValueError("Bán kính phải nằm trong khoảng 0 đến 100 đơn vị game.")
        if confirmed and radius <= 0:
            raise ValueError("Cần nhập bán kính lớn hơn 0 trước khi xác nhận hiệu chuẩn.")
        calibrated = bool(confirmed and radius > 0)
        self.settings["inspection_radius"] = radius
        self.settings["inspection_calibrated"] = calibrated
        self.settings["inspection_radius_samples"] = validated_samples
        if self.plan:
            self.plan.data["inspection_radius"] = radius
            self.plan.data["inspection_calibrated"] = calibrated
            self.plan.data["inspection_radius_samples"] = validated_samples
            self._save_progress()
            self._publish(force=True)
        self.store.event(self._mission_id, "inspection_calibration_updated", {
            "radius": radius, "samples": validated_samples,
            "calibrated": calibrated, "map_id": self.current_map_id
        })
        return {"radius": radius, "calibrated": calibrated}

    def _prepare_plan(self):
        telemetry = self._wait_stopped()
        self._synchronize_map(telemetry)
        self.plan = CoveragePlan.load(self.route_directory, self.current_map_id, self.store)
        if self.plan:
            expected_strategy = self.settings.get("strategy", "corners_first")
            if self.plan.data.get("strategy") != expected_strategy:
                previous = self.plan
                anchor = previous.data.get("anchor") or telemetry["position"]
                self.plan = CoveragePlan.build(
                    self.current_map_id, previous.data["bounds"], previous.atlas, previous.known,
                    self.settings, anchor=anchor
                )
                done_ids = {p["id"] for p in previous.data.get("targets", []) if p["state"] == "done"}
                for p in self.plan.data["targets"]:
                    if p["id"] in done_ids:
                        p["state"] = "done"
                self.plan.data["trace"] = previous.data.get("trace", [])
                self.plan.save(self.route_directory, self.store)
            self.plan.data["inspection_radius"] = float(self.settings.get("inspection_radius", 0))
            self.plan.data["inspection_calibrated"] = bool(
                self.settings.get("inspection_calibrated", False)
                and self.settings.get("inspection_radius", 0) > 0
            )
        if self.plan and self.plan.data["observed_fraction"] >= 0.98:
            # Kiểm tra xem plan đã nạp có còn mốc nào khả dụng không:
            if not self.plan.next_target(max_attempts=int(self.settings.get("max_target_attempts", 3))):
                self._notify_status(f"Tuyến cũ của {self.current_map_name} đã đi hết mốc. Tự động lập tuyến mới (4 góc full map -> các vòng tròn) để chạy lại theo yêu cầu.")
                anchor = telemetry["position"]
                self.plan = CoveragePlan.build(
                    self.current_map_id, self.plan.data["bounds"], self.plan.atlas, self.plan.known,
                    self.settings, anchor=anchor
                )
                self.plan.save(self.route_directory, self.store)
            else:
                self._notify_status(f"Đã nhớ tuyến của {self.current_map_name}; tiếp tục các ô chưa đi.")
        else:
            self._survey_preview_rgb = None
            self._survey_observed_fraction = 0.0
            self._last_survey_render = 0.0
            self._phase("surveying")
            self._notify_status(f"Tự mở và kéo xem các vùng map {self.current_map_name} trước khi lập tuyến.")
            try:
                map_id, bounds, atlas, known = self.surveyor.survey()
            finally:
                self.surveyor.close_map()
            if map_id != self.current_map_id:
                raise RuntimeError("Map đã đổi trước khi lập xong tuyến.")
            previous = self.plan
            current = self._wait_stopped()
            if current["map_id"] != map_id:
                raise RuntimeError("Map thay đổi sau khảo sát; không lập tuyến từ tọa độ cũ.")
            anchor = previous.data.get("anchor") if previous else current["position"]
            self.plan = CoveragePlan.build(map_id, bounds, atlas, known, self.settings, anchor=anchor)
            self._survey_preview_rgb = None
            self._survey_observed_fraction = self.plan.data["observed_fraction"]
            # Preserve verified visits if a partial survey is expanded on the next run.
            if (previous and previous.data["bounds"] == bounds
                    and previous.data["cell_size"] == self.plan.data["cell_size"]):
                verified = {point["id"]: point for point in previous.data["targets"]
                            if point["state"] == "done"}
                for point in self.plan.data["targets"]:
                    if point["id"] in verified:
                        point["options"] = verified[point["id"]]["options"]
                        point["state"] = "done"
                self.plan.data["trace"] = previous.data["trace"]
        self.current_target = None
        if any(point["state"] != "done" for point in self.plan.data["targets"]):
            self.visited_maps.discard(self.current_map_id)
        self._phase("planned")
        self._save_progress()
        self._phase("planned")
        strat_name = "góc & viền trước, vòng tròn trong sau" if (self.plan and self.plan.data.get("strategy") == "corners_first") else "vòng mở rộng"
        self._notify_status(
            f"Đã lập tuyến {strat_name}: {len(self.plan.data['targets'])} mốc. "
            "Các ô chưa tới đích luôn được giữ lại để đi tiếp hoặc thử lại."
        )

    def reset_current_map(self):
        """Khởi động lại toàn bộ lộ trình của map hiện tại từ đầu (4 góc full map trước -> các vòng tròn trong sau)."""
        telemetry = self.vision.get_engine_telemetry()
        if not self._valid_position(telemetry):
            try:
                telemetry = self._wait_stopped()
            except Exception:
                telemetry = {"position": [237.0, 185.0], "map_id": self.current_map_id}
        self._synchronize_map(telemetry)
        if self.plan is None:
            self.plan = CoveragePlan.load(self.route_directory, self.current_map_id, self.store)
        if self.plan:
            previous = self.plan
            anchor = telemetry.get("position") or previous.data.get("anchor")
            self.plan = CoveragePlan.build(
                self.current_map_id, previous.data["bounds"], previous.atlas, previous.known,
                self.settings, anchor=anchor
            )
            self.visited_maps.discard(self.current_map_id)
            if str(self.current_map_id) in self._map_results:
                self._map_results[str(self.current_map_id)]["state"] = "pending"
                self._map_results[str(self.current_map_id)]["done"] = 0
            self.current_target = None
            self.plan.save(self.route_directory, self.store)
            self._save_progress()
            self._publish(force=True)
            self._notify_status(f"Đã lập lại lộ trình {self.current_map_name} từ đầu theo đúng chuẩn: 4 góc full map trước -> các vòng tròn bên trong sau ({len(self.plan.data['targets'])} mốc).")
            return True
        return False

    def _inspect_glitches(self, frame, telemetry):
        if self.glitch_detector is None:
            return
        found, incident = self.glitch_detector.inspect_frame_for_glitches(
            frame, self.current_map_name, telemetry.get("coords") or "", context=telemetry
        )

    def _async_inspect_glitches(self, telemetry):
        if self.glitch_detector is None or not self.is_running:
            return
        try:
            frame = self.ctrl.capture_frame(max_age_seconds=0.6)
            if frame is not None and self.glitch_detector.usable_frame(frame):
                self._inspect_glitches(frame, telemetry)
        except Exception:
            pass

    def _record_observation(self, incident):
        if self.sheet_sync:
            self.sheet_sync.add_observation(incident)

    def _incident_ready(self, incident):
        if self.sheet_sync:
            incident = self.sheet_sync.add_observation(incident)
        with self._state_lock:
            self.current_incident = incident
            if incident.get("status") == "suspected" and incident.get("bug_key") not in self._revisit_keys:
                self._revisit_keys.add(incident["bug_key"])
                self._revisits.append({"bug_key": incident["bug_key"], "map_id": incident["map_id"],
                                       "position": [incident["coord_x"], incident["coord_y"]],
                                       "attempts": 0, "state": "pending"})
        if self.cb_glitch_alert:
            self.cb_glitch_alert(incident)

    def _walk_target(self, target, destination):
        tolerance = float(self.settings.get("arrival_tolerance", 1.0))
        stall_seconds = float(self.settings.get("stuck_seconds", 8.0))
        previous_frame = None
        previous_position = None
        last_sample_position = None
        last_motion = last_fresh = time.monotonic()
        arrived_samples = 0
        stopped_samples = 0
        last_capture = 0.0
        loop_history = deque()
        best_goal_distance = None
        last_goal_progress = time.monotonic()
        foreign_map_id = None
        foreign_position_frame = None
        foreign_map_samples = 0
        while self.is_running:
            if self.is_paused or self.waiting_for_user_review:
                if not self._wait_active():
                    return "interrupted"
                if self._needs_repin:
                    self._needs_repin = False
                    return "repin"
                last_motion = last_fresh = time.monotonic()
                last_goal_progress = last_fresh
                best_goal_distance = None
                loop_history.clear()
                arrived_samples = stopped_samples = 0
            telemetry = self.vision.get_engine_telemetry()
            if self._valid_position(telemetry):
                if telemetry["map_id"] == self.current_map_id:
                    self._last_source_position = list(telemetry["position"])
                    foreign_map_id = None
                    foreign_position_frame = None
                    foreign_map_samples = 0
                else:
                    if telemetry["map_id"] != foreign_map_id:
                        foreign_map_id = telemetry["map_id"]
                        foreign_position_frame = None
                        foreign_map_samples = 0
                    if telemetry["position_frame"] != foreign_position_frame:
                        foreign_position_frame = telemetry["position_frame"]
                        foreign_map_samples += 1
                    confirmation_samples = max(1, int(self.settings.get("map_change_confirm_samples", 2)))
                    if foreign_map_samples >= confirmation_samples:
                        self.store.event(self._mission_id, "map_change_confirmed", {
                            "source_map_id": self.current_map_id,
                            "observed_map_id": telemetry["map_id"],
                            "samples": foreign_map_samples,
                            "target_id": target.get("id")
                        })
                        return "map_changed"
                    # A single inconsistent frame can occur during a map refresh.
                    # Do not record its position or treat it as a completed leg.
                    self._stop_event.wait(0.15)
                    continue
            is_valid = self._valid_position(telemetry)
            pos_age = telemetry.get("position_age")
            frame_changed = (telemetry.get("position_frame") != previous_frame)
            if is_valid:
                if pos_age is not None:
                    if pos_age < 12.0:
                        last_fresh = time.monotonic()
                    fresh = frame_changed or (pos_age < 12.0 and telemetry.get("doing") in self.STOPPED)
                else:
                    if frame_changed:
                        last_fresh = time.monotonic()
                    fresh = frame_changed
            else:
                fresh = False
            if fresh:
                previous_frame = telemetry["position_frame"]
                position = telemetry["position"]
                now = time.monotonic()
                goal_distance = math.dist(position, destination)
                progress_epsilon = float(self.settings.get("loop_progress_distance", 0.35))
                if best_goal_distance is None or goal_distance < best_goal_distance-progress_epsilon:
                    best_goal_distance = goal_distance
                    last_goal_progress = now
                loop_history.append((now, tuple(position)))
                loop_window = max(stall_seconds, float(self.settings.get("loop_window_seconds", 20.0)))
                while loop_history and now-loop_history[0][0] > loop_window:
                    loop_history.popleft()
                identity = telemetry.get("player_identity")
                if self._player_identity is not None and identity is not None and identity != self._player_identity:
                    raise RuntimeError("Đã đổi nhân vật trong khi di chuyển; hủy nhiệm vụ cũ.")
                if previous_position is not None and math.dist(position, previous_position) > float(self.settings.get("teleport_distance", 12)):
                    self.plan.data["trace"].append(None)
                    return "relocated"
                if self._leg and self._leg.get("from") and self._leg.get("to"):
                    origin, end = self._leg["from"], self._leg["to"]
                    dx, dy = end[0]-origin[0], end[1]-origin[1]
                    length2 = dx*dx+dy*dy
                    fraction = max(0, min(1, ((position[0]-origin[0])*dx+(position[1]-origin[1])*dy)/length2)) if length2 else 0
                    corridor_distance = math.dist(position, (origin[0]+fraction*dx, origin[1]+fraction*dy))
                    leg_distance = math.dist(origin, end)
                    allowed_corridor = max(
                        float(self.settings.get("corridor_tolerance", 10.0)), leg_distance * 2.5
                    )
                    max_dist_to_end = leg_distance + float(self.settings.get("detour_budget", 12.0))
                    deviation_timeout = float(self.settings.get("deviation_timeout_seconds", 12.0))
                    if (corridor_distance > allowed_corridor
                            and goal_distance > tolerance
                            and goal_distance > max_dist_to_end
                            and now-last_goal_progress >= deviation_timeout):
                        self.plan.data["trace"].append(None)
                        self._cancel_and_verify()
                        self._notify_status("Nhân vật lệch hành lang dự kiến; tính lại đường từ vị trí thật.")
                        return "deviated"
                if previous_position is None or math.dist(position, previous_position) > 0.08:
                    last_motion = time.monotonic()
                    previous_position = position
                self.plan.observe_position(position, tolerance, active_id=target["id"])
                self.store.event(self._mission_id, "position", {
                    "map_id": telemetry["map_id"], "frame": telemetry["position_frame"],
                    "position": list(position), "doing": telemetry.get("doing"),
                    "leg_id": (self._leg or {}).get("id")})
                stopped = (telemetry.get("doing_valid") and telemetry["doing"] in self.STOPPED
                           and last_sample_position is not None and math.dist(last_sample_position, position) <= 0.08)
                last_sample_position = position
                stopped_samples = stopped_samples + 1 if stopped else 0
                if stopped and math.dist(position, destination) <= tolerance:
                    moved = self._leg and self._leg.get("from") and math.dist(position, self._leg["from"]) > 0.3
                    if moved or target.get("attempts", 0) <= 1:
                        arrived_samples += 1
                    else:
                        arrived_samples = 0
                else:
                    arrived_samples = 0
                if arrived_samples >= 2:
                    self._remember_stopped(telemetry)
                    return "arrived"
                if (now-last_goal_progress >= stall_seconds
                        and self._is_position_loop(
                            loop_history,
                            cell_size=float(self.settings.get("loop_cell_size", 0.75)),
                            revisit_threshold=int(self.settings.get("loop_revisit_threshold", 3)),
                            min_samples=int(self.settings.get("loop_min_samples", 8)),
                            max_net_distance=float(self.settings.get("loop_net_distance", 1.5)))):
                    self.plan.note_obstacle(position, destination)
                    self.plan.data["trace"].append(None)
                    self._notify_status("Phát hiện nhân vật lặp quanh cùng khu vực mà không tiến gần đích; đang dừng để tính lại tuyến.")
                    self._cancel_and_verify()
                    return "retry"
                if stopped_samples >= 2 and time.monotonic() - last_motion >= stall_seconds:
                    self.plan.note_obstacle(position, destination)
                    return "retry"
                if not stopped and time.monotonic() - last_motion > stall_seconds * 2:
                    # Release pathfinding first; a failed release never opens the map.
                    check = self._cancel_and_verify()
                    self.plan.note_obstacle(check["position"], destination)
                    return "retry"

            if time.monotonic() - last_fresh > 15:
                raise RuntimeError("Mất dữ liệu vị trí; chưa tính chặng đang đi là hoàn tất.")
            now_cap = time.monotonic()
            capture_interval = max(1.5, float(self.settings.get("frame_capture_interval", 4.0)))
            frame = self.ctrl.capture_frame() if (fresh and now_cap - last_capture >= capture_interval) else None
            if frame is not None:
                last_capture = now_cap
                defeated = self.vision.is_defeated(frame)
                self._death_samples = self._death_samples+1 if defeated else 0
                if self._death_samples >= 2:
                    self.ctrl.click_revive_to_city()
                    self._death_samples = 0
                    self.store.event(self._mission_id, "revive_recovery_requested", {
                        "map_id": telemetry.get("map_id"),
                        "position": telemetry.get("position"),
                        "target_id": target.get("id")
                    })
                    return "relocated"
                if defeated:
                    self._stop_event.wait(0.3)
                    continue
                self._inspect_glitches(frame, telemetry)
                if not telemetry.get("map_dialog_open") and self.glitch_detector and self.glitch_detector.usable_frame(frame):
                    self.plan.observe_inspection(telemetry["position"])
            if time.monotonic() - self._last_save >= 2:
                self._save_progress()
            self._publish()
            self._stop_event.wait(0.3)
        return "interrupted"

    def _backtrack_from_obstacle(self):
        """Retrace recent verified turns once; never pin across the whole trail."""
        if not self.plan:
            return "unavailable"
        sample = self._wait_stopped()
        if sample["map_id"] != self.current_map_id:
            return "map_changed"
        current = sample["position"]
        path = self.plan.verified_return_path(current, max_waypoints=max(1, int(
            self.settings.get("recovery_max_waypoints", 4))))
        if not path:
            self._notify_status("Không có vệt liên tục đủ dài để lùi an toàn; giữ lại mốc chưa tới.")
            return "unavailable"
        deadline = time.monotonic()+float(self.settings.get("recovery_max_seconds", 12))
        target_id = (self.current_target or {}).get("id", "recovery")
        for index, point in enumerate(path):
            if not self._wait_active():
                return "interrupted"
            if time.monotonic() >= deadline:
                return "retry"
            start = self._wait_stopped()
            if start["map_id"] != self.current_map_id:
                return "map_changed"
            self._leg = {"id": uuid.uuid4().hex, "mission_id": self._mission_id,
                         "map_id": self.current_map_id, "target_id": target_id,
                         "purpose": "lùi theo vệt đã xác minh", "recovery": True,
                         "from": list(start["position"]), "to": list(point), "state": "walking"}
            self.store.event(self._mission_id, "leg_started", self._leg)
            self._phase("walking")
            self._notify_status(f"Lùi theo vệt đã đi: bước {index+1}/{len(path)} → ({point[0]:.1f}, {point[1]:.1f}).")
            outcome = self._walk_joystick_direct({"id": target_id}, point, max_steps=3,
                                                  tolerance=0.45, deadline=deadline)
            self._leg["state"] = outcome
            self.store.event(self._mission_id, "leg_result", self._leg)
            if outcome in {"interrupted", "map_changed", "relocated"}:
                return outcome
            if outcome != "arrived":
                return "retry"
        return "escaped"

    def _blocked_by_repeated_stalls(self, sample):
        radius = float(self.settings.get("stalled_area_radius", 4))
        limit = max(2, int(self.settings.get("max_stalled_area_attempts", 2)))
        area = self.plan.stalled_area(sample["position"], radius, limit)
        if area is None:
            self.plan.data.pop("blocked_reason", None)
            return False
        x, y = area["position"]
        reason = (f"Đã thất bại {area['failures']} lần quanh ({x:.1f}, {y:.1f}) mà không thêm mốc mới. "
                  "Đã lưu phần còn thiếu và dừng tại chỗ; cần một lối ra được xác minh trước khi thử tiếp vùng này.")
        self.plan.data["blocked_reason"] = reason
        self._notify_status(reason)
        self._save_progress()
        self._phase("partial")
        return True

    def _probe_corner_crevice(self, target):
        """Dùng joystick chui sâu vào khe núi, hốc cây, góc bản đồ không thể chấm trên minimap."""
        sample = self._wait_stopped()
        current_pos = sample["position"]
        bounds = self.plan.data.get("bounds", [0, 0, 1500, 1500]) if self.plan else [0, 0, 1500, 1500]
        map_center = ((bounds[0] + bounds[2] / 2) / 16, (bounds[1] + bounds[3] / 2) / 16)
        purpose = target.get("purpose", "")

        from core.ld_controller import game_to_joystick_angle
        if "tây bắc" in purpose:
            base_angle = game_to_joystick_angle(-2.0, -2.0)
        elif "đông bắc" in purpose:
            base_angle = game_to_joystick_angle(2.0, -2.0)
        elif "tây nam" in purpose:
            base_angle = game_to_joystick_angle(-2.0, 2.0)
        elif "đông nam" in purpose:
            base_angle = game_to_joystick_angle(2.0, 2.0)
        else:
            dx = current_pos[0] - map_center[0]
            dy = current_pos[1] - map_center[1]
            base_angle = game_to_joystick_angle(dx, dy)

        best_pos = current_pos
        for offset in [0, 30, -30]:
            probe_angle = (base_angle + offset) % 360
            for _ in range(3):
                if not self._wait_active():
                    return
                before = self.vision.get_engine_telemetry()
                if not self._valid_position(before) or before["map_id"] != self.current_map_id:
                    return
                p_before = before["position"]
                try:
                    self._movement_may_be_active = True
                    self.ctrl.move_joystick(probe_angle, duration_ms=1200)
                except Exception:
                    pass
                self._stop_event.wait(1.3)
                if not self.is_running:
                    return
                sample_now = self.vision.get_engine_telemetry()
                if not self._valid_position(sample_now) or sample_now["map_id"] != self.current_map_id:
                    return
                p_after = sample_now.get("position")
                if not p_after:
                    break
                d = math.dist(p_before, p_after)
                if d >= 0.2:
                    self._notify_status(f"Dùng joystick chui góc: ({p_after[0]:.2f}, {p_after[1]:.2f}) (sâu thêm +{d:.2f})")
                    self.plan.observe_position(p_after, float(self.settings.get("arrival_tolerance", 1.0)))
                    best_pos = p_after
                else:
                    break

        if math.dist(current_pos, best_pos) >= 0.3:
            if not self._wait_active():
                return
            reverse_angle = (base_angle + 180) % 360
            try:
                self._movement_may_be_active = True
                self.ctrl.move_joystick(reverse_angle, duration_ms=900)
            except Exception:
                pass
            self._stop_event.wait(1.0)
            if not self.is_running:
                return
        self._wait_stopped()

    def _walk_joystick_direct(self, target, destination, max_steps=8, tolerance=None, deadline=None):
        """Đi bộ bằng joystick trực tiếp cho khoảng cách ngắn, không mở map."""
        tol = float(self.settings.get("arrival_tolerance", 1.0) if tolerance is None else tolerance)
        from core.ld_controller import game_to_joystick_angle
        progress_threshold = 0.20
        initial_distance = None
        progress_anchor = None
        stall_count = 0
        for step in range(max_steps):
            if not self._wait_active():
                return "interrupted"
            if deadline is not None and time.monotonic() >= deadline:
                break
            sample = self.vision.get_engine_telemetry()
            if not self._valid_position(sample):
                time.sleep(0.3)
                continue
            if sample["map_id"] == self.current_map_id:
                self._last_source_position = list(sample["position"])
            if sample["map_id"] != self.current_map_id:
                return "map_changed"
            current = sample["position"]
            dx = destination[0] - current[0]
            dy = destination[1] - current[1]
            dist = math.hypot(dx, dy)
            if initial_distance is None:
                initial_distance = dist
            if progress_anchor is None:
                progress_anchor = dist
            if dist <= tol:
                if self._confirm_joystick_arrival(destination, tol, target.get("id")):
                    return "arrived"
            angle = game_to_joystick_angle(dx, dy)
            duration = min(500, max(180, int(dist * 180)))
            if not self._wait_active():
                return "interrupted"
            try:
                self._movement_may_be_active = True
                if hasattr(self.ctrl, "move_joystick"):
                    self.ctrl.move_joystick(angle, duration_ms=duration)
            except Exception as e:
                self._notify_status(f"Nhịp vuốt joystick gặp lỗi: {e}; tiếp tục kiểm tra vị trí.")
            self._stop_event.wait(duration / 1000.0 + 0.05)
            if not self.is_running:
                return "interrupted"
            sample_after = self.vision.get_engine_telemetry()
            if self._valid_position(sample_after):
                if sample_after["map_id"] == self.current_map_id:
                    self._last_source_position = list(sample_after["position"])
                if sample_after["map_id"] != self.current_map_id:
                    return "map_changed"
                new_pos = sample_after["position"]
                new_dist = math.dist(new_pos, destination)
                self.plan.observe_position(new_pos, tol, active_id=target.get("id"))
                if new_dist <= tol:
                    if self._confirm_joystick_arrival(destination, tol, target.get("id")):
                        return "arrived"
                if progress_anchor - new_dist >= progress_threshold:
                    progress_anchor = new_dist
                    continue
                # Không tự bẻ hướng khi lệch: dừng joystick và để bộ tìm đường
                # trên map tính lại từ vị trí thật.
                break
            break
        sample_final = self._wait_stopped()
        if self._valid_position(sample_final) and sample_final["map_id"] == self.current_map_id:
            self.plan.observe_position(sample_final["position"], tol, active_id=target.get("id"))
            if math.dist(sample_final["position"], destination) <= tol:
                return "arrived"
        if (initial_distance is not None and self._valid_position(sample_final)
                and math.dist(sample_final["position"], destination) <= initial_distance - progress_threshold):
            return "walked"
        return "stalled"

    def _confirm_joystick_arrival(self, destination, tolerance, active_id=None):
        """A nearby sample is not completion until fresh telemetry proves a stop."""
        sample = self._wait_stopped()
        if not self._valid_position(sample) or sample["map_id"] != self.current_map_id:
            return False
        position = sample["position"]
        self.plan.observe_position(position, tolerance, active_id=active_id)
        return math.dist(position, destination) <= tolerance

    def _perform_active_unstuck(self, curr_pos, angle_blocked):
        """
        Quy trình thoát kẹt chủ động VIP PRO MAX (Active Unstuck Escape Maneuver):
        1. Đánh dấu chướng ngại vật vào bản đồ (note_obstacle) với barrier slab và khóa góc trong _blocked_sectors.
        2. Xác định các góc rút lui ứng viên:
           - Ứng viên 1: Lùi về tọa độ vệt di chuyển đã xác minh gần nhất (Persistent Verified Breadcrumbs).
           - Ứng viên 2: Góc quay 180° lùi ngược hướng với góc đâm vào vật cản.
           - Ứng viên 3: Góc né 110° và -110°.
        3. Thực thi vuốt giữ joystick liên tục từ 1.5s - 2.2s để đưa nhân vật thoát hẳn ra khỏi vùng cây/đá:
           - Kiểm tra vị trí liên tục mỗi 0.15s: nếu đã dịch chuyển ra xa >= 1.5 đơn vị thì hoàn thành và dừng thoát kẹt ngay.
           - Nếu sau 0.55s góc này hoàn toàn bị chặn (< 0.12 đơn vị): tự động chuyển ngay sang góc né tiếp theo.
        4. Trả về vị trí an toàn mới sau khi thoát kẹt.
        """
        from core.ld_controller import game_to_joystick_angle
        self._notify_status(f"⚠️ Phát hiện mắc kẹt tại ({curr_pos[0]:.1f}, {curr_pos[1]:.1f}); Kích hoạt quy trình thoát kẹt chủ động...")

        rad_b = math.radians(angle_blocked)
        obs_probe = [curr_pos[0] + math.cos(rad_b) * 1.5, curr_pos[1] + math.sin(rad_b) * 1.5]
        if self.plan:
            self.plan.note_obstacle(
                curr_pos, obs_probe, duration=1800.0,
                reason="stuck against tree/rock obstacle", radius=3, barrier=True,
                heading=(math.cos(rad_b), math.sin(rad_b))
            )
        now_time = time.monotonic()
        if not hasattr(self, "_blocked_sectors"):
            self._blocked_sectors = []
        self._blocked_sectors = [s for s in self._blocked_sectors if s["expires"] > now_time]
        self._blocked_sectors.append({
            "pos": list(curr_pos),
            "angle": angle_blocked,
            "radius": 4.5,
            "span": 80.0,
            "expires": now_time + 120.0
        })

        candidates_escape = []
        if hasattr(self, "_verified_breadcrumbs") and self._verified_breadcrumbs:
            for bc in reversed(self._verified_breadcrumbs):
                d_bc = math.dist(curr_pos, bc)
                if 0.8 <= d_bc <= 6.0:
                    ang_bc = game_to_joystick_angle(bc[0] - curr_pos[0], bc[1] - curr_pos[1])
                    diff_bc = abs((ang_bc - angle_blocked + 180) % 360 - 180)
                    if diff_bc >= 65.0:
                        candidates_escape.append(ang_bc)
                        break

        direct_reverse = (angle_blocked + 180) % 360
        if direct_reverse not in candidates_escape:
            candidates_escape.append(direct_reverse)
        candidates_escape.append((angle_blocked + 110) % 360)
        candidates_escape.append((angle_blocked - 110) % 360)

        initial_p = list(curr_pos)
        escaped_pos = list(curr_pos)

        for attempt_ang in candidates_escape:
            self._notify_status(f"🔙 Đang lùi dứt khoát theo hướng {attempt_ang:.1f}° để thoát khỏi lùm cây/vách đá...")
            if hasattr(self.ctrl, "joystick_press"):
                self.ctrl.joystick_press(attempt_ang)
            elif hasattr(self.ctrl, "joystick_steer"):
                self.ctrl.joystick_steer(attempt_ang)

            sub_start = time.monotonic()
            sub_init_p = list(escaped_pos)
            moved_far_enough = False

            while time.monotonic() - sub_start < 2.0:
                self._stop_event.wait(0.15)
                if not self.is_running or self.is_paused:
                    break
                sample = self.vision.get_engine_telemetry()
                if self._valid_position(sample):
                    escaped_pos = list(sample["position"])
                    net_dist = math.dist(initial_p, escaped_pos)
                    sub_dist = math.dist(sub_init_p, escaped_pos)
                    if net_dist >= 1.5:
                        self._notify_status(f"✅ Đã thoát kẹt thành công ra khoảng trống an toàn ({escaped_pos[0]:.1f}, {escaped_pos[1]:.1f}, cách điểm kẹt {net_dist:.2f} đơn vị).")
                        moved_far_enough = True
                        break
                    if time.monotonic() - sub_start > 0.55 and sub_dist < 0.12:
                        break

            if moved_far_enough:
                break

        if hasattr(self.ctrl, "joystick_release"):
            self.ctrl.joystick_release()

        self._last_source_position = list(escaped_pos)
        if hasattr(self, "bypasser"):
            self.bypasser.reset()
        return escaped_pos

    def _run_path_joystick_continuous(self, target, path, destination, tolerance=None, max_total_seconds=60.0):
        """
        Di chuyển LIÊN TỤC không dừng nghỉ bằng Joystick qua các điểm chỉ dẫn (path -> destination):
        - Không dừng lại ở từng mốc trung gian.
        - Xoay hướng vuốt joystick ngay lập tức khi gần tới mốc kế tiếp.
        - Xử lý vật cản: Chỉ cần thấy 1 lần vuốt mà nhân vật vẫn đứng yên (< 0.12 đơn vị) -> bẻ lái né vật cản ngay.
          Nếu nhịp né tiếp theo vẫn đứng yên -> lập tức chuyển sang mốc khác, không cố đứng thử lại.
        """
        tol = float(self.settings.get("arrival_tolerance", 1.0) if tolerance is None else tolerance)
        from core.ld_controller import game_to_joystick_angle

        # Tạo danh sách các mốc cần qua, mốc cuối là destination
        waypoints = [list(wp) for wp in (path or [])]
        dest_list = list(destination)
        if not waypoints or math.dist(waypoints[-1], dest_list) > 0.3:
            waypoints.append(dest_list)

        wp_idx = 0
        started = time.monotonic()
        consecutive_stalls = 0
        last_publish_time = 0.0
        last_glitch_inspect_time = 0.0
        vision_radius = float(self.settings.get("vision_radius", 3.2))

        # Khởi tạo góc ban đầu và luồng cảm ứng liên tục (zero-lift touch stream)
        curr_p = self._last_source_position or dest_list
        target_init_wp = dest_list
        for wp in waypoints:
            if math.dist(curr_p, wp) >= 0.5:
                target_init_wp = wp
                break
        init_dx = target_init_wp[0] - curr_p[0]
        init_dy = target_init_wp[1] - curr_p[1]
        if math.hypot(init_dx, init_dy) >= 0.05:
            init_angle = game_to_joystick_angle(init_dx, init_dy)
        else:
            init_angle = 0.0
        if hasattr(self.ctrl, "joystick_press"):
            self.ctrl.joystick_press(init_angle)
        last_joystick_angle = init_angle

        # Sliding window cho phát hiện vật cản: loại bỏ hoàn toàn báo động giả khi bắt đầu tăng tốc
        window_anchor_pos = None
        window_anchor_time = started
        bypass_active_until = 0.0
        recent_breadcrumbs = [list(curr_p)]

        def _cleanup_exit(outcome):
            if hasattr(self.ctrl, "joystick_release"):
                self.ctrl.joystick_release()
            if hasattr(self, "_last_glitch_thread") and self._last_glitch_thread is not None:
                self._last_glitch_thread.join(timeout=0.25)
            return outcome

        while self._wait_active():
            if time.monotonic() - started > max_total_seconds:
                return _cleanup_exit("timeout")

            sample = self.vision.get_engine_telemetry()
            if not self._valid_position(sample):
                time.sleep(0.04)
                continue
            if sample["map_id"] != self.current_map_id:
                return _cleanup_exit("map_changed")

            curr_pos = sample["position"]
            self._last_source_position = list(curr_pos)
            if self.plan:
                self.plan.data["current_player_position"] = list(curr_pos)
            if window_anchor_pos is None:
                window_anchor_pos = list(curr_pos)
                window_anchor_time = time.monotonic()

            # Lưu lại vệt di chuyển thông thoáng thực tế (Verified Walkable Breadcrumbs) để lùi khẩn cấp khi gặp ngõ cụt
            if not self._verified_breadcrumbs or math.dist(curr_pos, self._verified_breadcrumbs[-1]) >= 0.35:
                self._verified_breadcrumbs.append(list(curr_pos))
            recent_breadcrumbs = list(self._verified_breadcrumbs)

            # Nhìn trực tiếp khi di chuyển: Quét rộng tầm nhìn nón (Forward Vision Cone)
            current_target_wp = waypoints[wp_idx]
            pre_dx = current_target_wp[0] - curr_pos[0]
            pre_dy = current_target_wp[1] - curr_pos[1]
            pre_hyp = math.hypot(pre_dx, pre_dy) or 1.0
            init_heading = (pre_dx / pre_hyp, pre_dy / pre_hyp)
            if self.plan:
                self.plan.observe_position(curr_pos, tol, active_id=target.get("id"), vision_radius=vision_radius, heading=init_heading)
                self.plan.observe_inspection(curr_pos, radius_override=vision_radius, heading=init_heading)

            # Cập nhật radar trực tiếp liên tục trong khi di chuyển (mỗi 0.28s)
            now_time = time.monotonic()
            if now_time - last_publish_time > 0.28:
                last_publish_time = now_time
                self._publish(force=True)

            # Săn lỗi đồ họa AI trực tiếp bất đồng bộ (hoàn toàn không làm chậm nhịp di chuyển)
            if self.glitch_detector and (now_time - last_glitch_inspect_time > 1.8):
                last_glitch_inspect_time = now_time
                t = threading.Thread(
                    target=self._async_inspect_glitches,
                    args=(dict(sample),),
                    daemon=True
                )
                self._last_glitch_thread = t
                t.start()

            # Kiểm tra xem đã tới đích cuối cùng chưa hoặc target đã hoàn thành nhờ tầm nhìn trực tiếp
            dist_to_final = math.dist(curr_pos, dest_list)
            if dist_to_final <= tol or target.get("state") == "done":
                if hasattr(self, "bypasser"):
                    self.bypasser.reset()
                return _cleanup_exit("arrived")

            # Chuyển mốc tiếp theo nếu đã tới gần hoặc đã vượt qua mốc dọc theo tuyến (bậc thang/dốc)
            while wp_idx < len(waypoints) - 1:
                dist_to_curr = math.dist(curr_pos, waypoints[wp_idx])
                next_wp = waypoints[wp_idx + 1]
                dist_to_next = math.dist(curr_pos, next_wp)

                seg_dx = next_wp[0] - waypoints[wp_idx][0]
                seg_dy = next_wp[1] - waypoints[wp_idx][1]
                seg_len = math.hypot(seg_dx, seg_dy) or 1.0
                to_curr_x = curr_pos[0] - waypoints[wp_idx][0]
                to_curr_y = curr_pos[1] - waypoints[wp_idx][1]
                projection = (to_curr_x * seg_dx + to_curr_y * seg_dy) / seg_len

                if dist_to_curr <= max(1.2, tol) or (projection > 0.25 and dist_to_next < seg_len + 0.4):
                    wp_idx += 1
                else:
                    break

            current_target_wp = waypoints[wp_idx]
            dx = current_target_wp[0] - curr_pos[0]
            dy = current_target_wp[1] - curr_pos[1]
            dist_to_wp = math.hypot(dx, dy)

            if dist_to_wp <= tol and wp_idx >= len(waypoints) - 1:
                if hasattr(self, "bypasser"):
                    self.bypasser.reset()
                return _cleanup_exit("arrived")

            # Auto Mount Maintenance
            if sample.get("doing") == "walk" and (now_time - getattr(self, "_last_mount_check", 0) > 3.0):
                self._last_mount_check = now_time
                if hasattr(self.ctrl, "toggle_mount"):
                    self.ctrl.toggle_mount()

            # Map Dialog Guard: giữ màn hình game 100% không bị che
            if sample.get("map_dialog_open") and hasattr(self.ctrl, "close_map_dialog"):
                self.ctrl.close_map_dialog(_cancel=True)

            # Tính điểm ngắm đón đầu (Pure Pursuit Lookahead) giúp leo bậc thang và bo cua mượt mà
            target_look = list(current_target_wp)
            if wp_idx < len(waypoints) - 1:
                next_wp = waypoints[wp_idx + 1]
                if dist_to_wp < 2.5:
                    blend = (2.5 - dist_to_wp) / 2.5
                    target_look[0] = (1.0 - blend * 0.55) * current_target_wp[0] + (blend * 0.55) * next_wp[0]
                    target_look[1] = (1.0 - blend * 0.55) * current_target_wp[1] + (blend * 0.55) * next_wp[1]

            steer_raw_dx = target_look[0] - curr_pos[0]
            steer_raw_dy = target_look[1] - curr_pos[1]
            steer_hyp = math.hypot(steer_raw_dx, steer_raw_dy) or 1.0
            heading_x = steer_raw_dx / steer_hyp
            heading_y = steer_raw_dy / steer_hyp

            # Cập nhật hướng nhìn thực tế lên radar HUD
            if self.plan:
                self.plan.data["current_heading"] = [round(heading_x, 3), round(heading_y, 3)]

            # Phát hiện vật cản thực tế (Realistic Telemetry Stall Detection):
            # Tọa độ từ game hook cập nhật mỗi ~0.35s - 0.5s. Do đó chu kỳ kiểm tra tối thiểu phải là 1.0s.
            # Trong 1.0s, nhân vật chạy với tốc độ ~4.5 đơn vị/s sẽ đi được 3.0 - 4.5 đơn vị.
            # Nếu trong 1.0s liên tục mà độ dịch chuyển net_moved < 0.20 thì mới xem xét có vật cản.
            if (now_time - started > 0.8) and (now_time >= bypass_active_until):
                time_in_window = now_time - window_anchor_time
                if time_in_window >= 1.0:
                    net_moved = math.dist(curr_pos, window_anchor_pos)
                    # Reset sliding window cho chu kỳ tiếp theo
                    window_anchor_pos = list(curr_pos)
                    window_anchor_time = now_time

                    if net_moved < 0.20:
                        consecutive_stalls += 1
                        angle_blocked = game_to_joystick_angle(heading_x, heading_y)
                        obs_dist = 0.8
                        obs_pt = (curr_pos[0] + heading_x * obs_dist, curr_pos[1] + heading_y * obs_dist)

                        # 1. Ghi nhận vật cản vừa phải (radius=1 để không bao trùm lên mốc đến)
                        if self.plan:
                            self.plan.note_obstacle(obs_pt, obs_pt, duration=180.0, radius=1, barrier=True, heading=(heading_x, heading_y))

                        # 2. Khóa góc cản cho hệ thống bẻ lái (Anti-Reentry Steering Guard)
                        if not hasattr(self, "_blocked_sectors"):
                            self._blocked_sectors = []
                        self._blocked_sectors = [s for s in self._blocked_sectors if s["expires"] > now_time]
                        self._blocked_sectors.append({
                            "pos": list(curr_pos),
                            "angle": angle_blocked,
                            "radius": 3.5,
                            "span": 60.0,
                            "expires": now_time + 45.0
                        })

                        new_route = self.plan.route_to(curr_pos, dest_list) if (self.plan and hasattr(self.plan, "route_to")) else None

                        if consecutive_stalls < 2:
                            # Lần đầu: Ghi nhận vật cản, bẻ lái lách góc và tiếp tục lướt mượt mà theo đường vòng
                            self._notify_status(f"Gặp vật cản tại ({curr_pos[0]:.1f}, {curr_pos[1]:.1f}); bẻ lái lách góc và tiếp tục theo đường vòng.")
                            if hasattr(self, "bypasser") and hasattr(self.bypasser, "find_smart_exit"):
                                bypass_heading = self.bypasser.find_smart_exit(
                                    curr_pos, angle_blocked,
                                    plan=self.plan,
                                    destination=current_target_wp,
                                    breadcrumbs=list(self._verified_breadcrumbs)
                                )
                            else:
                                bypass_heading = (angle_blocked + 80) % 360

                            if hasattr(self.ctrl, "joystick_steer"):
                                self.ctrl.joystick_steer(bypass_heading)
                            last_joystick_angle = bypass_heading

                            new_route_fresh = self.plan.route_to(curr_pos, dest_list) if (self.plan and hasattr(self.plan, "route_to")) else new_route
                            if new_route_fresh:
                                waypoints = [list(wp) for wp in new_route_fresh]
                                if math.dist(waypoints[-1], dest_list) > 0.3:
                                    waypoints.append(dest_list)
                                wp_idx = 0

                            bypass_active_until = now_time + 0.70
                            self._stop_event.wait(0.12)
                            continue
                        else:
                            # Đã thử bẻ lái lách góc mà vẫn bị chặn >= 2 lần liên tiếp (2+ giây không tiến):
                            # Mới kích hoạt quy trình thoát kẹt chủ động ra khoảng trống
                            self._notify_status(f"Vật cản chặn đường tại ({curr_pos[0]:.1f}, {curr_pos[1]:.1f}); kích hoạt lùi thoát kẹt.")
                            self._perform_active_unstuck(curr_pos, angle_blocked)
                            return _cleanup_exit("stalled")
                    else:
                        consecutive_stalls = 0
                        if hasattr(self, "bypasser"):
                            self.bypasser.reset()

            # Nếu đang trong nhịp bẻ lái lách góc (bypass glide), duy trì góc né
            if now_time < bypass_active_until:
                self._movement_may_be_active = True
                self._stop_event.wait(0.12)
                continue

            # Tính góc di chuyển cơ sở theo mục tiêu phía trước
            target_angle = game_to_joystick_angle(heading_x, heading_y)

            # BỘ LỌC CẤM CHUI VÀO LẠI (Anti-Reentry Sector Guard):
            # Nếu góc di chuyển đâm vào khu vực vừa bị kẹt trong bán kính 4.0 đơn vị,
            # LẬP TỨC BẺ LÁI LỆCH RA KHỎI GÓC CẤM để bảo vệ nhân vật tuyệt đối không chui vào lại
            if hasattr(self, "_blocked_sectors") and self._blocked_sectors:
                for s in self._blocked_sectors:
                    if s["expires"] > now_time and math.dist(curr_pos, s["pos"]) <= s["radius"]:
                        ang_diff = (target_angle - s["angle"] + 180) % 360 - 180
                        if abs(ang_diff) < s["span"]:
                            veer_dir = 1.0 if ang_diff >= 0 else -1.0
                            target_angle = (s["angle"] + veer_dir * (s["span"] + 10.0)) % 360
                            break

            # Tầm nhìn đón đầu phía trước (Proactive Forward Lookahead):
            # Nhìn trước 1.8 - 2.5 đơn vị để nhận diện góc tường / bậc thang và chủ động bẻ lái lách qua trước khi va chạm
            if self.plan and hasattr(self.plan, "cast_ray"):
                forward_clearance = self.plan.cast_ray(curr_pos, target_angle, max_dist=2.5, step=0.25)
                if forward_clearance < 1.2:
                    best_veer_angle = target_angle
                    best_clearance = forward_clearance
                    for veer in [30, -30, 50, -50, 75, -75]:
                        cand_angle = (target_angle + veer) % 360
                        cand_clear = self.plan.cast_ray(curr_pos, cand_angle, max_dist=2.8, step=0.25)
                        if cand_clear > best_clearance + 0.5:
                            best_clearance = cand_clear
                            best_veer_angle = cand_angle
                    if best_veer_angle != target_angle:
                        target_angle = best_veer_angle

            # Áp dụng giới hạn góc xoay sinh học thích ứng (Adaptive Angular Slew Rate)
            if last_joystick_angle is not None:
                angle_diff = (target_angle - last_joystick_angle + 180) % 360 - 180
                abs_diff = abs(angle_diff)
                if abs_diff <= 45.0:
                    max_turn = 35.0  # Lái mượt mà như game thủ chuyên nghiệp trên đoạn cong
                elif abs_diff <= 90.0:
                    max_turn = 65.0  # Dứt khoát khi bẻ cua góc vuông / bậc thang
                else:
                    max_turn = 90.0  # Xoay phản ứng nhanh khi đảo hướng gắt
                turn = max(-max_turn, min(max_turn, angle_diff))
                smooth_angle = (last_joystick_angle + turn) % 360
            else:
                smooth_angle = target_angle
            last_joystick_angle = smooth_angle

            # Điều khiển Joystick liên tục không nhấc tay (Seamless Continuous Touch Stream)
            self._movement_may_be_active = True
            if hasattr(self.ctrl, "joystick_steer"):
                self.ctrl.joystick_steer(smooth_angle)
            elif hasattr(self.ctrl, "move_joystick"):
                self.ctrl.move_joystick(smooth_angle, duration_ms=480)

            # Nhịp lướt 120ms (8.3 Hz mượt như lướt ngón tay thật trên màn hình cảm ứng)
            self._stop_event.wait(0.12)

        return _cleanup_exit("interrupted")

    def _cover_map(self):
        maximum = max(1, int(self.settings.get("max_target_attempts", 3)))
        revisit_count = 0
        while self._wait_active():
            target = self.plan.next_target(maximum)
            if target is None:
                if self.plan.add_inspection_gaps():
                    self._notify_status("Đã khép các vòng; bổ sung mốc để kiểm tra phần hình ảnh còn thiếu.")
                    self._save_progress()
                    continue
                with self._state_lock:
                    job = next((job for job in self._revisits if job["map_id"] == self.current_map_id
                                and job["state"] == "pending" and job["attempts"] < 1), None)
                if job is None or revisit_count >= int(self.settings.get("revisit_budget", 3)):
                    return "finished"
                revisit_count += 1
                job["attempts"] += 1
                target = {"id": "review:"+job["bug_key"], "batch": max(p["batch"] for p in self.plan.data["targets"]),
                          "purpose": "tái kiểm tra cảnh nghi ngờ", "options": [job["position"]],
                          "attempts": 0, "total_attempts": 0, "state": "pending", "review_job": job}

            joystick_only = bool(self.settings.get("joystick_only", False))
            if joystick_only:
                sample = self.vision.get_engine_telemetry()
                if self._valid_position(sample):
                    telemetry = sample
                else:
                    telemetry = self._wait_stopped(max_seconds=2.0)
            else:
                telemetry = self._wait_stopped()

            if telemetry["map_id"] != self.current_map_id:
                return "map_changed"
            if not target.get("review_job"):
                self.plan.observe_position(telemetry["position"], float(self.settings.get("arrival_tolerance", 1)))
                if target["state"] == "done":
                    if self.plan.data.get("resume_target_id") == target["id"]:
                        self.plan.data["resume_target_id"] = None
                    self._save_progress()
                    self._publish(force=True)
                    continue
            if self._blocked_by_repeated_stalls(telemetry):
                return "blocked"
            self.current_target = target
            self.plan.data["active_id"] = target["id"]
            self.plan.data["active_path"] = []
            destination = CoveragePlan.destination(target)
            target["destination"] = destination
            tol = float(self.settings.get("arrival_tolerance", 1.0))
            dist_to_dest = math.dist(telemetry["position"], destination)
            if not target.get("review_job") and dist_to_dest <= tol:
                self._complete_target(target)
                self._notify_status(f"Mốc {target['id']} ({target.get('purpose', 'mốc')}) đã ở trong tầm ({dist_to_dest:.2f} <= {tol}); bỏ qua ghim thừa.")
                continue

            # Dùng joystick trực tiếp chỉ cho chế độ không dùng continuous
            direct_walk_max = float(self.settings.get("direct_walk_max_distance", 2.5))
            skip_repeat_direct = (target.get("state") == "retry" and target.get("attempts", 0) > 0
                                  and len(target.get("options", [])) <= 1 and not target.get("review_job"))
            direct_walk_outcome = "stalled" if skip_repeat_direct else None
            if not joystick_only and dist_to_dest <= direct_walk_max and not target.get("review_job") and not skip_repeat_direct:
                self._notify_status(f"Vòng {target['batch']} · {target.get('purpose', 'quét')} → đi bộ bằng joystick ({dist_to_dest:.1f} đơn vị).")
                self._leg = {"id": uuid.uuid4().hex, "mission_id": self._mission_id,
                             "map_id": self.current_map_id, "target_id": target["id"],
                             "ring": target["batch"], "purpose": target.get("purpose", "quét vòng joystick"),
                             "from": list(telemetry["position"]), "to": list(destination),
                             "tolerance": tol, "state": "walking"}
                self.store.event(self._mission_id, "leg_started", self._leg)
                self._phase("walking")
                outcome = self._walk_joystick_direct(target, destination)
                direct_walk_outcome = outcome
                if outcome == "stalled":
                    self._notify_status("Joystick chưa tiến gần đích; dừng thử tại chỗ và chuyển sang tìm đường trên map.")
                self._leg["state"] = outcome
                self.store.event(self._mission_id, "leg_result", self._leg)
                if outcome == "arrived":
                    self._complete_target(target)
                    if target.get("is_perimeter") or "góc" in target.get("purpose", ""):
                        self._probe_corner_crevice(target)
                    if hasattr(self.plan, "progress_summary"):
                        prog = self.plan.progress_summary()
                        self._notify_status(f"[Tiến độ map] Vòng {target['batch']}/{prog['max_ring']} · Đã xong {prog['done']}/{prog['total']} mốc ({prog['percent']:.1f}%)")
                        if prog["is_complete"]:
                            self._notify_status(f"Đã tới toàn bộ {prog['total']} mốc tuyến của {self.current_map_name}; đang đối chiếu độ phủ hình ảnh riêng.")
                    if target.get("is_perimeter") or "góc" in target.get("purpose", ""):
                        self._save_progress()
                        self._publish(force=True)
                    continue
                if outcome in {"interrupted", "map_changed", "relocated"}:
                    return outcome
                if outcome in {"walked", "stalled"}:
                    current_after_direct = self._wait_stopped()
                    if self._valid_position(current_after_direct):
                        if current_after_direct["map_id"] != self.current_map_id:
                            return "map_changed"
                        telemetry = current_after_direct
                        self.plan.observe_position(telemetry["position"], tol, active_id=target["id"])
            elif skip_repeat_direct:
                self._notify_status(f"Ô {target['id']} đã thử tại cùng một điểm; bỏ lặp joystick và tính đường từ vị trí hiện tại.")

            target["state"] = "active"
            target["attempts"] += 1
            target["total_attempts"] += 1
            route_started = time.monotonic()
            path = self.plan.route_to(telemetry["position"], destination)
            if hasattr(self.ctrl, "metrics"):
                self.ctrl.metrics.record("route_planning", time.monotonic()-route_started)
            self.plan.data["active_path"] = path or []
            if not path:
                # Không tìm được đường A* tới đích:
                from core.ld_controller import game_to_joystick_angle
                to_dest_angle = game_to_joystick_angle(destination[0] - telemetry["position"][0], destination[1] - telemetry["position"][1])
                if self.plan and not self.plan.is_walkable(telemetry["position"][0], telemetry["position"][1]):
                    self._notify_status("Vị trí nhân vật nằm trong vùng cản; kích hoạt thoát kẹt đưa ra khoảng trống.")
                    new_pos = self._perform_active_unstuck(telemetry["position"], to_dest_angle)
                    telemetry["position"] = new_pos
                    path = self.plan.route_to(telemetry["position"], destination)
                    self.plan.data["active_path"] = path or []
                if not path:
                    target["state"] = "deferred"
                    target["reason"] = "Không tìm thấy hành lang đường đi tới mốc; tạm hoãn để đi mốc khác."
                    self._notify_status(f"Mốc {target['id']} không có lối đi thông suốt; tạm hoãn và chuyển mốc tiếp theo.")
                    self._save_progress()
                    self._publish(force=True)
                    continue

            outcome = "retry"
            if joystick_only:
                self._phase("walking")
                self._leg = {"id": uuid.uuid4().hex, "mission_id": self._mission_id,
                             "map_id": self.current_map_id, "target_id": target["id"],
                             "ring": target["batch"], "purpose": target.get("purpose", "quét viền/góc"),
                             "from": list(telemetry["position"]), "to": list(destination),
                             "tolerance": tol, "state": "walking"}
                self.store.event(self._mission_id, "leg_started", self._leg)
                self._save_progress()
                num_wp = len(path) if path else 1
                self._notify_status(
                    f"Vòng {target['batch']} · {target.get('purpose', 'khảo sát')} "
                    f"→ chạy liên tục qua {num_wp} mốc tới ({destination[0]:.1f}, {destination[1]:.1f})."
                )
                outcome = self._run_path_joystick_continuous(target, path, destination, tolerance=tol)
                self._leg["state"] = outcome
                self.store.event(self._mission_id, "leg_result", self._leg)
                if outcome == "arrived":
                    self._complete_target(target)
                    if hasattr(self.plan, "progress_summary"):
                        prog = self.plan.progress_summary()
                        self._notify_status(f"[Tiến độ map] Vòng {target['batch']}/{prog['max_ring']} · Đã xong {prog['done']}/{prog['total']} mốc ({prog['percent']:.1f}%)")
                        if prog["is_complete"]:
                            self._notify_status(f"Đã tới toàn bộ {prog['total']} mốc tuyến của {self.current_map_name}; đang đối chiếu độ phủ hình ảnh riêng.")
                    self._save_progress()
                    self._publish(force=True)
                    continue
                if outcome == "stalled":
                    retry_allowed = target["attempts"] < maximum
                    target["state"] = "retry" if (retry_allowed and target["attempts"] < 2) else "deferred"
                    if target["state"] == "deferred":
                        target["reason"] = "Đứng yên khi gặp vật cản; hoãn và chuyển sang mốc khác ngay."
                        self._notify_status(f"Ô {target['id']} bị chặn bởi vật cản; hoãn và chuyển ngay sang mốc tiếp theo.")
                    else:
                        target["reason"] = "Đứng yên khi gặp vật cản; ghi nhận vật cản và thử lại đường vòng sau."
                        self._notify_status(f"Ô {target['id']} bị chặn bởi vật cản; ghi nhận vật cản và chuyển mốc tiếp theo.")
                    self._save_progress()
                    self._publish(force=True)
                    continue
                if outcome in {"interrupted", "map_changed", "relocated"}:
                    return outcome
            elif path:
                self._save_progress()
                for index, waypoint in enumerate(path):
                    if not self._wait_active():
                        outcome = "interrupted"
                        break
                    current = self._wait_stopped()
                    if not self._wait_active():
                        outcome = "interrupted"
                        break
                    if current["map_id"] != self.current_map_id:
                        outcome = "map_changed"
                        break
                    if math.dist(current["position"], waypoint) <= (0.5 if index < len(path)-1 else tol):
                        continue
                    self._phase("pinning")
                    self._leg = {"id": uuid.uuid4().hex, "mission_id": self._mission_id,
                                 "map_id": self.current_map_id, "target_id": target["id"],
                                 "ring": target["batch"], "purpose": target.get("purpose", "quét vòng"),
                                 "from": list(current["position"]), "to": list(waypoint),
                                 "tolerance": tol, "state": "pinning"}
                    self.store.event(self._mission_id, "leg_started", self._leg)
                    self._save_progress()
                    self._notify_status(
                        f"Vòng {target['batch']} · {target.get('purpose', 'khảo sát')} — đoạn {index+1}/{len(path)} "
                        f"→ ({waypoint[0]:.1f}, {waypoint[1]:.1f})."
                    )
                    try:
                        self.surveyor.pin(*waypoint, self.current_map_id)
                    except RuntimeError as e:
                        if "Map thay đổi" in str(e) or "sang map" in str(e):
                            outcome = "map_changed"
                            break
                        raise
                    self._needs_repin = False
                    self._leg["state"] = "walking"
                    self._phase("walking")
                    outcome = self._walk_target(target, waypoint)
                    self._leg["state"] = outcome
                    self.store.event(self._mission_id, "leg_result", self._leg)
                    if outcome != "arrived":
                        break
            else:
                self._notify_status(f"Chưa tìm được hành lang tới ô {target['id']}; kiểm tra tiến độ trước khi thử bước tiếp theo.")

            # Chỉ chỉnh bằng joystick khi còn rất sát đích; xa hơn thì giữ đường ghim
            # để tránh chạy lệch khỏi vòng khảo sát.
            if outcome != "arrived" and not target.get("review_job"):
                current_sample = self._wait_stopped()
                if self._valid_position(current_sample):
                    remaining_dist = math.dist(current_sample["position"], destination)
                    direct_made_progress = (direct_walk_outcome is None
                                             or dist_to_dest - remaining_dist >= 0.25)
                    correction_distance = float(self.settings.get("final_joystick_correction_distance", 1.5))
                    if remaining_dist <= correction_distance and direct_made_progress:
                        self._notify_status(f"Ghim map đã đưa nhân vật tới gần đích ({remaining_dist:.1f} đơn vị); chuyển sang joystick (ô tròn) đi nốt đoạn cuối.")
                        self._phase("walking")
                        joystick_outcome = self._walk_joystick_direct(target, destination, max_steps=5)
                        if joystick_outcome == "arrived":
                            outcome = "arrived"

            if outcome == "arrived":
                self._complete_target(target)
                if target.get("is_perimeter") or "góc" in target.get("purpose", ""):
                    self._probe_corner_crevice(target)
                if hasattr(self.plan, "progress_summary"):
                    prog = self.plan.progress_summary()
                    self._notify_status(f"[Tiến độ map] Vòng {target['batch']}/{prog['max_ring']} · Đã xong {prog['done']}/{prog['total']} mốc ({prog['percent']:.1f}%)")
                    if prog["is_complete"]:
                        self._notify_status(f"Đã tới toàn bộ {prog['total']} mốc tuyến của {self.current_map_name}; đang đối chiếu độ phủ hình ảnh riêng.")
                if target.get("review_job"):
                    # Hold a small bounded observation window after reaching the scene.
                    for _ in range(5):
                        if not self._wait_active():
                            break
                        sample = self.vision.get_engine_telemetry()
                        if not self._valid_position(sample) or sample["map_id"] != self.current_map_id:
                            break
                        self._inspect_glitches(self.ctrl.capture_frame(), sample)
                        self._stop_event.wait(0.5)
                    target["review_job"]["state"] = "observed_again"
            elif outcome in {"retry", "deviated"}:
                final_sample = self._wait_stopped()
                no_distance_progress = True
                if self._valid_position(final_sample) and final_sample["map_id"] == self.current_map_id:
                    final_distance = math.dist(final_sample["position"], destination)
                    no_distance_progress = dist_to_dest - final_distance < 0.25
                same_route_stalled = len(target.get("options", [])) <= 1 and no_distance_progress
                retry_allowed = target["attempts"] < maximum and not same_route_stalled
                target["state"] = "retry" if retry_allowed else "deferred"
                if same_route_stalled:
                    target["reason"] = "Đã thử tuyến một lần nhưng không tiến gần đích; tạm hoãn để tiếp tục các mốc khác."
                    self._notify_status(f"Ô {target['id']} không tiến gần sau một lần thử; tạm hoãn để tool tiếp tục mốc khác.")
                else:
                    target["reason"] = "Chưa tìm được đường hoặc chặng không tới đích; chưa kết luận vật cản vĩnh viễn."
                    self._notify_status(f"Ô {target['id']} chưa tới được; lưu lại và tự thử đường vào khác.")
                if path and self._valid_position(final_sample):
                    area = self.plan.record_stall(
                        final_sample["position"], destination,
                        radius=float(self.settings.get("stalled_area_radius", 4)),
                        duration=float(self.settings.get("stalled_area_cooldown", 600)))
                    self.store.event(self._mission_id, "stalled_area", dict(area))
                    if self._blocked_by_repeated_stalls(final_sample):
                        target["state"] = "deferred"
                        self.plan.data["active_id"] = None
                        self.plan.data["active_path"] = []
                        self._save_progress()
                        return "blocked"
                    if area["failures"] == 1 and target["state"] == "retry":
                        recovery = self._backtrack_from_obstacle()
                        if recovery in {"interrupted", "map_changed", "relocated"}:
                            outcome = recovery
            else:
                target["state"] = "retry"
                if outcome == "repin":
                    if not target.get("review_job"):
                        self.plan.data["resume_target_id"] = target["id"]
                    target["attempts"] = max(0, target["attempts"]-1)
            if target.get("review_job") and outcome != "arrived":
                target["review_job"]["state"] = "deferred"
            self.plan.data["active_id"] = None
            self.plan.data["active_path"] = []
            needs_final_save = (outcome != "arrived" or target.get("review_job")
                                or target.get("is_perimeter") or "góc" in target.get("purpose", ""))
            if needs_final_save:
                self._save_progress()
                self._publish(force=True)
            if outcome in {"interrupted", "map_changed", "relocated"}:
                return outcome
        return "interrupted"


    def _navigate_to_map_via_link(self, target):
        navigation = self.ctrl.config.get("navigation", {})
        connection = next((edge for edge in navigation.get("connections", [])
                           if edge.get("from") == self.current_map_id and edge.get("to") == target["id"]
                           and edge.get("verified") and edge.get("exit")), None)
        if connection:
            return self._navigate_portal(target, connection)
        world_slot = navigation.get("world_slot_overrides", {}).get(str(target["id"]))
        if world_slot and world_slot.get("verified"):
            return self._navigate_world_slot(target, world_slot)
        if target.get("screen_xy") or target.get("cocos_xy"):
            return self._navigate_world_slot(target, target)
        layout = target.get("legacy_link")
        if not layout:
            return False
        self._wait_stopped()
        previous_id = self.current_map_id
        self._phase("transition")
        self.surveyor.open_map()
        width, height = self.surveyor.screen_size
        def tap(x, y, delay=0.3):
            self.ctrl.tap(round(x*width/1920), round(y*height/1080), jitter=False, delay=delay)
        tap(275, 925, delay=0.5)
        # Start from a reproducible list origin, including after a previous map.
        for _ in range(4):
            if not self._wait_active():
                raise InterruptedError()
            self.ctrl.swipe(round(1500*width/1920), round(320*height/1080),
                            round(1500*width/1920), round(850*height/1080), duration_ms=250)
        for _ in range(layout.get("page", 0)):
            if not self._wait_active():
                raise InterruptedError()
            self.ctrl.swipe(round(1500*width/1920), round(750*height/1080),
                            round(1500*width/1920), round(320*height/1080), duration_ms=250)
        y = 245+layout["row_idx"]*55
        if y > 880:
            self.ctrl.close_map_dialog()
            return False
        tap(1450, y)
        tap(1630, 910, delay=0.3)
        self.ctrl.close_map_dialog()
        return self._await_map(target["id"], 180)

    def _navigate_portal(self, target, connection):
        sample = self._wait_stopped()
        path = self.plan.route_to(sample["position"], connection["exit"])
        if not path:
            return False
        self._phase("transition")
        for waypoint in path:
            sample = self._wait_stopped()
            if sample["map_id"] != self.current_map_id:
                if sample["map_id"] != target["id"]:
                    raise RuntimeError("Cửa ra dẫn sang map khác dự kiến; chưa đánh dấu map đích đã tới.")
                return True
            self._leg = {"id": uuid.uuid4().hex, "purpose": "tới cửa ra sang "+target["name"],
                         "map_id": self.current_map_id, "from": list(sample["position"]), "to": list(waypoint)}
            self._save_progress()
            self._movement_may_be_active = True
            self.surveyor.pin(*waypoint, self.current_map_id)
            outcome = self._walk_target({"id": "exit"}, waypoint)
            if outcome == "map_changed":
                if self._wait_stopped()["map_id"] != target["id"]:
                    raise RuntimeError("Cửa ra dẫn sang map khác dự kiến; giữ map đích là chưa tới.")
                return True
            if outcome != "arrived":
                return False
        return self._await_map(target["id"], 20)

    def _navigate_world_slot(self, target, slot):
        self._wait_stopped()
        if self.route_phase != "transition_return":
            self._phase("transition")
        self.ctrl.open_world_map()
        # Chờ bảng Bản đồ thế giới sẵn sàng
        world_ready = False
        for _ in range(12):
            sample = self.vision.get_engine_telemetry()
            if sample.get("map_data", {}).get("world", {}).get("up"):
                world_ready = True
                break
            self._stop_event.wait(0.15)
        if not world_ready:
            self.ctrl.close_map_dialog()
            return False
        width, height = self.surveyor.screen_size
        x, y = slot["screen_xy"]
        self.ctrl.tap(round(x*width/1920), round(y*height/1080), jitter=False, delay=0.3)
        # Chờ bản đồ chi tiết của map đích hiển thị
        for _ in range(10):
            sample = self.vision.get_engine_telemetry()
            world = sample.get("map_data", {}).get("world", {})
            if world.get("detail") == 1 and (world.get("detail_map") == target["id"] or target["id"] is None):
                break
            self._stop_event.wait(0.15)
        # Bấm điểm trung tâm bản đồ chi tiết để kích hoạt tự tìm đường liên map
        confirm_xy = slot.get("confirm_xy", [959, 539])
        cx, cy = confirm_xy
        self._movement_may_be_active = True
        self.ctrl.tap(round(cx*width/1920), round(cy*height/1080), jitter=False, delay=0.3)
        if self.vision.get_engine_telemetry().get("map_dialog_open"):
            self.ctrl.close_map_dialog()
        return self._await_map(target["id"], 180)

    def _await_map(self, expected, timeout):
        deadline = time.monotonic()+timeout
        last_motion = time.monotonic()
        previous_pos = None
        while self._wait_active() and time.monotonic() < deadline:
            sample = self.vision.get_engine_telemetry()
            if self._valid_position(sample):
                current_map = sample["map_id"]
                current_pos = sample["position"]
                if previous_pos is None or math.dist(previous_pos, current_pos) > 0.08:
                    last_motion = time.monotonic()
                    previous_pos = current_pos
                if current_map == expected:
                    self._wait_stopped()
                    self._notify_status(f"Đã sang map mới {sample.get('map_name', expected)} thành công.")
                    return True
                is_cross_map = (sample.get("auto_move") == 1
                                or sample.get("map_data", {}).get("goto", {}).get("cross_map") == 1
                                or sample.get("doing") in self.MOVING)
                if not is_cross_map and (time.monotonic() - last_motion > 12.0):
                    self._cancel_and_verify()
                    return False
            self._stop_event.wait(0.3)
        self._cancel_and_verify()
        return False

    def _has_entry(self, target):
        navigation = self.ctrl.config.get("navigation", {})
        slot = navigation.get("world_slot_overrides", {}).get(str(target["id"]), {})
        return bool(target.get("screen_xy") or target.get("cocos_xy") or target.get("legacy_link") or slot.get("verified") or any(
            edge.get("from") == self.current_map_id and edge.get("to") == target["id"] and edge.get("verified")
            for edge in navigation.get("connections", [])))

    def _run_loop(self):
        attempted = set()
        bound = False
        relocations = 0
        try:
            if hasattr(self.ctrl, "ensure_connection"):
                self.ctrl.ensure_connection()
                self._notify_status(self.ctrl.connection_status)
            if hasattr(self.ctrl, "lock_session"):
                self.ctrl.lock_session()
            bound = True
            self._bound = True
            if hasattr(self.ctrl, "set_input_gate"):
                self.ctrl.set_input_gate(lambda: self.is_running)
            if hasattr(self.ctrl, "calibrate_resolution"):
                self.surveyor.screen_size = self.ctrl.calibrate_resolution()
            if not self._valid_position(self.vision.get_engine_telemetry()):
                raise RuntimeError("Chưa có vị trí mới từ nhân vật. Hãy vào game và đợi dữ liệu cập nhật trước khi bắt đầu.")
            self._configure_profile()
            self.store.event(self._mission_id, "mission_started", {"profile": self.profile})
            if self.sheet_sync and hasattr(self.sheet_sync, "start"):
                self.sheet_sync.start()
            resume_ok = self.pending_map_return is None or self._recover_pending_map_return()
            while resume_ok and self._wait_active():
                self._prepare_plan()
                outcome = self._cover_map()
                if outcome == "interrupted":
                    break
                if outcome in {"map_changed", "relocated"}:
                    relocations += 1
                    if relocations > 5:
                        raise RuntimeError("Nhiều lần chết/dịch chuyển trong một phiên; giữ tiến độ để kiểm tra nguyên nhân.")
                    self._cancel_and_verify()
                    cur_telem = self.vision.get_engine_telemetry()
                    if not self._handle_unexpected_map_change(cur_telem):
                        self._phase("partial")
                        break
                    continue
                attempted.add(self.current_map_id)
                complete = self.plan.complete()
                route_complete = self.plan.is_route_complete()
                unfinished_targets = sum(point["state"] != "done" for point in self.plan.data["targets"])
                self._map_results[str(self.current_map_id)] = {
                    "name": self.current_map_name,
                    "state": "complete" if complete else "route_complete" if route_complete else "partial",
                    "reason": ("" if complete else
                               "Đã tới đủ mốc tuyến; phạm vi quan sát hình ảnh chưa được hiệu chỉnh để xác nhận toàn map."
                               if route_complete else
                               self.plan.data.get("blocked_reason") or
                               f"Còn {unfinished_targets} mốc chưa tới; cần giữ map hiện tại và tiếp tục sau."),
                    "done": len(self.plan.data["targets"])-unfinished_targets,
                    "total": len(self.plan.data["targets"]),
                    **self.plan.coverage()}
                if complete or route_complete:
                    self.visited_maps.add(self.current_map_id)
                    if complete:
                        self._notify_status(f"Đã hoàn thành {self.current_map_name}: toàn bộ mốc tuyến đã tới và vùng nền đủ điều kiện xác nhận đã kiểm tra.")
                    else:
                        self._notify_status(f"Đã tới toàn bộ mốc tuyến của {self.current_map_name}. Độ phủ ảnh chưa hiệu chuẩn nên chưa xác nhận toàn bộ bề mặt map.")
                else:
                    self._notify_status(f"Còn {unfinished_targets} mốc chưa tới ở {self.current_map_name}; dừng tại map này để không chuyển map khi tuyến còn thiếu.")
                    self._save_progress()
                    self._phase("partial")
                    break
                self._save_progress()
                remaining = []
                for offset in range(1, len(self.ordered_maps)+1):
                    item = self.ordered_maps[(self.current_map_idx+offset) % len(self.ordered_maps)]
                    if item["id"] is not None and item["id"] not in attempted | self.visited_maps:
                        remaining.append(item)
                if not remaining or not self.settings.get("auto_next_map", True):
                    all_complete = all(item.get("state") in {"complete", "route_complete"}
                                       for item in self._map_results.values())
                    self._phase("completed" if all_complete else "partial")
                    break
                transitioned = False
                # Prefer a verified adjacent exit, then the known inter-map UI.
                connections = self.ctrl.config.get("navigation", {}).get("connections", [])
                neighbours = {edge["to"]: edge.get("cost", 1) for edge in connections
                              if edge.get("from") == self.current_map_id and edge.get("verified")}
                remaining.sort(key=lambda target: (target["id"] not in neighbours, neighbours.get(target["id"], 0)))
                for target in remaining:
                    if not self._has_entry(target):
                        self._map_results[str(target["id"])] = {"name": target["name"], "state": "no_route",
                                                                 "reason": "Chưa có thao tác cửa vào đã hiệu chỉnh; không tự ghim tọa độ đoán."}
                        continue
                    self._notify_status(f"Đã khép tuyến hiện tại; tới {target['name']} để khảo sát phần chưa làm.")
                    if self._navigate_to_map_via_link(target):
                        transitioned = True
                        break
                    attempted.add(target["id"])
                    self._map_results[str(target["id"])] = {"name": target["name"], "state": "entry_failed",
                                                             "reason": "Chưa xác minh tới map đích; có thể thiếu điều kiện mở cửa."}
                    self._save_progress()
                if not transitioned:
                    self._phase("partial")
                    break
        except InterruptedError:
            self._phase("stopping")
        except Exception as exc:
            self._phase("error")
            self._notify_status(f"Dừng hành trình: {exc}")
        finally:
            if bound:
                try:
                    cancel_thread = self._stop_cancel_thread
                    if cancel_thread and cancel_thread.is_alive():
                        cancel_thread.join(timeout=10)
                        if cancel_thread.is_alive():
                            raise RuntimeError("Lệnh hủy di chuyển vẫn đang chờ; chưa thể xác nhận dừng.")
                    if self._movement_may_be_active:
                        self._cancel_and_verify()
                except Exception as exc:
                    self._phase("stop_unverified")
                    self._notify_status(f"Chưa xác minh nhân vật đã dừng: {exc}")
                finally:
                    if hasattr(self.ctrl, "unlock_session"):
                        self.ctrl.unlock_session()
                    self._bound = False
            if self.route_phase not in {"completed", "partial", "error", "stop_unverified"}:
                self._phase("stopped")
            if self.plan:
                for point in self.plan.data["targets"]:
                    if point["state"] == "active":
                        point["state"] = "retry"
                self.plan.data["active_id"] = None
                self.plan.data["active_path"] = []
                try:
                    self._save_progress()
                except Exception as exc:
                    self._notify_status(f"Không lưu được tiến độ: {exc}")
            else:
                try:
                    self._save_progress()
                except Exception as exc:
                    self._notify_status(f"Không lưu được trạng thái: {exc}")
            self.is_running = False
            self._publish(force=True)

    def user_confirm_bug(self, custom_note=None, incident=None):
        selected = incident or self.current_incident
        if not selected:
            return None
        record = self.sheet_sync.add_confirmed_bug(selected, custom_note)
        if self.current_incident and self.current_incident["id"] == selected["id"]:
            self.current_incident = None
        self.waiting_for_user_review = False
        return record

    def user_reject_bug(self, incident=None):
        selected = incident or self.current_incident
        if selected and self.sheet_sync:
            self.sheet_sync.reject(selected)
        if self.current_incident and selected and self.current_incident["id"] == selected["id"]:
            self.current_incident = None
        self.waiting_for_user_review = False
