"""Temporal visual candidates. A dark area alone is not proof of a game defect."""

import collections
import hashlib
import json
import math
import os
import queue
import threading
import time
import uuid

import cv2
import numpy as np

from core.runtime_store import ROOT, utc_now


class GlitchDetector:
    def __init__(self, evidence_dir=None, settings=None):
        self.evidence_dir = evidence_dir or os.path.join(ROOT, "reports", "evidence")
        os.makedirs(self.evidence_dir, exist_ok=True)
        self.settings = settings or {}
        self.pending_review = None
        self.on_observation = None
        self.on_ready = None
        self.last_error = None
        self._tracks = collections.OrderedDict()
        self._recent = collections.OrderedDict()
        self._jobs = queue.Queue(maxsize=4)
        self._after_jobs = []
        self._frame_buffer = collections.deque(maxlen=6)
        self._previous = None
        self._previous_map = None
        self._closed = threading.Event()
        self._worker = threading.Thread(target=self._write_loop, name="evidence-writer", daemon=True)
        self._worker.start()

    @staticmethod
    def usable_frame(frame):
        if frame is None or frame.ndim != 3 or min(frame.shape[:2]) < 200:
            return False
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        return (float(np.mean(gray < 12)) < 0.55 and float(np.mean(gray > 248)) < 0.70
                and float(np.std(gray)) > 5)

    @staticmethod
    def _matching_boxes(previous, current):
        for x, y, width, height in previous:
            for nx, ny, nw, nh in current:
                intersection = max(0, min(x+width, nx+nw)-max(x, nx))*max(0, min(y+height, ny+nh)-max(y, ny))
                if intersection/max(1, min(width*height, nw*nh)) >= 0.3:
                    return True
        return False

    @staticmethod
    def _ground_mask(frame):
        height, width = frame.shape[:2]
        mask = np.zeros((height, width), np.uint8)
        def rectangle(x1, y1, x2, y2, value):
            mask[round(y1*height/1080):round(y2*height/1080),
                 round(x1*width/1920):round(x2*width/1920)] = value
        rectangle(80, 130, 1840, 860, 255)
        for box in ((1660, 30, 1920, 290), (0, 750, 450, 1080),
                    (1500, 650, 1920, 1080), (400, 840, 1400, 1080), (850, 400, 1080, 720)):
            rectangle(*box, 0)
        return mask

    def _boxes(self, frame, kind):
        height, width = frame.shape[:2]
        ground = self._ground_mask(frame) > 0
        if kind == "black_void":
            pixels = (cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY) < 12) & ground
            minimum = 3500*width*height/(1920*1080)
        else:
            b, g, r = cv2.split(frame)
            pixels = (b > 180) & (g < 60) & (r > 180) & ground
            minimum = 1500*width*height/(1920*1080)
        kernel = max(3, int(9*width/1920) | 1)
        mask = cv2.morphologyEx(pixels.astype(np.uint8)*255, cv2.MORPH_OPEN, np.ones((kernel, kernel), np.uint8))
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        return [cv2.boundingRect(contour) for contour in contours if cv2.contourArea(contour) >= minimum]

    def _check_black_void(self, frame, min_area=3500):
        boxes = self._boxes(frame, "black_void")
        return bool(boxes), boxes

    def _check_missing_texture(self, frame, min_area=1500):
        boxes = self._boxes(frame, "missing_texture")
        return bool(boxes), boxes

    def inspect_frame_for_glitches(self, frame, map_name="Chưa rõ", coords_str="", context=None):
        context = context or {}
        if self.last_error:
            raise RuntimeError(f"Không lưu được bằng chứng: {self.last_error}")
        if (not self.usable_frame(frame) or context.get("map_dialog_open")
                or context.get("loading") or context.get("occluded") or context.get("defeated")):
            self._tracks.clear()
            return False, None

        # Lưu khung hình vào buffer xoay vòng phục vụ quay clip động
        self._frame_buffer.append(frame.copy())

        remaining = []
        for item in self._after_jobs:
            pending = item[0]
            before = item[1]
            detected = item[2]
            source_frame = item[3]
            buffer_frames = item[4] if len(item) > 4 else []
            if context.get("position_frame") != source_frame and not self._jobs.full():
                after = frame.copy() if context.get("map_id") == pending["map_id"] else None
                self._jobs.put_nowait((pending, before, detected, after, buffer_frames))
            else:
                remaining.append(item)
        self._after_jobs = remaining
        before_frame = self._previous if self._previous_map == context.get("map_id") else None
        self._previous, self._previous_map = frame, context.get("map_id")
        position = context.get("position")
        if position is None or context.get("position_frame") is None:
            return False, None
        now = time.monotonic()
        map_id = context.get("map_id", map_name)
        emitted = None
        for kind in ("black_void", "missing_texture"):
            boxes = self._boxes(frame, kind)
            key = (map_id, kind, round(position[0]/4), round(position[1]/4), context.get("game_build", "unknown"))
            if not boxes:
                self._tracks.pop(key, None)
                continue
            track = self._tracks.get(key)
            if track is None or now-track["last_seen"] > 4 or not self._matching_boxes(track.get("boxes", []), boxes):
                track = {"count": 0, "first": now, "last_seen": now, "frame": None,
                         "before": before_frame.copy() if before_frame is not None else None, "positions": [], "boxes": boxes}
                self._tracks[key] = track
            if track["frame"] == context["position_frame"]:
                continue
            track.update(frame=context["position_frame"], last_seen=now, count=track["count"]+1)
            track["boxes"] = boxes
            track["positions"].append(tuple(position))
            track["positions"] = track["positions"][-16:]
            if track["count"] < int(self.settings.get("confirm_frames", 3)) or now-track["first"] < float(self.settings.get("confirm_seconds", 1.5)):
                continue
            if now-self._recent.get(key, -1e9) < float(self.settings.get("dedup_seconds", 120)):
                continue
            if self._jobs.full() or len(self._after_jobs) >= 4:
                continue
            observed_views = max(math.dist(position, earlier) for earlier in track["positions"])
            # Automatic acceptance must be enabled only after labelled evaluation.
            confirmed = (kind == "missing_texture" and self.settings.get("auto_confirm_missing_texture", False)
                         and track["count"] >= 5 and observed_views >= 1.5)
            incident_id = uuid.uuid4().hex
            bug_key = hashlib.sha256(json.dumps(key, ensure_ascii=False).encode("utf-8")).hexdigest()

            # Đánh giá mức độ nghiêm trọng (Severity Classification)
            total_defect_area = sum(w * h for _, _, w, h in boxes)
            h_f, w_f = frame.shape[:2]
            norm_area = total_defect_area * (1920 * 1080) / max(1, w_f * h_f)
            if norm_area >= 12000:
                severity = "CRITICAL"
                severity_vi = "NGHIÊM TRỌNG"
            elif norm_area >= 3500 or kind == "missing_texture":
                severity = "MAJOR"
                severity_vi = "TRUNG BÌNH"
            else:
                severity = "MINOR"
                severity_vi = "NHẸ"

            incident = {"id": incident_id, "observation_id": incident_id, "bug_key": bug_key,
                        "timestamp": utc_now(), "map_id": map_id, "map_name": map_name,
                        "coord_x": round(position[0], 3), "coord_y": round(position[1], 3),
                        "coordinate_kind": "player_position", "coords": f"{position[0]:.3f},{position[1]:.3f}",
                        "glitch_type": "VÙNG ĐEN BẤT THƯỜNG" if kind == "black_void" else "NGHI THIẾU TEXTURE",
                        "kind": kind,
                        "severity": severity, "severity_vi": severity_vi,
                        "total_defect_area": round(norm_area, 1),
                        "description": f"{len(boxes)} vùng {kind} [{severity_vi}]; lặp trong {track['count']} mẫu vị trí mới.",
                        "status": "machine_confirmed" if confirmed else "suspected",
                        "confidence": "rule_confirmed" if confirmed else "needs_review",
                        "source_frame": context["position_frame"], "game_build": context.get("game_build", "unknown"),
                        "clean_image": incident_id+"_clean.png", "annotated_image": incident_id+"_annotated.png",
                        "before_image": incident_id+"_before.png", "after_image": incident_id+"_after.png",
                        "clip_gif": incident_id+"_clip.gif",
                        "boxes": boxes, "evidence_state": "pending"}
            if self.on_observation:
                self.on_observation(incident)
            buffer_snapshot = list(self._frame_buffer)
            self._after_jobs.append((incident, track["before"], frame.copy(), context["position_frame"], buffer_snapshot))
            self._recent[key] = now
            emitted = incident
        while len(self._tracks) > 8:
            self._tracks.popitem(last=False)
        while len(self._recent) > 512:
            self._recent.popitem(last=False)
        return bool(emitted), emitted

    def _save_png(self, filename, frame):
        path = os.path.join(self.evidence_dir, filename)
        temporary = path + ".next.png"
        if not cv2.imwrite(temporary, frame):
            raise OSError("Ghi ảnh PNG thất bại.")
        os.replace(temporary, path)

    def _save_gif(self, filename, frames, duration_ms=320):
        if not frames:
            return
        from PIL import Image
        path = os.path.join(self.evidence_dir, filename)
        temporary = path + ".next.gif"
        pil_images = []
        for f in frames:
            h, w = f.shape[:2]
            target_w = 640
            target_h = max(1, int(h * (target_w / w)))
            resized = cv2.resize(f, (target_w, target_h), interpolation=cv2.INTER_AREA)
            rgb = cv2.cvtColor(resized, cv2.COLOR_BGR2RGB)
            pil_images.append(Image.fromarray(rgb))
        if pil_images:
            pil_images[0].save(
                temporary,
                save_all=True,
                append_images=pil_images[1:],
                duration=duration_ms,
                loop=0
            )
            os.replace(temporary, path)

    def _write_loop(self):
        while not self._closed.is_set() or not self._jobs.empty():
            try:
                job_item = self._jobs.get(timeout=0.2)
            except queue.Empty:
                continue
            if len(job_item) == 5:
                incident, before, frame, after, buffer_frames = job_item
            else:
                incident, before, frame, after = job_item[:4]
                buffer_frames = []
            try:
                self._save_png(incident["clean_image"], frame)
                if before is not None:
                    self._save_png(incident["before_image"], before)
                else:
                    incident["before_image"] = ""
                if after is not None:
                    self._save_png(incident["after_image"], after)
                else:
                    incident["after_image"] = ""

                # Vẽ khoanh vùng lỗi neon nổi bật và HUD trên cùng
                annotated = frame.copy()
                for x, y, width, height in incident["boxes"]:
                    cv2.rectangle(annotated, (x, y), (x+width, y+height), (0, 0, 255), 3)
                    cv2.putText(annotated, f"BUG ({width}x{height})", (x, max(22, y - 6)),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 0, 255), 1)

                h_top = 38
                cv2.rectangle(annotated, (0, 0), (annotated.shape[1], h_top), (20, 20, 20), -1)
                sev = incident.get("severity", "MAJOR")
                sev_vi = incident.get("severity_vi", "TRUNG BÌNH")
                color = (0, 0, 255) if sev == "CRITICAL" else (0, 165, 255) if sev == "MAJOR" else (0, 220, 255)
                cv2.putText(annotated,
                            f"[{sev_vi}] {incident['kind']} | Map: {incident['map_name']} ({incident['map_id']}) | Pos: {incident['coords']}",
                            (16, 26), cv2.FONT_HERSHEY_SIMPLEX, 0.65, color, 2)
                self._save_png(incident["annotated_image"], annotated)

                # Quay clip GIF bằng chứng (Approach -> Highlight -> Aftermath)
                clip_frames = []
                if buffer_frames:
                    clip_frames.extend(buffer_frames[-4:])
                elif before is not None:
                    clip_frames.append(before)
                clip_frames.extend([annotated, annotated, annotated])
                if after is not None:
                    clip_frames.append(after)

                try:
                    self._save_gif(incident["clip_gif"], clip_frames, duration_ms=320)
                except Exception:
                    pass

                incident["evidence_state"] = "ready"
                if self.on_ready:
                    self.on_ready(incident)
            except Exception as exc:
                self.last_error = str(exc)
            finally:
                self._jobs.task_done()

    def close(self, timeout=3):
        for item in self._after_jobs:
            pending = item[0]
            before = item[1]
            detected = item[2]
            buffer_frames = item[4] if len(item) > 4 else []
            try:
                self._jobs.put((pending, before, detected, None, buffer_frames), timeout=timeout)
            except queue.Full:
                self.last_error = "Còn bằng chứng trong hàng chờ; metadata đã giữ trong SQLite."
                break
        self._after_jobs.clear()
        self._closed.set()
        self._worker.join(timeout)
