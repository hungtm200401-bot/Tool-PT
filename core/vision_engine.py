import cv2
import numpy as np
import threading
import time

class VisionEngine:
    """
    VIP PRO MAX Vision & State Detector for Phong Thần Client
    """

    def __init__(self, adb_path=None, device_id=None, controller=None):
        # Coordinates for 1920x1080
        self.minimap_roi = (1670, 30, 1910, 280)
        self.coord_roi = (1720, 70, 1850, 105)
        self.map_title_roi = (1680, 40, 1850, 75)
        self.dead_popup_roi = (300, 860, 360, 1060) # y1, x1, y2, x2
        self.revive_btn_roi = (590, 650, 640, 770)  # "Về thành" button
        if hasattr(adb_path, "adb_path") and controller is None:
            controller = adb_path
            adb_path = controller.adb_path
            device_id = controller.device_id
        self.adb_path = adb_path
        self.device_id = device_id
        self.controller = controller
        self._source_frames = {}
        self._source_changed = {}
        self._source_device = None
        self._cached_telemetry = None
        self._last_telemetry_time = 0.0
        self._telemetry_lock = threading.Lock()
        self._bg_telemetry_running = False
        self._bg_telemetry_thread = None

    def start_background_telemetry(self, poll_interval=0.06):
        with self._telemetry_lock:
            if self._bg_telemetry_running:
                return
            self._bg_telemetry_running = True
            self._bg_telemetry_thread = threading.Thread(
                target=self._telemetry_poll_worker,
                args=(poll_interval,),
                name="telemetry-poll-worker",
                daemon=True
            )
            self._bg_telemetry_thread.start()

    def stop_background_telemetry(self):
        with self._telemetry_lock:
            self._bg_telemetry_running = False

    def _telemetry_poll_worker(self, poll_interval=0.06):
        while getattr(self, "_bg_telemetry_running", False):
            try:
                self._fetch_engine_telemetry_sync()
            except Exception:
                pass
            time.sleep(poll_interval)

    def get_engine_telemetry(self):
        """
        Đọc trực tiếp dữ liệu telemetry thời gian thực từ engine Cocos2dx / Phong Thần:
        - Tên Map, Tọa độ X-Y, Subworld ID
        - Trạng thái nhân vật: 'stand', 'run', 'walk', 'attack'
        - Trạng thái cửa sổ: đang mở bản đồ hay đang trong trận
        """
        now_req = time.monotonic()
        if self.controller is not None:
            self.adb_path = self.controller.adb_path
            self.device_id = self.controller.device_id
        device = (self.adb_path, self.device_id)
        with self._telemetry_lock:
            if device != self._source_device:
                self._source_device = device
                self._source_frames.clear()
                self._source_changed.clear()
                self._cached_telemetry = None
            max_age = 0.08 if self._bg_telemetry_running else 0.12
            if self._cached_telemetry is not None and (now_req - self._last_telemetry_time < max_age):
                return dict(self._cached_telemetry)

        return self._fetch_engine_telemetry_sync()

    def _fetch_engine_telemetry_sync(self):
        started = time.monotonic()
        import subprocess
        import json
        telemetry = {
            "map_name": "",
            "coords": "",
            "map_id": 0,
            "doing": "unknown",
            "doing_valid": False,
            "position": None,
            "position_frame": None,
            "map_frame": None,
            "auto_move": None,
            "map_data": {},
            "in_game": False,
            "received_at": time.monotonic(),
            "map_dialog_open": False
        }
        if self.controller is not None:
            self.adb_path = self.controller.adb_path
            self.device_id = self.controller.device_id
            telemetry["game_build"] = getattr(self.controller, "game_build", "unknown-build")
        if not self.adb_path or not self.device_id:
            return telemetry
        source_ages = {}

        def read_status(filename):
            path = "/sdcard/Android/data/com.tech3cgame.vhpt1/files/" + filename
            script = f"date +%s; stat -c %Y {path}; cat {path}"
            cmd = [self.adb_path, "-s", self.device_id, "shell", script]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=1.5,
                                    creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
            raw = (result.stdout if result else "").strip()
            # Nếu lệnh shell thường bị từ chối quyền hoặc lỗi, fallback sang su 0
            if (hasattr(result, "returncode") and result.returncode != 0) or (not raw and hasattr(result, "stderr") and result.stderr):
                cmd_su = [self.adb_path, "-s", self.device_id, "shell", "su", "0", "sh", "-c", f"'{script}'"]
                res_su = subprocess.run(cmd_su, capture_output=True, text=True, timeout=1.5,
                                        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
                if res_su and res_su.stdout:
                    raw = res_su.stdout.strip()
            lines = raw.split("\n", 2)
            age = None
            if len(lines) == 3 and lines[0].strip().isdigit() and lines[1].strip().isdigit():
                delta = int(lines[0].strip()) - int(lines[1].strip())
                age = float(max(0, delta)) if delta >= -2 else 3600.0
                raw = lines[2]
            return json.loads(raw), age

        try:
            data, source_ages["map"] = read_status("map-render-status.json")
            if data:
                telemetry["map_data"] = data
                telemetry["map_frame"] = data.get("frames")
                telemetry["auto_move"] = data.get("auto_move")
                mini = data.get("mini", {})
                telemetry["map_name"] = mini.get("name", "").strip()
                telemetry["coords"] = mini.get("pos", "").strip()
                telemetry["map_id"] = data.get("world", {}).get("player_map", 0)
                telemetry["map_dialog_open"] = bool(
                    data.get("world", {}).get("up") or data.get("nodes", {}).get("map", 0)
                )
        except Exception:
            pass

        try:
            data_pos, source_ages["position"] = read_status("pos-trace-status.json")
            if data_pos:
                player = data_pos.get("player", {})
                telemetry["position_frame"] = data_pos.get("frames")
                mps = player.get("mps")
                if isinstance(mps, list) and len(mps) == 2:
                    telemetry["position"] = (float(mps[0])/256, float(mps[1])/512)
                if "doing" in player:
                    telemetry["doing"] = str(player["doing"]).strip().lower()
                    telemetry["doing_valid"] = bool(telemetry["doing"])
                if not telemetry["map_id"]:
                    telemetry["map_id"] = data_pos.get("sub_world_id", 0)
                telemetry["position_map_id"] = data_pos.get("sub_world_id", 0)
                telemetry["player_identity"] = player.get("id") or player.get("name")
        except Exception:
            pass

        now = time.monotonic()
        for source in ("position", "map"):
            frame_number = telemetry.get(source+"_frame")
            if frame_number is not None and frame_number != self._source_frames.get(source):
                if source in self._source_frames:
                    self._source_changed[source] = now
                self._source_frames[source] = frame_number
            telemetry[source+"_age"] = (source_ages[source] if source_ages.get(source) is not None
                                        else now-self._source_changed.get(source, now-3600))
        telemetry["in_game"] = bool(telemetry.get("position_map_id") and telemetry["position"]
                                    and telemetry["doing_valid"] and telemetry["position_age"] < 15)
        with self._telemetry_lock:
            self._cached_telemetry = dict(telemetry)
            self._last_telemetry_time = now
        if self.controller is not None and hasattr(self.controller, "metrics"):
            self.controller.metrics.record("telemetry", time.monotonic()-started)
        return telemetry

    def is_defeated(self, frame):
        """Kiểm tra xem nhân vật có đang bị Trọng thương hay không"""
        if frame is None:
            return False
        y1, x1, y2, x2 = self.revive_btn_roi
        height, width = frame.shape[:2]
        crop = frame[round(y1*height/1080):round(y2*height/1080),
                     round(x1*width/1920):round(x2*width/1920)]
        if crop.size == 0:
            return False
        # Map terrain is also warm yellow/brown. Mean-color checks therefore
        # mistake sand for the revive button and can trigger unwanted taps.
        # Require a connected, saturated, button-shaped gold region instead.
        hsv = cv2.cvtColor(crop, cv2.COLOR_BGR2HSV)
        gold = cv2.inRange(hsv, np.array([10, 110, 130], dtype=np.uint8),
                           np.array([45, 255, 255], dtype=np.uint8))
        gold = cv2.morphologyEx(gold, cv2.MORPH_CLOSE, np.ones((3, 3), dtype=np.uint8))
        count, _, stats, _ = cv2.connectedComponentsWithStats(gold, connectivity=8)
        for index in range(1, count):
            _, _, blob_width, blob_height, area = stats[index]
            aspect = blob_width / max(1, blob_height)
            fill = area / max(1, blob_width * blob_height)
            if (area >= 180 and blob_width >= 28 and blob_height >= 8
                    and 1.8 <= aspect <= 12 and fill >= 0.2):
                return True
        return False

    def is_map_dialog_open(self, frame):
        """Kiểm tra xem bảng bản đồ lớn có đang mở hay không"""
        if frame is None:
            return False
        # Look for the green 'Bản đồ lân cận' tab at x: 80-180, y: 120-160
        tab_crop = frame[120:160, 80:180]
        mean_bgr = cv2.mean(tab_crop)[:3]
        b, g, r = mean_bgr
        # Tab has dark greenish-gold theme
        if g > 60 and g > b + 15:
            return True
        return False

    def get_minimap(self, frame):
        """Crop khu vực bản đồ con góc trên bên phải"""
        if frame is None:
            return None
        x1, y1, x2, y2 = self.minimap_roi
        return frame[y1:y2, x1:x2]

    def get_coordinate_crop(self, frame):
        """Crop vùng hiển thị tọa độ X, Y trên bản đồ nhỏ"""
        if frame is None:
            return None
        x1, y1, x2, y2 = self.coord_roi
        crop = frame[y1:y2, x1:x2]
        gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
        _, thresh = cv2.threshold(gray, 220, 255, cv2.THRESH_BINARY)
        return crop, thresh

    def compute_optical_flow_magnitude(self, prev_frame, curr_frame):
        """
        Đo lường mức độ dịch chuyển thực sự của khung cảnh nền thế giới.
        Loại trừ khu vực nhân vật ở tâm và UI rìa màn hình.
        """
        if prev_frame is None or curr_frame is None:
            return 0.0

        # Crop ground region (excluding HUD, minimap, chatbox, character center)
        # Background landscape sample: y: 400 to 700, x: 1100 to 1600
        roi_prev = prev_frame[400:700, 1100:1600]
        roi_curr = curr_frame[400:700, 1100:1600]

        gray1 = cv2.cvtColor(roi_prev, cv2.COLOR_BGR2GRAY)
        gray2 = cv2.cvtColor(roi_curr, cv2.COLOR_BGR2GRAY)

        flow = cv2.calcOpticalFlowFarneback(
            gray1, gray2, None,
            pyr_scale=0.5, levels=3, winsize=15,
            iterations=3, poly_n=5, poly_sigma=1.2, flags=0
        )

        mag, _ = cv2.cartToPolar(flow[..., 0], flow[..., 1])
        avg_mag = float(np.mean(mag))
        return avg_mag
