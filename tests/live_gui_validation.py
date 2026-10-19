"""Explicit live GUI acceptance. Opens the real tool and leaves it stopped for review.

python -B tests/live_gui_validation.py --seconds 150 --arrivals 2
Uses real game input. Not part of unittest discovery.
"""

import argparse
import atexit
import ctypes
import json
import math
from pathlib import Path
import sys
import time
import traceback

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.dont_write_bytecode = True

from PIL import ImageGrab

from core.coverage_planner import atomic_json
from core.single_instance import SingleInstanceLock
from gui.app_gui import AppGUI


class LiveGUIReview:
    def __init__(self, app, seconds, arrivals):
        self.app, self.seconds, self.arrivals = app, seconds, arrivals
        self.directory = ROOT / "reports" / "gui_review"
        self.directory.mkdir(parents=True, exist_ok=True)
        self.started = time.monotonic()
        self.stage = "ready"
        self.stage_started = self.started
        self.result = {"passed": False, "auto_next_map": False, "samples": [], "checks": {}, "gui_errors": []}
        self.first_mission = None
        self.initial_map = None
        self.pause_requested = False
        self.resumed = False
        self.saved_ids = set()
        self.last_phase = None
        self.last_sample_at = 0
        app.engine.settings["auto_next_map"] = False
        app.report_callback_exception = self.callback_error
        app.log(f"[Kiểm tra trực tiếp] Tối đa {seconds:.0f} giây; giữ nguyên map, thử tạm dừng, tiếp tục và lưu/khôi phục.")
        app.after(500, self.tick)

    def mark(self, stage):
        self.stage = stage
        self.stage_started = time.monotonic()
        self.app.log(f"[Kiểm tra trực tiếp] {stage}")

    def callback_error(self, error_type, error, tb):
        traceback.print_exception(error_type, error, tb)
        self.result["gui_errors"].append(str(error))
        self.result["passed"] = False
        self.app.engine.stop()
        atomic_json(str(self.directory / "result.json"), self.result)
        if self.stage != "finished":
            self.mark("stop_final")

    def capture(self, name, widget=None):
        widget = widget or self.app
        try:
            hwnd = ctypes.windll.user32.GetAncestor(widget.winfo_id(), 2)
            if ctypes.windll.user32.IsIconic(hwnd):
                return
            ImageGrab.grab(window=hwnd).save(self.directory / (name+".png"))
        except Exception as exc:
            self.result.setdefault("capture_errors", []).append(str(exc))

    def sample(self):
        with self.app.vision._telemetry_lock:
            return dict(self.app.vision._cached_telemetry or {})

    def worker_alive(self):
        worker = self.app.engine.worker_thread
        return bool(worker and worker.is_alive())

    def finish(self):
        engine = self.app.engine
        self.result.update(elapsed_seconds=round(time.monotonic()-self.started, 2),
                           final_phase=engine.route_phase, metrics=self.app.ctrl.metrics.snapshot())
        self.result["passed"] = bool(self.result["checks"]) and all(self.result["checks"].values())
        if self.result.get("error") or self.result["gui_errors"]:
            self.result["passed"] = False
        atomic_json(str(self.directory / "result.json"), self.result)
        self.capture("tool_stopped")
        self.app.log("[Kiểm tra trực tiếp] " + ("ĐẠT" if self.result["passed"] else "CÒN MỤC CHƯA ĐẠT")
                     + "; đã dừng. Kết quả: reports/gui_review/result.json")
        self.stage = "finished"
        if self.app._current_map_preview is not None:
            self.app.open_map_viewer()
            self.app.after(800, lambda: self.capture("map_large", self.app._map_viewer))

    def tick(self):
        if self.app._closing or self.stage == "finished":
            return
        try:
            self.step()
        except Exception as exc:
            self.result["error"] = str(exc)
            self.result["traceback"] = traceback.format_exc()
            self.app.log(f"[Kiểm tra trực tiếp] Gặp lỗi: {exc}; đang dừng.")
            self.app.action_stop()
            self.mark("stop_final")
        if self.stage != "finished":
            self.app.after(250, self.tick)

    def step(self):
        now = time.monotonic()
        engine = self.app.engine
        sample = self.sample()
        if now-self.last_sample_at >= 1 and sample.get("position"):
            self.result["samples"].append({
                "elapsed": round(now-self.started, 2), "phase": engine.route_phase,
                **{key: sample.get(key) for key in ("map_id", "position", "doing", "position_age")}})
            self.last_sample_at = now
        if engine.route_phase != self.last_phase:
            print("GUI phase:", engine.route_phase, flush=True)
            self.last_phase = engine.route_phase
        checks = self.result["checks"]
        if self.stage == "ready":
            if self.app._game_ready and not self.app._detecting_ld:
                self.capture("tool_before_run")
                self.initial_map = sample["map_id"]
                self.app.action_start()
                self.first_mission = engine._mission_id
                self.mark("running")
            elif now-self.started > 30:
                raise RuntimeError("Nhân vật chưa có vị trí mới sau 30 giây.")
            return
        if self.stage in {"running", "pause_wait", "pause_hold"}:
            if engine.route_phase in {"error", "stop_unverified"}:
                raise RuntimeError("Nhiệm vụ báo lỗi: "+engine.route_phase)
            if now-self.started > self.seconds:
                checks["requested_arrivals"] = False
                self.app.action_stop()
                self.mark("stop_first")
                return
            if not self.worker_alive() and engine.route_phase in {"partial", "completed"}:
                checks["requested_arrivals"] = False
                self.result["ended_reason"] = (engine.plan.data.get("blocked_reason") if engine.plan else None)
                self.app.action_stop()
                self.mark("stop_first")
                return
        if self.stage == "running":
            if engine.route_phase == "walking" and not self.pause_requested:
                leg = engine._leg or {}
                if (leg.get("from") and sample.get("position")
                        and sample.get("doing") in engine.MOVING
                        and math.dist(leg["from"], sample["position"]) >= .8):
                    self.capture("tool_running")
                    self.expected_target = (engine.current_target or {}).get("id")
                    self.app.action_pause()
                    self.pause_requested = True
                    self.mark("pause_wait")
            with engine.store.connection() as db:
                rows = db.execute("SELECT payload FROM events WHERE mission=? AND kind='leg_result'",
                                  (self.first_mission,)).fetchall()
            legs = [json.loads(row[0]) for row in rows]
            arrivals = [leg for leg in legs if leg.get("state") == "arrived"
                        and leg.get("from") and leg.get("to") and math.dist(leg["from"], leg["to"]) >= 1]
            if self.resumed and len(arrivals) >= self.arrivals:
                self.result["legs"] = legs
                checks["requested_arrivals"] = True
                self.app.action_stop()
                self.mark("stop_first")
        elif self.stage == "pause_wait":
            if engine._pause_ack:
                checks["pause_acknowledged"] = True
                self.pause_position = list(sample["position"])
                self.capture("tool_paused")
                self.mark("pause_hold")
            elif now-self.stage_started > 25:
                raise RuntimeError("Tạm dừng chưa được xác minh sau 25 giây.")
        elif self.stage == "pause_hold" and now-self.stage_started >= 2:
            displacement = math.dist(self.pause_position, sample["position"])
            self.result["pause_displacement"] = displacement
            checks["pause_held_position"] = displacement <= .1
            checks["resume_same_target"] = (engine.current_target or {}).get("id") == self.expected_target
            self.app.action_pause()
            self.resumed = not engine.is_paused
            checks["resume_accepted"] = self.resumed
            self.mark("running")
        elif self.stage == "stop_first":
            if not self.worker_alive():
                checks["first_stop_verified"] = (engine.route_phase != "stop_unverified"
                                                  and sample.get("doing") in engine.STOPPED)
                self.saved_ids = {p["id"] for p in engine.plan.data["targets"] if p["state"] == "done"}
                self.result["saved_done_count"] = len(self.saved_ids)
                self.capture("tool_first_stop")
                self.app.action_start()
                self.mark("reload_saved")
            elif now-self.stage_started > 35:
                raise RuntimeError("Dừng lần một chưa hoàn tất sau 35 giây.")
        elif self.stage == "reload_saved":
            if engine._mission_id != self.first_mission and engine.plan is not None:
                loaded = {p["id"] for p in engine.plan.data["targets"] if p["state"] == "done"}
                checks["saved_progress_reloaded"] = bool(self.saved_ids) and self.saved_ids <= loaded
                self.result["reloaded_done_count"] = len(loaded)
                self.capture("tool_reloaded")
                self.app.action_stop()
                self.mark("stop_final")
            elif now-self.stage_started > 25:
                raise RuntimeError("Chưa nạp lại được tiến độ sau 25 giây.")
        elif self.stage == "stop_final":
            if not self.worker_alive():
                checks["final_stop_verified"] = (engine.route_phase not in {"error", "stop_unverified"}
                                                  and sample.get("doing") in engine.STOPPED)
                self.final_position = list(sample.get("position") or [0, 0])
                self.mark("stopped_hold")
            elif now-self.stage_started > 35:
                raise RuntimeError("Dừng cuối chưa hoàn tất sau 35 giây.")
        elif self.stage == "stopped_hold" and now-self.stage_started >= 4:
            checks["no_movement_after_stop"] = math.dist(self.final_position, sample["position"]) <= .1
            checks["same_map"] = self.initial_map is not None and all(
                item["map_id"] == self.initial_map for item in self.result["samples"])
            self.finish()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--seconds", type=float, default=150)
    parser.add_argument("--arrivals", type=int, default=2)
    args = parser.parse_args()
    if not (30 <= args.seconds <= 300) or args.arrivals < 1:
        parser.error("seconds must be between 30 and 300 and arrivals must be positive")
    lock = SingleInstanceLock(str(ROOT / "reports" / "tool-instance.lock"))
    if not lock.acquire():
        raise RuntimeError("Đã có cửa sổ tool đang mở; đóng bình thường trước khi test GUI.")
    atexit.register(lock.release)
    app = AppGUI()
    app.after(300, app.deiconify)
    review = LiveGUIReview(app, args.seconds, args.arrivals)
    app._live_review = review
    app.mainloop()


if __name__ == "__main__":
    main()
