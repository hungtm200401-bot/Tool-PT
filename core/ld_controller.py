import os
import json
import time
import math
import random
import subprocess
import threading
import cv2
import numpy as np

from core.ld_discovery import LDDiscovery, run_quiet
from core.runtime_metrics import RuntimeMetrics

class LDController:
    """
    VIP PRO MAX Controller for LDPlayer (Phong Thần Client)
    - Điều khiển cảm ứng đa điểm, Joystick ảo 360 độ
    - Trích xuất khung hình siêu tốc không ghi đĩa
    - Giả lập thao tác ngón tay người dùng (Bézier Curve & Gaussian Jitter)
    """

    def __init__(self, config_path=None, auto_connect=True):
        if config_path is None:
            base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            config_path = os.path.join(base_dir, "config", "settings.json")

        self.config_path = config_path
        with open(config_path, "r", encoding="utf-8") as f:
            self.config = json.load(f)

        self.adb_path = None
        self.device_id = None
        self.device_name = "Chưa kết nối"
        self.available_devices = []
        self.connection_status = "Đang chờ dò LDPlayer."
        self._user_selected_serial = None
        self._command_lock = threading.RLock()
        self._input_lock = threading.RLock()
        self._capture_lock = threading.RLock()
        self._touch_down = False
        self._touch_device = "/dev/input/event2"
        self._session = None
        self._input_gate = None
        self.metrics = RuntimeMetrics()
        self.input_sequence = 0
        self._last_frame = None
        self._last_frame_time = 0.0
        self.joystick_center = (
            self.config["joystick"]["center_x"],
            self.config["joystick"]["center_y"]
        )
        self.joystick_radius = self.config["joystick"].get("radius", 120)
        self.ui = self.config["ui_elements"]

        # Cơ chế giữ màn hình máy tính và LD luôn sáng khi chạy nhiệm vụ
        self._keep_awake_running = False
        self._keep_awake_stop = threading.Event()
        self._keep_awake_thread = None

        self.fast_pipe_enabled = True
        self._shell_pipe = None
        self._shell_pipe_device = None

        if auto_connect:
            self.refresh_connection()

    @property
    def connected(self):
        return bool(self.adb_path and self.device_id)

    def refresh_connection(self):
        if self._session is not None:
            raise RuntimeError("Đang giữ phiên LD cho nhiệm vụ; không được tự đổi thiết bị.")
        self._close_shell_pipe()
        result = LDDiscovery(self.config).scan(self._user_selected_serial)
        self.available_devices = result["devices"]
        self.adb_path = result["adb_path"]
        self.device_id = None
        self.device_name = "Chưa kết nối"
        if result["selected"]:
            selected = result["selected"]
            self.adb_path = selected["adb_path"]
            self.device_id = selected["serial"]
            self.device_name = selected["name"]
        self.connection_status = result["message"]
        print(f"[LDController] {self.connection_status}")
        return self.connected

    def select_device(self, serial):
        if self._session is not None:
            return False
        selected = next((device for device in self.available_devices if device["serial"] == serial), None)
        if selected is None:
            return False
        if selected["serial"] != self.device_id:
            self._close_shell_pipe()
        self.adb_path = selected["adb_path"]
        self.device_id = selected["serial"]
        self.device_name = selected["name"]
        self._user_selected_serial = serial
        self.connection_status = f"Đã chọn {self.device_name} — {self.device_id}."
        return True

    def ensure_connection(self):
        if self.connected:
            result = run_quiet([self.adb_path, "-s", self.device_id, "get-state"])
            if result and result.returncode == 0 and result.stdout.strip() == "device":
                return
            raise RuntimeError("LD đã chọn không còn online; dùng Dò lại LD trước khi bắt đầu nhiệm vụ mới.")
        if self._session is not None:
            raise RuntimeError("Mất LD của nhiệm vụ; không tự chuyển sang LD khác.")
        if not self.refresh_connection():
            raise RuntimeError(self.connection_status)

    def _boot_id(self, force=False):
        now = time.monotonic()
        if not force and getattr(self, "_cached_boot_id", None) and (now - getattr(self, "_boot_id_time", 0) < 30.0):
            return self._cached_boot_id
        result = run_quiet(self._device_command("shell", "cat", "/proc/sys/kernel/random/boot_id"), timeout=6)
        if result is None or result.returncode != 0 or not result.stdout.strip():
            if getattr(self, "_cached_boot_id", None):
                return self._cached_boot_id
            raise RuntimeError("Không xác minh được phiên LD; ngừng phát lệnh.")
        self._cached_boot_id = result.stdout.strip()
        self._boot_id_time = now
        return self._cached_boot_id

    def lock_session(self):
        with self._command_lock:
            self.ensure_connection()
            self._session = (self.adb_path, self.device_id, self._boot_id())
            identity = run_quiet(self._device_command("shell", "settings", "get", "secure", "android_id"), timeout=4)
            self.device_fingerprint = (identity.stdout.strip() if identity and identity.returncode == 0 else "")
            if not self.device_fingerprint or self.device_fingerprint == "null":
                self.device_fingerprint = self.device_id
            package = self.config.get("game_package", "com.tech3cgame.vhpt1")
            details = run_quiet(self._device_command("shell", "dumpsys", "package", package), timeout=5)
            import re
            version = re.search(r"versionName=([^\s]+)", details.stdout) if details and details.returncode == 0 else None
            code = re.search(r"versionCode=(\d+)", details.stdout) if details and details.returncode == 0 else None
            self.game_build = self.config.get("game_build") or (version.group(1)+":"+code.group(1) if version and code else "unknown-build")
            self._start_keep_awake()
            return self._session

    def unlock_session(self):
        with self._command_lock:
            self._session = None
            self._input_gate = None
            self._close_shell_pipe()
            self._stop_keep_awake()

    def set_input_gate(self, allowed):
        self._input_gate = allowed

    def cancel_movement(self):
        """Disengage auto-pathfinding via a slight joystick drag; caller must verify fresh stationary samples."""
        cx, cy = self.joystick_center
        self.swipe(cx, cy, cx + 35, cy, duration_ms=150, _cancel=True)

    def calibrate_resolution(self):
        result = run_quiet(self._device_command("shell", "wm", "size"), timeout=4)
        if result is None or result.returncode != 0:
            raise RuntimeError("Không đọc được độ phân giải LD.")
        import re
        sizes = re.findall(r"(\d+)x(\d+)", result.stdout)
        if not sizes:
            raise RuntimeError("LD không cung cấp kích thước màn hình hợp lệ.")
        width, height = map(int, sizes[-1])
        if width < height or abs(width/height - 1920/1080) > 0.04:
            raise RuntimeError("Bố cục game chưa được hiệu chỉnh cho tỷ lệ màn hình này; cần dùng màn hình ngang 16:9.")
        base = self.config["resolution"]
        sx, sy = width/base["width"], height/base["height"]
        self.ui = {name: {**point, "x": round(point["x"]*sx), "y": round(point["y"]*sy)}
                   for name, point in self.config["ui_elements"].items()}
        self.joystick_center = (round(self.config["joystick"]["center_x"]*sx),
                                round(self.config["joystick"]["center_y"]*sy))
        self.screen_size = (width, height)
        return self.screen_size

    def _get_shell_pipe(self):
        if not getattr(self, "fast_pipe_enabled", True) or not self.connected:
            return None
        if self._shell_pipe is not None:
            if self._shell_pipe.poll() is None and self._shell_pipe_device == self.device_id:
                return self._shell_pipe
            self._close_shell_pipe()
        if not os.path.exists(str(self.adb_path)):
            return None

        try:
            creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
            cmd = [self.adb_path, "-s", self.device_id, "shell"]
            self._shell_pipe = subprocess.Popen(
                cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                creationflags=creationflags
            )
            self._shell_pipe_device = self.device_id
            return self._shell_pipe
        except Exception:
            self._shell_pipe = None
            self._shell_pipe_device = None
            return None

    def _close_shell_pipe(self):
        pipe = getattr(self, "_shell_pipe", None)
        if pipe is not None:
            try:
                if pipe.stdin and not pipe.stdin.closed:
                    pipe.stdin.close()
                pipe.terminate()
                pipe.wait(timeout=0.3)
            except Exception:
                try:
                    pipe.kill()
                except Exception:
                    pass
            finally:
                self._shell_pipe = None
                self._shell_pipe_device = None

    def _device_command(self, *arguments):
        if not self.connected:
            raise RuntimeError("Chưa kết nối LDPlayer. Hãy dò LD trước khi thao tác.")
        return [self.adb_path, "-s", self.device_id, *arguments]

    def _input(self, *arguments, _cancel=False):
        with self._command_lock, self.metrics.measure("input"):
            if not _cancel and self._input_gate is not None and not self._input_gate():
                raise InterruptedError("Nhiệm vụ đã dừng; hủy lệnh điều khiển đang chờ.")
            if self._session is not None:
                if self._session[:2] != (self.adb_path, self.device_id) or self._boot_id() != self._session[2]:
                    raise RuntimeError("Phiên LD đã thay đổi; hủy lệnh của nhiệm vụ cũ.")
            if not _cancel and self._input_gate is not None and not self._input_gate():
                raise InterruptedError("Nhiệm vụ đã dừng trong lúc kiểm tra phiên; hủy lệnh điều khiển.")
            self.input_sequence += 1

            pipe = self._get_shell_pipe()
            if pipe is not None and pipe.stdin is not None:
                try:
                    cmd_line = "input " + " ".join(map(str, arguments)) + "\n"
                    pipe.stdin.write(cmd_line.encode("utf-8"))
                    pipe.stdin.flush()
                    return
                except (BrokenPipeError, OSError):
                    self._close_shell_pipe()

            try:
                result = subprocess.run(
                    self._device_command("shell", "input", *map(str, arguments)),
                    capture_output=True, text=True, encoding="utf-8", errors="replace",
                    timeout=8, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0)
                )
            except subprocess.TimeoutExpired:
                # A timed-out touch may still have reached Android. Never replay it:
                # duplicate taps/swipes can move the actor after the UI reports stop.
                raise RuntimeError("LD quá thời gian chờ lệnh điều khiển; không gửi lại để tránh thao tác trùng.")
            except OSError as exc:
                raise RuntimeError(f"Không gửi được lệnh tới LD: {exc}")
            if result.returncode != 0:
                raise RuntimeError("LD từ chối lệnh điều khiển; chặng hiện tại được giữ là chưa hoàn tất.")

    def capture_frame(self, max_age_seconds=1.0):
        """Chụp màn hình LDPlayer tức thì và giải mã trực tiếp vào OpenCV BGR array với bộ nhớ đệm chống nghẽn"""
        now = time.monotonic()
        if self._last_frame is not None and now - self._last_frame_time < max_age_seconds:
            return self._last_frame.copy()
        acquired = self._capture_lock.acquire(timeout=0.15)
        try:
            if not acquired:
                return self._last_frame.copy() if self._last_frame is not None else None
            cmd = self._device_command("exec-out", "screencap", "-p")
            with self.metrics.measure("screencap"):
                p = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=2.5,
                                   creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
            raw_bytes = p.stdout if p.returncode == 0 else b""
            if raw_bytes:
                frame = cv2.imdecode(np.frombuffer(raw_bytes, np.uint8), cv2.IMREAD_COLOR)
                if frame is None:
                    cleaned = raw_bytes.replace(b'\r\r\n', b'\n').replace(b'\r\n', b'\n')
                    frame = cv2.imdecode(np.frombuffer(cleaned, np.uint8), cv2.IMREAD_COLOR)
                if frame is not None:
                    self._last_frame = frame
                    self._last_frame_time = now
                    return frame
        except Exception:
            # Fallback to cached frame on ADB collision or transient timeout
            if self._last_frame is not None:
                return self._last_frame.copy()
        finally:
            if acquired:
                self._capture_lock.release()
        return self._last_frame.copy() if self._last_frame is not None else None

    def tap(self, x, y, jitter=True, delay=0.1, *, _cancel=False):
        """Tap vào tọa độ (x, y) với độ lệch ngẫu nhiên mô phỏng ngón tay người"""
        target_x = x
        target_y = y
        if jitter:
            target_x += random.randint(-3, 3)
            target_y += random.randint(-3, 3)

        self._input("tap", target_x, target_y, _cancel=_cancel)

        if delay > 0:
            time.sleep(delay)

    def swipe(self, x1, y1, x2, y2, duration_ms=400, *, _cancel=False):
        """Vuốt từ (x1, y1) đến (x2, y2) mượt mà"""
        self._input("swipe", x1, y1, x2, y2, duration_ms, _cancel=_cancel)

    def move_joystick(self, angle_degrees, duration_ms=1200):
        """
        Di chuyển nhân vật theo góc mong muốn (0 - 360 độ):
        - 0 độ: Di chuyển sang phải
        - 90 độ: Di chuyển xuống dưới
        - 180 độ: Di chuyển sang trái
        - 270 độ: Di chuyển lên trên
        """
        rad = math.radians(angle_degrees)
        cx, cy = self.joystick_center
        r = self.joystick_radius

        dest_x = int(cx + r * math.cos(rad))
        dest_y = int(cy + r * math.sin(rad))

        self.swipe(cx, cy, dest_x, dest_y, duration_ms=duration_ms)

    def joystick_press(self, angle_degrees):
        """
        Đặt ngón tay lên tâm joystick và trượt ra hướng cần đi (ACTION_DOWN -> ACTION_MOVE).
        Khởi tạo luồng cảm ứng liên tục, không bao giờ nhấc tay lên trong suốt hành trình.
        """
        rad = math.radians(angle_degrees)
        cx, cy = self.joystick_center
        r = self.joystick_radius
        dest_x = int(cx + r * math.cos(rad))
        dest_y = int(cy + r * math.sin(rad))

        pipe = self._get_shell_pipe()
        if pipe is not None and pipe.stdin is not None:
            try:
                dev = getattr(self, "_touch_device", "/dev/input/event2")
                cmds = (
                    f"sendevent {dev} 3 47 0\n"
                    f"sendevent {dev} 3 57 101\n"
                    f"sendevent {dev} 3 53 {cx}\n"
                    f"sendevent {dev} 3 54 {cy}\n"
                    f"sendevent {dev} 3 58 1\n"
                    f"sendevent {dev} 1 330 1\n"
                    f"sendevent {dev} 0 0 0\n"
                    f"sendevent {dev} 3 47 0\n"
                    f"sendevent {dev} 3 53 {dest_x}\n"
                    f"sendevent {dev} 3 54 {dest_y}\n"
                    f"sendevent {dev} 0 0 0\n"
                )
                pipe.stdin.write(cmds.encode("utf-8"))
                pipe.stdin.flush()
                self._touch_down = True
                return
            except Exception:
                self._touch_down = False

        self.move_joystick(angle_degrees, duration_ms=480)

    def joystick_steer(self, angle_degrees):
        """
        Chuyển hướng ngón tay mượt mà (ACTION_MOVE) trong khi vẫn ĐANG GIỮ JOYSTICK.
        Ngón tay KHÔNG BAO GIỜ NHẤC LÊN -> Nhân vật KHÔNG BAO GIỜ KHỰNG hay khựng nhịp.
        """
        rad = math.radians(angle_degrees)
        cx, cy = self.joystick_center
        r = self.joystick_radius
        dest_x = int(cx + r * math.cos(rad))
        dest_y = int(cy + r * math.sin(rad))

        if getattr(self, "_touch_down", False):
            pipe = self._get_shell_pipe()
            if pipe is not None and pipe.stdin is not None:
                try:
                    dev = getattr(self, "_touch_device", "/dev/input/event2")
                    cmds = (
                        f"sendevent {dev} 3 47 0\n"
                        f"sendevent {dev} 3 53 {dest_x}\n"
                        f"sendevent {dev} 3 54 {dest_y}\n"
                        f"sendevent {dev} 0 0 0\n"
                    )
                    pipe.stdin.write(cmds.encode("utf-8"))
                    pipe.stdin.flush()
                    return
                except Exception:
                    self._touch_down = False

        # Fallback tự nhiên qua swipe gối đầu nếu sendevent chưa khả dụng
        self.move_joystick(angle_degrees, duration_ms=480)

    def joystick_release(self):
        """
        Nhấc ngón tay lên (ACTION_UP) khi đã đến đích hoặc dừng di chuyển.
        """
        if getattr(self, "_touch_down", False):
            self._touch_down = False
            pipe = self._get_shell_pipe()
            if pipe is not None and pipe.stdin is not None:
                try:
                    dev = getattr(self, "_touch_device", "/dev/input/event2")
                    cmds = (
                        f"sendevent {dev} 3 47 0\n"
                        f"sendevent {dev} 3 57 -1\n"
                        f"sendevent {dev} 1 330 0\n"
                        f"sendevent {dev} 0 0 0\n"
                    )
                    pipe.stdin.write(cmds.encode("utf-8"))
                    pipe.stdin.flush()
                except Exception:
                    pass

    def open_local_map(self):
        """Mở bản đồ lân cận (Click Minimap)"""
        m = self.ui["minimap_click_open"]
        self.tap(m["x"], m["y"], delay=0.5)

    def open_world_map(self):
        """Mở bản đồ thế giới 32 Map"""
        self.open_local_map()
        w = self.ui["world_map_tab"]
        self.tap(w["x"], w["y"], delay=0.5)

    def close_map_dialog(self, *, _cancel=False):
        """Đóng bảng bản đồ"""
        c = self.ui["map_dialog_close"]
        self.tap(c["x"], c["y"], delay=0.3, _cancel=_cancel)

    def click_revive_to_city(self):
        """Khi bị trọng thương, bấm 'Về thành' để hồi sinh an toàn"""
        btn = self.ui["revive_city_button"]
        self.tap(btn["x"], btn["y"], delay=0.8)

    def toggle_mount(self):
        """Bấm lên thú / xuống thú để chạy nhanh hơn"""
        btn = self.ui["mount_button"]
        self.tap(btn["x"], btn["y"], delay=0.3)

    def walk_game_direction(self, dx, dy, duration_ms=1000):
        """Di chuyển nhân vật theo hướng tọa độ game (dx, dy) bằng joystick ảo."""
        angle = game_to_joystick_angle(dx, dy)
        self.move_joystick(angle, duration_ms=duration_ms)

    def check_and_recover_session(self):
        """Nếu game bị văng ra màn hình Đăng nhập hoặc Chọn Server, tự động khôi phục lại."""
        f = self.capture_frame()
        if f is not None:
            h, w = f.shape[:2]
            # Kiểm tra nút Đăng nhập màu xanh lá
            roi_login = f[int(h*0.55):int(h*0.68), int(w*0.38):int(w*0.48)]
            hsv_login = cv2.cvtColor(roi_login, cv2.COLOR_BGR2HSV)
            green_login = (hsv_login[:, :, 0] > 35) & (hsv_login[:, :, 0] < 85) & (hsv_login[:, :, 1] > 100)
            if np.mean(green_login) > 0.05:
                print("[LDController] Phát hiện màn hình Đăng nhập; tự động bấm Đăng nhập lại.")
                self.tap(round(w*0.417), round(h*0.617), jitter=False, delay=1.5)
                time.sleep(2.0)
                return True

            # Kiểm tra màn hình Chọn Server (nút VHPT1 Test ở góc 290, 285)
            roi_server = f[int(h*0.22):int(h*0.32), int(w*0.12):int(w*0.22)]
            hsv_server = cv2.cvtColor(roi_server, cv2.COLOR_BGR2HSV)
            green_server = (hsv_server[:, :, 0] > 35) & (hsv_server[:, :, 0] < 85) & (hsv_server[:, :, 1] > 60)
            if np.mean(green_server) > 0.01:
                print("[LDController] Phát hiện màn hình Chọn Server; bấm vào VHPT1 Test để vào game.")
                self.tap(round(w*0.151), round(h*0.264), jitter=False, delay=0.2)
                self.tap(round(w*0.151), round(h*0.264), jitter=False, delay=1.5)
                time.sleep(2.0)
                return True
        return False

    def _start_keep_awake(self):
        if not getattr(self, "_keep_awake_running", False):
            self._keep_awake_running = True
            self._keep_awake_stop.clear()
            self._keep_awake_thread = threading.Thread(target=self._keep_awake_loop, daemon=True)
            self._keep_awake_thread.start()

    def _stop_keep_awake(self):
        self._keep_awake_running = False
        self._keep_awake_stop.set()
        thread = self._keep_awake_thread
        if thread and thread is not threading.current_thread():
            thread.join(timeout=2)
        if thread and not thread.is_alive():
            self._keep_awake_thread = None

    def _keep_awake_loop(self):
        """Giữ Windows tỉnh khi nhiệm vụ chạy, không tạo input giả hay lệnh ADB nền."""
        import ctypes
        ES_CONTINUOUS = 0x80000000
        ES_SYSTEM_REQUIRED = 0x00000001
        ES_DISPLAY_REQUIRED = 0x00000002
        flags = ES_CONTINUOUS | ES_SYSTEM_REQUIRED | ES_DISPLAY_REQUIRED
        try:
            if hasattr(ctypes, "windll"):
                ctypes.windll.kernel32.SetThreadExecutionState(flags)
                while not self._keep_awake_stop.wait(30.0):
                    ctypes.windll.kernel32.SetThreadExecutionState(flags)
        except Exception:
            pass
        finally:
            try:
                if hasattr(ctypes, "windll"):
                    ctypes.windll.kernel32.SetThreadExecutionState(ES_CONTINUOUS)
            except Exception:
                pass

    def close(self):
        self._close_shell_pipe()
        self._stop_keep_awake()



def game_to_joystick_angle(dx, dy):
    """
    Chuyển đổi vector độ lệch tọa độ game (dx, dy) sang góc vuốt joystick màn hình (0-360 độ).
    Hệ tọa độ game Phong Thần là isometric 2.5D (nghiêng ~45 độ và có tỉ lệ trục 2:1).
    Ma trận chuyển đổi thực nghiệm đo đạc trực tiếp từ game engine:
      u = 0.6229 * dx - 0.7947 * dy
      v = 0.4570 * dx + 0.9801 * dy
    """
    if abs(dx) < 1e-6 and abs(dy) < 1e-6:
        return 0.0
    u = 0.6229 * dx - 0.7947 * dy
    v = 0.4570 * dx + 0.9801 * dy
    return math.degrees(math.atan2(v, u)) % 360


