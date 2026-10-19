import os
import sys
import webbrowser
import threading
import queue
import json
import tkinter as tk
from PIL import Image
from pathlib import Path
import customtkinter as ctk

# Ensure core and reports can be imported
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.ld_controller import LDController
from core.vision_engine import VisionEngine
from core.glitch_detector import GlitchDetector
from core.obstacle_bypasser import ObstacleBypasser
from core.google_sheet_sync import GoogleSheetSync
from core.map_traversal_engine import MapTraversalEngine
from core.html_reporter import HTMLReporter
from core.coverage_planner import atomic_json

GOOGLE_SHEET_URL = "https://docs.google.com/spreadsheets/d/1AvRcllKqX03WwwrE508vhJBnnWBUx2_hgpU8gHwZoqY/edit?gid=0#gid=0"

class AppGUI(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("PHONG THẦN — Khảo sát vòng mở rộng")
        screen_width = self.winfo_screenwidth()
        screen_height = self.winfo_screenheight()
        window_width = max(900, min(1720, screen_width-40))
        window_height = max(700, min(1024, screen_height-80))
        x = max(0, (screen_width-window_width)//2)
        y = max(0, (screen_height-window_height-48)//2)
        self.geometry(f"{window_width}x{window_height}+{x}+{y}")
        self.minsize(min(1120, window_width), min(780, window_height))
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")

        # Initialize core components
        self.ctrl = LDController(auto_connect=False)
        self.vision = VisionEngine(controller=self.ctrl)
        self.detector = GlitchDetector(settings=self.ctrl.config.get("detection", {}))
        self.bypasser = ObstacleBypasser(self.ctrl)
        self.sheet_sync = GoogleSheetSync()
        self.engine = MapTraversalEngine(
            self.ctrl, self.vision, self.detector, self.bypasser, self.sheet_sync
        )
        self.reporter = HTMLReporter(store=self.sheet_sync.store)
        self._detecting_ld = False
        self._device_options = {}
        self._ld_retry_id = None
        self._ld_unlock_id = None
        self._closing = False
        self._ui_queue = queue.Queue(maxsize=256)
        self._shutdown_thread = None
        self._current_map_preview = None
        self._map_viewer = None
        self._map_viewer_image = None
        self._map_viewer_status = None
        self._map_viewer_photo = None
        self._map_viewer_resize_id = None
        self._sheet_polling = False
        self._last_connection_message = None
        self._game_ready = False
        self._game_polling = False
        self._route_resize_id = None
        self._empty_preview_image = ctk.CTkImage(
            light_image=Image.new("RGB", (2, 2), "#21262d"), size=(1, 1))

        # Connect callbacks
        self.engine.cb_status = self.update_status
        self.engine.cb_glitch_alert = self.on_glitch_alert
        self.engine.cb_progress = self.update_progress
        self.engine.cb_route_progress = self.update_route_progress

        self._build_ui()
        self.sheet_sync.start()
        self.protocol("WM_DELETE_WINDOW", self._close_app)
        self.bind("<F8>", lambda _e: self.action_reset_map())
        self.bind("<F9>", lambda _e: self.action_start())
        self.bind("<F10>", lambda _e: self.action_pause())
        self.bind("<F11>", lambda _e: self.action_stop())
        self._start_global_hotkeys()
        self.after(100, self.action_detect_ld)
        self.after(80, self._drain_ui)
        self.after(1500, self._poll_sheet)
        self.after(5000, self._poll_runtime_metrics)
        self.after(1000, self._poll_game_state)

    def _build_ui(self):
        # Header Frame
        header = ctk.CTkFrame(self, fg_color="#161b22", corner_radius=10)
        header.pack(fill="x", padx=16, pady=12)

        title_lbl = ctk.CTkLabel(
            header,
            text="PHONG THẦN · KHẢO SÁT VÒNG MỞ RỘNG VÀ GHI NHẬN BẤT THƯỜNG",
            font=ctk.CTkFont(size=19, weight="bold"),
            text_color="#d29922"
        )
        title_lbl.pack(anchor="w", padx=16, pady=(12, 4))

        self.lbl_device_summary = ctk.CTkLabel(
            header,
            text="Tự tìm LDPlayer trên máy | Hỗ trợ màn hình game 1920x1080 | Tự lập tuyến và ghi nhận lỗi",
            font=ctk.CTkFont(size=12),
            text_color="#8b949e"
        )
        self.lbl_device_summary.pack(anchor="w", padx=16, pady=(0, 5))

        connection_row = ctk.CTkFrame(header, fg_color="transparent")
        connection_row.pack(fill="x", padx=16, pady=(0, 4))
        self.ld_selector = ctk.CTkOptionMenu(
            connection_row, values=["Đang dò LDPlayer…"], width=390,
            state="disabled", command=self.action_select_ld
        )
        self.ld_selector.pack(side="left", padx=(0, 8))
        self.btn_detect_ld = ctk.CTkButton(
            connection_row, text="Dò lại LD", width=105, command=self.action_detect_ld
        )
        self.btn_detect_ld.pack(side="left")
        self.lbl_game_state = ctk.CTkLabel(
            connection_row, text="● Đang kiểm tra nhân vật…", text_color="#d29922",
            font=ctk.CTkFont(size=12), anchor="w"
        )
        self.lbl_game_state.pack(side="left", padx=(14, 0))
        self.lbl_connection_info = ctk.CTkLabel(
            header, text="Đang tự tìm nơi cài LDPlayer và kết nối ADB…",
            font=ctk.CTkFont(size=11), text_color="#8b949e", wraplength=1120, justify="left"
        )
        self.lbl_connection_info.pack(anchor="w", padx=16, pady=(0, 8))

        # Main Layout (2 Columns)
        main_content = ctk.CTkFrame(self, fg_color="transparent")
        main_content.pack(fill="both", expand=True, padx=16, pady=(0, 16))

        # Left Column - Controls & Stats
        left_col = ctk.CTkFrame(main_content, width=340, fg_color="#161b22", corner_radius=10)
        left_col.pack(side="left", fill="both", padx=(0, 10), pady=0)

        # Status Badge
        lbl_st_title = ctk.CTkLabel(left_col, text="TRẠNG THÁI TUẦN TRA", font=ctk.CTkFont(size=12, weight="bold"), text_color="#8b949e")
        lbl_st_title.pack(anchor="w", padx=16, pady=(16, 4))

        self.lbl_status = ctk.CTkLabel(left_col, text="● Sẵn sàng tự lập tuyến", font=ctk.CTkFont(size=14, weight="bold"), text_color="#3fb950", wraplength=340, justify="left")
        self.lbl_status.pack(anchor="w", padx=16, pady=(0, 10))

        # Progress Map
        total_maps = len(self.engine.catalog)
        lbl_prog_title = ctk.CTkLabel(left_col, text=f"TIẾN TRÌNH KHẢO SÁT BẢN ĐỒ ({total_maps} MAP)", font=ctk.CTkFont(size=12, weight="bold"), text_color="#8b949e")
        lbl_prog_title.pack(anchor="w", padx=16, pady=(4, 4))

        self.lbl_cur_map = ctk.CTkLabel(left_col, text="Map: Đang sẵn sàng...", font=ctk.CTkFont(size=13), text_color="#f0f6fc", wraplength=340, justify="left")
        self.lbl_cur_map.pack(anchor="w", padx=16, pady=(0, 4))

        self.progress_bar = ctk.CTkProgressBar(left_col, height=12)
        self.progress_bar.set(0.0)
        self.progress_bar.pack(fill="x", padx=16, pady=(0, 4))

        self.lbl_progress_text = ctk.CTkLabel(left_col, text=f"0 / {total_maps} Bản đồ (0%)", font=ctk.CTkFont(size=12), text_color="#8b949e")
        self.lbl_progress_text.pack(anchor="w", padx=16, pady=(0, 14))


        # Confirmed Bugs Card
        bug_card = ctk.CTkFrame(left_col, fg_color="#21262d", corner_radius=8)
        bug_card.pack(fill="x", padx=16, pady=(0, 14))

        self.lbl_bug_count = ctk.CTkLabel(
            bug_card,
            text=f"{len(self.sheet_sync.records)} LỖI ĐÃ XÁC NHẬN",
            font=ctk.CTkFont(size=20, weight="bold"),
            text_color="#f85149"
        )
        self.lbl_bug_count.pack(pady=(10, 2))

        self.lbl_sheet_status = ctk.CTkLabel(bug_card, text="Đang đọc hàng chờ đồng bộ…", font=ctk.CTkFont(size=11), text_color="#8b949e", wraplength=330)
        self.lbl_sheet_status.pack(pady=(0, 10))

        # Action Buttons
        self.btn_reset = ctk.CTkButton(
            left_col, text="🔄 CHẠY LẠI TỪ ĐẦU (4 GÓC -> VÒNG) (F8)", font=ctk.CTkFont(size=13, weight="bold"),
            fg_color="#1f6feb", hover_color="#388bfd", height=36, command=self.action_reset_map
        )
        self.btn_reset.pack(fill="x", padx=16, pady=(5, 3))

        self.btn_start = ctk.CTkButton(
            left_col, text="▶ TIẾP TỤC / BẮT ĐẦU (F9)", font=ctk.CTkFont(size=14, weight="bold"),
            fg_color="#238636", hover_color="#2ea043", height=40, command=self.action_start
        )
        self.btn_start.pack(fill="x", padx=16, pady=5)

        self.btn_pause = ctk.CTkButton(
            left_col, text="⏸ TẠM DỪNG / TIẾP TỤC (F10)", font=ctk.CTkFont(size=13),
            fg_color="#d29922", hover_color="#bb8009", height=34, command=self.action_pause
        )
        self.btn_pause.pack(fill="x", padx=16, pady=5)

        self.btn_stop = ctk.CTkButton(
            left_col, text="⏹ DỪNG HỆ THỐNG (F11)", font=ctk.CTkFont(size=13),
            fg_color="#da3633", hover_color="#b62324", height=34, command=self.action_stop
        )
        self.btn_stop.pack(fill="x", padx=16, pady=5)

        # Google Sheet Buttons
        sheet_box = ctk.CTkFrame(left_col, fg_color="transparent")
        sheet_box.pack(fill="x", padx=16, pady=(10, 14))

        self.btn_open_sheet = ctk.CTkButton(
            sheet_box, text="🔗 MỞ LINK GOOGLE SHEET", font=ctk.CTkFont(size=12, weight="bold"),
            fg_color="#1f6feb", hover_color="#388bfd", height=36, command=self.action_open_sheet
        )
        self.btn_open_sheet.pack(fill="x", pady=(0, 6))

        self.btn_copy_sheet = ctk.CTkButton(
            sheet_box, text="📋 COPY LỖI VÀO CLIPBOARD (DÁN SHEET)", font=ctk.CTkFont(size=11, weight="bold"),
            fg_color="#8957e5", hover_color="#a371f7", height=34, command=self.action_copy_sheet
        )
        self.btn_copy_sheet.pack(fill="x", pady=0)
        ctk.CTkButton(sheet_box, text="CẤU HÌNH ĐỒNG BỘ / THỬ LẠI", height=30,
                      command=self.action_configure_sheet).pack(fill="x", pady=(6, 0))

        # Right Column - Review Box & Live Log
        right_col = ctk.CTkFrame(main_content, fg_color="#161b22", corner_radius=10)
        right_col.pack(side="right", fill="both", expand=True, padx=0, pady=0)

        # Route preview and per-leg coverage
        self.route_frame = ctk.CTkFrame(right_col, fg_color="#21262d", corner_radius=8)
        self.route_frame.pack(fill="both", expand=True, padx=16, pady=(16, 8))
        self.route_frame.bind("<Configure>", self._schedule_route_resize)
        route_heading = ctk.CTkFrame(self.route_frame, fg_color="transparent")
        route_heading.pack(fill="x", padx=14, pady=(10, 3))
        self.lbl_route_title = ctk.CTkLabel(
            route_heading, text="LỘ TRÌNH HIỆN TẠI", font=ctk.CTkFont(size=13, weight="bold"),
            text_color="#58a6ff", anchor="w"
        )
        self.lbl_route_title.pack(side="left", fill="x", expand=True)
        self.btn_open_map = ctk.CTkButton(
            route_heading, text="⛶ XEM MAP LỚN", width=150, height=28,
            state="disabled", command=self.open_map_viewer
        )
        self.btn_open_map.pack(side="right", padx=(8, 0))
        self.btn_inspection = ctk.CTkButton(
            route_heading, text="◎ HIỆU CHUẨN VÙNG", width=170, height=28,
            command=self.action_configure_inspection
        )
        self.btn_inspection.pack(side="right", padx=(8, 0))
        self.lbl_route_phase = ctk.CTkLabel(
            self.route_frame, text="Đang chờ bắt đầu.", font=ctk.CTkFont(size=11),
            text_color="#c9d1d9", anchor="w", justify="left", wraplength=1000
        )
        self.lbl_route_phase.pack(fill="x", padx=14, pady=(0, 4))
        self.route_image = ctk.CTkLabel(self.route_frame, text="Tool sẽ tự mở map, quan sát và lập tuyến.", height=260)
        self.route_image.pack(fill="both", expand=True, padx=14, pady=(0, 5))
        self.route_image.bind("<Double-Button-1>", lambda _event: self.open_map_viewer())
        self.lbl_route_legend = ctk.CTkLabel(
            self.route_frame, text="Lam: map đã đọc · Lục: vệt đã đi · Xám đậm: chưa đọc · Vàng: mốc · Cam: tuyến kế tiếp",
            font=ctk.CTkFont(size=11), text_color="#8b949e"
        )
        self.lbl_route_legend.pack(anchor="w", padx=14, pady=(0, 4))
        self.lbl_perf = ctk.CTkLabel(
            self.route_frame, text="Hiệu năng: đang chờ số đo.",
            font=ctk.CTkFont(size=10), text_color="#8b949e", anchor="w"
        )
        self.lbl_perf.pack(anchor="w", padx=14, pady=(0, 5))
        self.activity_tabs = ctk.CTkTabview(right_col, height=215, fg_color="#21262d")
        self.activity_tabs.pack(fill="x", padx=16, pady=(0, 12))
        for name in ("Nhật ký", "Duyệt cảnh", "Mốc tuyến"):
            self.activity_tabs.add(name)
        self.route_list = ctk.CTkTextbox(
            self.activity_tabs.tab("Mốc tuyến"), font=ctk.CTkFont(family="Consolas", size=11),
            text_color="#c9d1d9", fg_color="#0d1117", wrap="word"
        )
        self.route_list.pack(fill="both", expand=True, padx=8, pady=8)

        # Review Panel for User Confirmation (Initially Hidden or Idle)
        self.review_frame = ctk.CTkFrame(self.activity_tabs.tab("Duyệt cảnh"), fg_color="#21262d", corner_radius=8)
        self.review_frame.pack(fill="both", expand=True)

        self.lbl_review_title = ctk.CTkLabel(
            self.review_frame,
            text="CHƯA CÓ CẢNH NGHI NGỜ",
            font=ctk.CTkFont(size=13, weight="bold"),
            text_color="#8b949e"
        )
        self.lbl_review_title.pack(anchor="w", padx=14, pady=(10, 4))

        self.lbl_review_details = ctk.CTkLabel(
            self.review_frame,
            text="Tool lưu cảnh lặp nhiều khung hình và tiếp tục tuyến. Bạn có thể duyệt cảnh nghi ngờ; bộ phát hiện hiện hỗ trợ vùng đen và texture tím.",
            font=ctk.CTkFont(size=12),
            text_color="#c9d1d9", wraplength=620, justify="left"
        )
        self.lbl_review_details.pack(anchor="w", padx=14, pady=(0, 8))

        self.review_btn_box = ctk.CTkFrame(self.review_frame, fg_color="transparent")
        self.review_btn_box.pack(fill="x", padx=14, pady=(0, 10))

        self.btn_confirm_bug = ctk.CTkButton(
            self.review_btn_box, text="✅ XÁC NHẬN LỖI (GHI VÀO GOOGLE SHEET)", font=ctk.CTkFont(size=12, weight="bold"),
            fg_color="#238636", hover_color="#2ea043", height=34, state="disabled", command=self.action_confirm_bug
        )
        self.btn_confirm_bug.pack(side="left", fill="x", expand=True, padx=(0, 8))

        self.btn_reject_bug = ctk.CTkButton(
            self.review_btn_box, text="❌ BỎ QUA (KHÔNG PHẢI LỖI)", font=ctk.CTkFont(size=12),
            fg_color="#484f58", hover_color="#6e7681", height=34, state="disabled", command=self.action_reject_bug
        )
        self.btn_reject_bug.pack(side="left", fill="x", expand=True, padx=0)
        review_tools = ctk.CTkFrame(self.review_frame, fg_color="transparent")
        review_tools.pack(fill="x", padx=14, pady=(0, 8))
        ctk.CTkButton(review_tools, text="Cảnh chưa duyệt tiếp theo", width=200,
                      command=self.action_review_saved).pack(side="left", padx=(0, 6))
        ctk.CTkButton(review_tools, text="Xem ảnh / Clip", width=120,
                      command=self.action_view_evidence).pack(side="left", padx=(0, 6))
        ctk.CTkButton(review_tools, text="Xuất báo cáo", width=125,
                      command=self.action_report).pack(side="left")

        # Live Console Log
        self.log_box = ctk.CTkTextbox(self.activity_tabs.tab("Nhật ký"), font=ctk.CTkFont(family="Consolas", size=12), text_color="#c9d1d9", fg_color="#0d1117")
        self.log_box.pack(fill="both", expand=True, padx=8, pady=8)

        self.log("Khởi động hệ thống Auto Traversal & Săn Lỗi Đen Map thành công.")
        self.log("Tự dò LDPlayer trên máy; kết nối sẽ hiển thị trong danh sách phía trên.")
        self.log(f"Sheet đích: {GOOGLE_SHEET_URL}. Chỉ báo đồng bộ sau khi đọc lại đúng ID.")
        self._update_route_progress_ui(self.engine.get_route_snapshot())

    def log(self, message):
        self.log_box.insert("end", f"{message}\n")
        if int(self.log_box.index("end-1c").split(".")[0]) > 2000:
            self.log_box.delete("1.0", "300.0")
        self.log_box.see("end")

    def _schedule(self, callback):
        if not self._closing:
            try:
                self._ui_queue.put_nowait(callback)
            except queue.Full:
                pass

    def _drain_ui(self):
        if self._closing:
            return
        for _ in range(30):
            try:
                callback = self._ui_queue.get_nowait()
            except queue.Empty:
                break
            try:
                callback()
            except Exception as exc:
                self.log(f"Lỗi cập nhật giao diện: {exc}")
        self.after(80, self._drain_ui)

    def _start_global_hotkeys(self):
        import time
        def listener():
            try:
                import ctypes
                user32 = getattr(ctypes, "windll", None)
                if not user32:
                    return
                user32 = user32.user32
                VK_F8 = 0x77
                VK_F9 = 0x78
                VK_F10 = 0x79
                VK_F11 = 0x7A
                last_state = {VK_F8: False, VK_F9: False, VK_F10: False, VK_F11: False}
                while not getattr(self, "_closing", False):
                    time.sleep(0.06)
                    for vk, action in ((VK_F8, self.action_reset_map),
                                      (VK_F9, self.action_start),
                                      (VK_F10, self.action_pause),
                                      (VK_F11, self.action_stop)):
                        down = bool(user32.GetAsyncKeyState(vk) & 0x8000)
                        if down and not last_state[vk]:
                            self._schedule(action)
                        last_state[vk] = down
            except Exception:
                pass
        threading.Thread(target=listener, daemon=True, name="global-hotkeys").start()

    def _close_app(self):
        if self._closing:
            return
        self._closing = True
        self.engine.stop()
        self.lbl_status.configure(text="Đang hủy chạy, lưu tiến độ và đóng hàng chờ…")
        if self._ld_retry_id is not None:
            self.after_cancel(self._ld_retry_id)
        if self._ld_unlock_id is not None:
            self.after_cancel(self._ld_unlock_id)
        self._finish_close()

    def _finish_close(self):
        worker = self.engine.worker_thread
        if worker and worker.is_alive():
            self.after(150, self._finish_close)
            return
        if self._shutdown_thread is None:
            def shutdown():
                self.detector.close(timeout=5)
                self.sheet_sync.close(timeout=3)
                try:
                    self.sheet_sync.export()
                    self.reporter.generate()
                except Exception as exc:
                    print(f"Không xuất được báo cáo cuối phiên: {exc}")
                finally:
                    self.ctrl.close()
            self._shutdown_thread = threading.Thread(target=shutdown, daemon=True)
            self._shutdown_thread.start()
        if self._shutdown_thread.is_alive():
            self.after(150, self._finish_close)
        else:
            self.destroy()

    def _poll_sheet(self):
        if self._closing:
            return
        if not self._sheet_polling:
            self._sheet_polling = True
            def read_status():
                try:
                    summary = self.sheet_sync.summary()
                    count = len(self.sheet_sync.records)
                    self._schedule(lambda: self._render_sheet(summary, count))
                finally:
                    self._sheet_polling = False
            threading.Thread(target=read_status, daemon=True).start()
        self.after(1500, self._poll_sheet)

    def _poll_runtime_metrics(self):
        if self._closing:
            return
        snapshot = self.ctrl.metrics.snapshot()
        def p95(name):
            return snapshot.get(name, {}).get("p95_ms")
        telemetry, capture = p95("telemetry"), p95("screencap")
        inputs, routing = p95("input"), p95("route_planning")
        fmt = lambda value: f"{value:.0f} ms" if value is not None else "—"
        self.lbl_perf.configure(
            text=f"P95 · telemetry {fmt(telemetry)} · chụp ảnh {fmt(capture)} · lệnh {fmt(inputs)} · lập tuyến {fmt(routing)}"
        )
        self.after(5000, self._poll_runtime_metrics)

    def _poll_game_state(self):
        if self._closing:
            return
        if self.ctrl.connected and not self._detecting_ld and not self._game_polling:
            self._game_polling = True
            device = (self.ctrl.adb_path, self.ctrl.device_id)
            def read_state():
                try:
                    sample = self.vision.get_engine_telemetry()
                    self._schedule(lambda: self._render_game_state(sample, device))
                finally:
                    self._game_polling = False
            threading.Thread(target=read_state, daemon=True).start()
        self.after(3000, self._poll_game_state)

    def _render_game_state(self, sample, device):
        if device != (self.ctrl.adb_path, self.ctrl.device_id):
            return
        self._game_ready = self.engine._valid_position(sample)
        if self._game_ready:
            x, y = sample["position"]
            doing = "Đứng yên" if sample.get("doing") in self.engine.STOPPED else "Đang di chuyển"
            text = f"● {sample.get('map_name') or 'Map '+str(sample['map_id'])} · ({x:.1f}, {y:.1f}) · {doing}"
            color = "#3fb950"
        else:
            text = "● Chưa có vị trí mới · Hãy vào nhân vật trong game"
            color = "#d29922"
        self.lbl_game_state.configure(text=text, text_color=color)
        if self.engine.route_phase == "idle":
            self.lbl_status.configure(
                text="● Sẵn sàng khảo sát" if self._game_ready else "● Chờ nhân vật vào game",
                text_color=color
            )
        self._render_ld_connection()

    def _render_sheet(self, summary, count):
        self.lbl_bug_count.configure(text=f"{count} LỖI ĐÃ XÁC NHẬN")
        queued = sum(summary.get(state, 0) for state in ("queued", "retry", "syncing"))
        text = f"Đã đối soát: {summary.get('synced', 0)} · Chờ: {queued} · Cần xử lý: {summary.get('blocked', 0)}"
        if not summary.get("configured"):
            text += "\nChưa cấu hình dịch vụ ghi Sheet; dữ liệu vẫn được lưu cục bộ."
        if summary.get("last_error") or summary.get("worker_error"):
            text += "\n" + (summary.get("worker_error") or summary["last_error"])
        self.lbl_sheet_status.configure(text=text)

    def action_configure_inspection(self):
        if self.engine.is_running:
            self.log("Hiệu chuẩn vùng quan sát chỉ đổi được khi nhiệm vụ đã dừng.")
            return
        dialog = ctk.CTkToplevel(self)
        dialog.title("Hiệu chuẩn vùng quan sát map")
        dialog.geometry("620x560")
        dialog.transient(self)
        dialog.grab_set()
        ctk.CTkLabel(
            dialog, text="PHẠM VI NHÂN VẬT CÓ THỂ KIỂM TRA",
            font=ctk.CTkFont(size=16, weight="bold"), text_color="#58a6ff"
        ).pack(anchor="w", padx=22, pady=(22, 10))
        ctk.CTkLabel(
            dialog,
            text=("Đo bán kính theo đơn vị tọa độ game ở 4 vị trí thoáng, cách xa nhau. "
                  "Tool dùng số đo nhỏ nhất để tránh tô vùng chưa kiểm tra. "
                  "Nếu chưa có số đo đáng tin cậy, để trạng thái chưa hiệu chuẩn; "
                  "tool vẫn ghi vệt di chuyển nhưng không khẳng định đã kiểm tra toàn bộ bề mặt."),
            wraplength=570, justify="left", text_color="#c9d1d9"
        ).pack(anchor="w", padx=22, pady=(0, 16))
        ctk.CTkLabel(dialog, text="4 số đo tại 4 vị trí khác nhau (tọa độ game)").pack(anchor="w", padx=22)
        measurements = ctk.CTkFrame(dialog, fg_color="transparent")
        measurements.pack(fill="x", padx=22, pady=(5, 12))
        saved_samples = self.ctrl.config.get("traversal", {}).get("inspection_radius_samples", [])
        sample_entries = []
        for index in range(4):
            row = ctk.CTkFrame(measurements, fg_color="transparent")
            row.pack(fill="x", pady=3)
            ctk.CTkLabel(row, text=f"Vị trí {index+1}", width=90, anchor="w").pack(side="left")
            entry = ctk.CTkEntry(row, width=210, placeholder_text="Ví dụ: 6.5")
            entry.pack(side="left")
            if index < len(saved_samples):
                entry.insert(0, str(saved_samples[index]))
            sample_entries.append(entry)
        current_radius = self.ctrl.config.get("traversal", {}).get("inspection_radius", 0)
        ctk.CTkLabel(dialog, text=f"Bán kính đang lưu: {float(current_radius):.2f} · chưa dùng để xác nhận nếu thiếu 4 số đo.",
                     text_color="#8b949e").pack(anchor="w", padx=22, pady=(0, 12))
        confirmed = tk.BooleanVar(value=bool(
            self.ctrl.config.get("traversal", {}).get("inspection_calibrated", False)
        ))
        ctk.CTkCheckBox(
            dialog, text="Tôi đã đo và kiểm tra con số này trên map thật",
            variable=confirmed
        ).pack(anchor="w", padx=22, pady=(0, 18))
        result = ctk.CTkLabel(dialog, text="", wraplength=570, justify="left")
        result.pack(anchor="w", padx=22, pady=(0, 12))

        def save_calibration():
            old_radius = self.ctrl.config.get("traversal", {}).get("inspection_radius", 0)
            old_confirmed = self.ctrl.config.get("traversal", {}).get("inspection_calibrated", False)
            old_samples = self.ctrl.config.get("traversal", {}).get("inspection_radius_samples", [])
            try:
                raw_samples = [entry.get().strip() for entry in sample_entries]
                has_measurements = any(raw_samples)
                samples = raw_samples if has_measurements or confirmed.get() else None
                updated = self.engine.update_inspection_calibration(
                    current_radius, confirmed.get(), samples
                )
                self.ctrl.config["traversal"]["inspection_radius"] = updated["radius"]
                self.ctrl.config["traversal"]["inspection_calibrated"] = updated["calibrated"]
                self.ctrl.config["traversal"]["inspection_radius_samples"] = (
                    self.engine.settings.get("inspection_radius_samples", [])
                )
                with open(self.ctrl.config_path, encoding="utf-8") as stream:
                    persisted_config = json.load(stream)
                persisted_config.setdefault("traversal", {}).update(self.ctrl.config["traversal"])
                atomic_json(self.ctrl.config_path, persisted_config)
            except (ValueError, RuntimeError, OSError) as exc:
                try:
                    self.engine.update_inspection_calibration(old_radius, old_confirmed, old_samples or None)
                except Exception:
                    pass
                result.configure(text=f"Chưa lưu được: {exc}", text_color="#f85149")
                return
            state = "Đã xác nhận hiệu chuẩn" if updated["calibrated"] else "Đã lưu nhưng vẫn để chưa hiệu chuẩn"
            self.log(f"{state}: bán kính {updated['radius']:.2f} đơn vị game.")
            dialog.destroy()

        actions = ctk.CTkFrame(dialog, fg_color="transparent")
        actions.pack(fill="x", padx=22, pady=(0, 18))
        ctk.CTkButton(actions, text="LƯU HIỆU CHUẨN", command=save_calibration).pack(side="left")
        ctk.CTkButton(actions, text="ĐÓNG", fg_color="#484f58", hover_color="#6e7681",
                      command=dialog.destroy).pack(side="right")

    def action_configure_sheet(self):
        dialog = ctk.CTkToplevel(self)
        dialog.title("Đồng bộ Google Sheet")
        dialog.geometry("660x350")
        ctk.CTkLabel(dialog, text="Làm theo docs/CAU_HINH_GOOGLE_SHEET.md để triển khai dịch vụ một lần.", wraplength=610).pack(padx=16, pady=12)
        endpoint = ctk.CTkEntry(dialog, width=610, placeholder_text="URL Apps Script .../exec")
        endpoint.pack(padx=16, pady=6)
        endpoint.insert(0, self.sheet_sync.config.get("endpoint", ""))
        token = ctk.CTkEntry(dialog, width=610, show="*", placeholder_text="SYNC_TOKEN của dịch vụ")
        token.pack(padx=16, pady=6)
        token.insert(0, os.environ.get(self.sheet_sync.config.get("token_env", "PHONG_THAN_SYNC_TOKEN"), ""))
        ctk.CTkLabel(dialog, text="Token ở đây chỉ giữ cho lần mở ứng dụng này. Có thể dùng biến môi trường PHONG_THAN_SYNC_TOKEN để giữ qua lần sau.", wraplength=610).pack(padx=16, pady=8)
        result = ctk.CTkLabel(dialog, text="", wraplength=610)
        result.pack(padx=16, pady=6)
        def save():
            url, secret = endpoint.get().strip(), token.get().strip()
            if not url.startswith("https://script.google.com/macros/s/") or not url.endswith("/exec") or len(secret) < 32:
                result.configure(text="Cần URL triển khai /exec và token ít nhất 32 ký tự.")
                return
            self.sheet_sync.config["endpoint"] = url
            os.environ[self.sheet_sync.config.get("token_env", "PHONG_THAN_SYNC_TOKEN")] = secret
            path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "config", "settings.json")
            with open(path, encoding="utf-8") as stream:
                config = json.load(stream)
            config["sheet_sync"] = self.sheet_sync.config
            atomic_json(path, config)
            self.sheet_sync.retry_blocked()
            result.configure(text="Đã lưu URL và đánh thức hàng chờ. Trạng thái đồng bộ hiển thị tại màn hình chính.")
        ctk.CTkButton(dialog, text="LƯU VÀ THỬ LẠI HÀNG CHỜ", command=save).pack(pady=8)

    def action_detect_ld(self):
        worker = self.engine.worker_thread
        if self._closing or self._detecting_ld or self.engine.is_running or (worker and worker.is_alive()):
            return
        if self._ld_retry_id is not None:
            self.after_cancel(self._ld_retry_id)
            self._ld_retry_id = None
        self._detecting_ld = True
        self._game_ready = False
        self.btn_detect_ld.configure(state="disabled", text="Đang dò…")
        self.ld_selector.configure(state="disabled")
        self.btn_start.configure(state="disabled")
        self.lbl_connection_info.configure(text="Đang tự tìm nơi cài LDPlayer và các LD đang online…")

        def discover():
            try:
                self.ctrl.refresh_connection()
            except Exception as exc:
                self.ctrl.adb_path = self.ctrl.device_id = None
                self.ctrl.available_devices = []
                self.ctrl.connection_status = f"Chưa dò được LDPlayer: {exc}"
            self._schedule(self._finish_detect_ld)

        threading.Thread(target=discover, daemon=True).start()

    def _finish_detect_ld(self):
        self._detecting_ld = False
        self._render_ld_connection()
        if self.ctrl.connection_status != self._last_connection_message:
            self.log(self.ctrl.connection_status)
            if self.ctrl.adb_path:
                self.log(f"ADB được tìm thấy: {self.ctrl.adb_path}")
            self._last_connection_message = self.ctrl.connection_status
        if not self.ctrl.connected and not self.ctrl.available_devices:
            self._ld_retry_id = self.after(10000, self.action_detect_ld)

    def _render_ld_connection(self):
        self._device_options = {}
        selected_label = None
        for device in self.ctrl.available_devices:
            game = " · game đang chạy" if device["game_running"] else (" · đã cài game" if device["game_installed"] else "")
            label = f"{device['name']} [{device['serial']}]{game}"
            self._device_options[label] = device["serial"]
            if device["serial"] == self.ctrl.device_id:
                selected_label = label
        values = list(self._device_options) or ["Chưa có LD online"]
        worker = getattr(self.engine, "worker_thread", None)
        worker_active = bool(worker and worker.is_alive())
        locked = self._detecting_ld or self.engine.is_running or worker_active
        if worker_active and not self.engine.is_running and self._ld_unlock_id is None:
            self._ld_unlock_id = self.after(150, self._unlock_ld_after_stop)
        self.ld_selector.configure(values=values, state="disabled" if locked or not self._device_options else "normal")
        self.ld_selector.set(selected_label or ("Chọn LD cần điều khiển" if self._device_options else values[0]))
        self.btn_detect_ld.configure(state="disabled" if locked else "normal", text="Dò lại LD")
        ready = getattr(self, "_game_ready", False)
        self.btn_start.configure(state="normal" if self.ctrl.connected and ready and not locked else "disabled")
        if hasattr(self, "btn_pause"):
            paused = getattr(self.engine, "is_paused", False)
            acknowledged = getattr(self.engine, "_pause_ack", False)
            pause_text = ("ĐANG XÁC MINH TẠM DỪNG…" if paused and not acknowledged
                          else "▶ TIẾP TỤC KHẢO SÁT (F10)" if paused else "⏸ TẠM DỪNG (F10)")
            self.btn_pause.configure(text=pause_text, state="normal" if self.engine.is_running
                                     and not (paused and not acknowledged) else "disabled")
            self.btn_stop.configure(text="ĐANG DỪNG…" if worker_active and not self.engine.is_running
                                    else "⏹ DỪNG HỆ THỐNG (F11)",
                                    state="normal" if self.engine.is_running else "disabled")
            self.btn_inspection.configure(state="disabled" if locked else "normal")
        info = self.ctrl.connection_status
        if self.ctrl.adb_path:
            info += f"  ADB: {self.ctrl.adb_path}"
        self.lbl_connection_info.configure(text=info)
        self.lbl_device_summary.configure(
            text=f"LDPlayer: {self.ctrl.device_name} · {self.ctrl.device_id or 'chưa kết nối'} "
                 "| Bố cục ngang 16:9 · Tự hiệu chỉnh kích thước khi bắt đầu"
        )

    def _unlock_ld_after_stop(self):
        self._ld_unlock_id = None
        if not self._closing:
            self._render_ld_connection()

    def action_select_ld(self, label):
        worker = getattr(self.engine, "worker_thread", None)
        if self._detecting_ld or self.engine.is_running or (worker and worker.is_alive()):
            return
        serial = self._device_options.get(label)
        if serial and self.ctrl.select_device(serial):
            self._game_ready = False
            self._render_ld_connection()
            self.log(self.ctrl.connection_status)

    def update_status(self, msg):
        self._schedule(lambda: self._update_status_ui(msg))

    def _update_status_ui(self, msg):
        phase = self.engine.route_phase
        color = ("#f85149" if phase in {"error", "stop_unverified"}
                 else "#d29922" if phase in {"stopping", "paused", "partial"}
                 else "#58a6ff" if self.engine.is_running else "#3fb950")
        self.lbl_status.configure(text=f"● {msg[:160]}{'…' if len(msg)>160 else ''}", text_color=color)
        self.log(msg)

    def update_progress(self, visited_count, total_count, cur_map_name):
        self._schedule(lambda: self._update_progress_ui(visited_count, total_count, cur_map_name))

    def update_route_progress(self, snapshot):
        self._schedule(lambda: self._update_route_progress_ui(snapshot))

    def _update_route_progress_ui(self, snapshot):
        phase = snapshot["phase"]
        if phase == "surveying":
            survey_pct = snapshot.get("observed_fraction", 0) * 100
            title = f"{snapshot['map_name']} · Đang đọc map · {survey_pct:.1f}%"
        else:
            title = (f"{snapshot['map_name']} · Vòng {snapshot['batch_idx']}/{max(0, snapshot['batch_count']-1)} "
                     f"· Đã tới {snapshot['done']}/{snapshot['total']} mốc")
        self.lbl_route_title.configure(text=title)
        phase_labels = {
            "idle": "Sẵn sàng tự quan sát map và lập tuyến theo từng vùng.",
            "connecting": "Đang xác minh kết nối và khóa đúng phiên LD đã chọn.",
            "surveying": "Tool đang tự kéo xem map và ghi nhớ địa hình.",
            "planned": "Đã lập các vòng mở rộng; tool tự chọn mốc chưa đi.",
            "pinning": "Tool đang tự ghim đích theo tuyến đã lập.",
            "walking": "Đang đi; theo dõi tọa độ thực tế trước khi chuyển chặng.",
            "verifying": "Đang xác minh đứng yên từ dữ liệu mới trước khi ghim chặng.",
            "transition": "Đang chuyển map; tiến độ từng map được lưu riêng.",
            "transition_return": "Phát hiện cổng sang map khác khi map hiện tại chưa xong; đang quay lại map cũ.",
            "completed": "Đã hoàn thành các mốc tuyến của nhiệm vụ; độ phủ hình ảnh được báo riêng theo từng map.",
            "partial": "Đã lưu tiến độ; còn phần chưa đủ bằng chứng để xác nhận hoàn tất.",
            "error": "Hành trình đã dừng; các ô chưa tới đích vẫn được giữ lại.",
            "stopping": "Đang hủy lệnh điều khiển và lưu điểm dừng.",
            "stopped": "Đã dừng và lưu tiến độ.",
            "paused": "Đã xác minh nhân vật dừng; giữ chặng để tiếp tục.",
            "stop_unverified": "Đã yêu cầu hủy chạy nhưng chưa xác minh đứng yên. Cần kiểm tra LD."
        }
        self.lbl_route_phase.configure(
            text=phase_labels.get(phase, "Đang cập nhật lộ trình.")
                 + (f" Cần đi lại: {snapshot['unresolved']} ô." if snapshot["unresolved"] else "")
                 + (f" Đã xem {snapshot['observed_fraction']*100:.1f}% ảnh map."
                    if snapshot["total"] or phase == "surveying" else "")
        )
        leg = snapshot.get("leg", {})
        stats = snapshot.get("coverage", {})
        details = self.lbl_route_phase.cget("text")
        if snapshot.get("blocked_reason"):
            details += "\n"+snapshot["blocked_reason"]
        if leg.get("from") and leg.get("to"):
            details += f"\n{leg.get('purpose', '')}: {tuple(round(v, 1) for v in leg['from'])} → {tuple(round(v, 1) for v in leg['to'])}"
        if snapshot["total"]:
            details += f"\nVệt đã đi: {stats.get('travelled_fraction', 0)*100:.1f}% diện tích nền ước lượng."
            details += (f" Kiểm tra hình: {stats.get('inspected_fraction', 0)*100:.1f}%." if stats.get("inspection_calibrated")
                        else " Phạm vi kiểm tra hình chưa được hiệu chỉnh; chưa xác nhận phủ toàn map.")
        self.lbl_route_phase.configure(text=details)
        if snapshot.get("preview_rgb") is not None:
            preview = Image.fromarray(snapshot["preview_rgb"])
            self._current_map_preview = preview.copy()
            self.btn_open_map.configure(state="normal")
            self._render_route_image()
        else:
            self._current_map_preview = None
            self.btn_open_map.configure(state="disabled")
            self.route_image.configure(image=self._empty_preview_image)
            self.route_image.configure(text="Đang chờ ảnh map từ game…", height=220)
            self._route_photo = None
            self._route_render_key = None
        self._refresh_map_viewer(snapshot)

        lines = []
        for idx, checkpoint in enumerate(snapshot["checkpoints"]):
            marker = {"done": "✓", "active": "▶", "pending": "○", "retry": "↻", "unreachable": "!", "deferred": "!"}.get(checkpoint["state"], "○")
            lines.append(f"{marker} {idx + 1:02d}. {checkpoint['name']}")
        contents = "\n".join(lines)
        if contents != getattr(self, "_route_contents", None):
            scroll = self.route_list.yview()[0]
            self.route_list.configure(state="normal")
            self.route_list.delete("1.0", "end")
            self.route_list.insert("1.0", contents)
            self.route_list.configure(state="disabled")
            self.route_list.yview_moveto(scroll)
            self._route_contents = contents

        self._render_ld_connection()

    def _schedule_route_resize(self, _event=None):
        if self._closing:
            return
        if self._route_resize_id is not None:
            self.after_cancel(self._route_resize_id)
        self._route_resize_id = self.after(120, self._render_route_image)

    def _render_route_image(self):
        self._route_resize_id = None
        preview = self._current_map_preview
        if self._closing or preview is None:
            return
        available_width = max(1, self.route_image.winfo_width()-16)
        available_height = max(1, self.route_image.winfo_height()-16)
        if min(available_width, available_height) < 30:
            return
        scale = min(available_width/preview.width, available_height/preview.height)
        width, height = max(1, round(preview.width*scale)), max(1, round(preview.height*scale))
        key = (id(preview), width, height)
        if key == getattr(self, "_route_render_key", None):
            return
        self._route_render_key = key
        photo = ctk.CTkImage(light_image=preview, dark_image=preview, size=(width, height))
        # Keep the previous Tk image alive until the label actually replaces it.
        # CTkLabel applies text before image when both are passed together.
        self.route_image.configure(image=photo)
        self.route_image.configure(text="")
        self._route_photo = photo

    def open_map_viewer(self):
        if self._current_map_preview is None:
            return
        if self._map_viewer is not None and self._map_viewer.winfo_exists():
            self._map_viewer.lift()
            self._render_map_viewer_image()
            return

        viewer = ctk.CTkToplevel(self)
        self._map_viewer = viewer
        viewer.title("Bản đồ khảo sát · Phóng to")
        viewer.configure(fg_color="#0d1117")
        screen_width, screen_height = self.winfo_screenwidth(), self.winfo_screenheight()
        window_width = max(720, min(1700, screen_width-48))
        window_height = max(560, min(1100, screen_height-72))
        x, y = max(0, (screen_width-window_width)//2), max(0, (screen_height-window_height)//2)
        viewer.geometry(f"{window_width}x{window_height}+{x}+{y}")

        self._map_viewer_status = ctk.CTkLabel(
            viewer, text="", font=ctk.CTkFont(size=16, weight="bold"), text_color="#c9d1d9"
        )
        self._map_viewer_status.pack(fill="x", padx=20, pady=(16, 8))
        self._map_viewer_image = ctk.CTkLabel(viewer, text="", fg_color="#0d1117")
        self._map_viewer_image.pack(fill="both", expand=True, padx=14, pady=8)
        ctk.CTkLabel(
            viewer,
            text="Ảnh map trong game · Lam: đã đọc · Lục: vệt đã đi · Xám đậm: chưa đọc · Vàng: mốc · Cam: tuyến kế tiếp",
            font=ctk.CTkFont(size=13), text_color="#aab4c0"
        ).pack(fill="x", padx=20, pady=(4, 16))
        viewer.bind("<Configure>", self._schedule_map_viewer_resize)
        viewer.protocol("WM_DELETE_WINDOW", self._close_map_viewer)
        self._refresh_map_viewer(self.engine.get_route_snapshot())
        viewer.after(80, self._render_map_viewer_image)

    def _refresh_map_viewer(self, snapshot):
        if self._map_viewer is None or not self._map_viewer.winfo_exists():
            return
        coverage = snapshot.get("coverage", {})
        if snapshot.get("phase") == "surveying":
            progress = f"Đã đọc {snapshot.get('observed_fraction', 0)*100:.1f}% ảnh map"
        else:
            progress = f"Đã đi {coverage.get('travelled_fraction', 0)*100:.1f}% diện tích ước lượng"
            if coverage.get("inspection_calibrated"):
                progress += f" · Đã kiểm tra hình {coverage.get('inspected_fraction', 0)*100:.1f}%"
            else:
                progress += " · Chưa hiệu chuẩn vùng quan sát"
        self._map_viewer_status.configure(text=f"{snapshot.get('map_name', 'Map')} · {progress}")
        self._render_map_viewer_image()

    def _schedule_map_viewer_resize(self, event):
        if event.widget is not self._map_viewer:
            return
        if self._map_viewer_resize_id is not None:
            self.after_cancel(self._map_viewer_resize_id)
        self._map_viewer_resize_id = self.after(100, self._render_map_viewer_image)

    def _render_map_viewer_image(self):
        self._map_viewer_resize_id = None
        if (self._map_viewer is None or not self._map_viewer.winfo_exists()
                or self._map_viewer_image is None):
            return
        if self._current_map_preview is None:
            self._map_viewer_image.configure(image=self._empty_preview_image)
            self._map_viewer_image.configure(text="Đang chờ ảnh map từ game…")
            self._map_viewer_photo = None
            return
        preview = self._current_map_preview
        available_width = max(320, self._map_viewer_image.winfo_width()-24)
        available_height = max(240, self._map_viewer_image.winfo_height()-24)
        scale = min(available_width/preview.width, available_height/preview.height)
        width, height = max(1, round(preview.width*scale)), max(1, round(preview.height*scale))
        photo = ctk.CTkImage(light_image=preview, dark_image=preview, size=(width, height))
        self._map_viewer_image.configure(image=photo)
        self._map_viewer_image.configure(text="")
        self._map_viewer_photo = photo

    def _close_map_viewer(self):
        if self._map_viewer_resize_id is not None:
            self.after_cancel(self._map_viewer_resize_id)
            self._map_viewer_resize_id = None
        if self._map_viewer is not None and self._map_viewer.winfo_exists():
            self._map_viewer.destroy()
        self._map_viewer = None
        self._map_viewer_image = None
        self._map_viewer_status = None
        self._map_viewer_photo = None

    def _update_progress_ui(self, visited_count, total_count, cur_map_name):
        pct = visited_count / max(1, total_count)
        self.progress_bar.set(pct)
        self.lbl_cur_map.configure(text=f"Map: {cur_map_name}")
        self.lbl_progress_text.configure(text=f"{visited_count} / {total_count} tuyến map đã hoàn thành ({int(pct*100)}%)")

    def on_glitch_alert(self, incident):
        self._schedule(lambda: self._on_glitch_alert_ui(incident))

    def _on_glitch_alert_ui(self, incident):
        self._display_incident = dict(incident)
        sev = incident.get("severity", "MAJOR")
        sev_vi = incident.get("severity_vi", "TRUNG BÌNH")
        bg_color = "#4d1515" if sev == "CRITICAL" else "#3d2712" if sev == "MAJOR" else "#182c3f"
        txt_color = "#ff4d4d" if sev == "CRITICAL" else "#ffa64d" if sev == "MAJOR" else "#58a6ff"

        self.review_frame.configure(fg_color=bg_color)
        self.lbl_review_title.configure(
            text=f"🚨 [{sev_vi}] PHÁT HIỆN LỖI: {incident['glitch_type']}!",
            text_color=txt_color
        )
        self.lbl_review_details.configure(
            text=f"Map: {incident['map_name']} | Tọa độ: ({incident['coord_x']}, {incident['coord_y']})\n"
                 f"Clip GIF: {incident.get('clip_gif', 'Đang kết xuất...')} | Ảnh: {incident.get('annotated_image', '')}\n"
                 f"Trạng thái: {incident['status']} | Diện tích lỗi: {incident.get('total_defect_area', 'N/A')} px"
        )
        self.btn_confirm_bug.configure(state="normal")
        self.btn_reject_bug.configure(state="normal")
        self.log(f"[CẢNH NGHI NGỜ - {sev_vi}] {incident['glitch_type']} tại {incident['map_name']} ({incident['coords']}); đã lưu clip & ảnh.")

    def action_confirm_bug(self):
        record = self.engine.user_confirm_bug(incident=getattr(self, "_display_incident", None))
        if record:
            self.lbl_bug_count.configure(text=f"{len(self.sheet_sync.records)} LỖI ĐÃ XÁC NHẬN")
            self.review_frame.configure(fg_color="#21262d")
            self.lbl_review_title.configure(text="✅ Đã ghi nhận lỗi thành công!", text_color="#3fb950")
            self.lbl_review_details.configure(text=f"Đã lưu lỗi {record['id']} và đưa vào hàng chờ; xem trạng thái Sheet để biết kết quả ghi.")
            self.btn_confirm_bug.configure(state="disabled")
            self.btn_reject_bug.configure(state="disabled")
            self.log("Đã lưu xác nhận vào SQLite; đồng bộ chạy ở nền.")

    def action_review_saved(self):
        def read():
            records = [record for record in self.sheet_sync.store.records(include_suspects=True)
                       if record.get("status") == "suspected" and record.get("evidence_state") == "ready"]
            if records:
                cursor = getattr(self, "_review_cursor", 0) % len(records)
                self._review_cursor = cursor+1
                self._schedule(lambda: self._on_glitch_alert_ui(records[cursor]))
            else:
                self._schedule(lambda: self.log("Không còn cảnh có bằng chứng đang chờ duyệt."))
        threading.Thread(target=read, daemon=True).start()

    def action_view_evidence(self):
        record = getattr(self, "_display_incident", None)
        if record:
            clip_name = record.get("clip_gif", "")
            clip_path = Path(self.detector.evidence_dir) / os.path.basename(clip_name) if clip_name else None
            if clip_path and clip_path.is_file():
                webbrowser.open(clip_path.resolve().as_uri())
                return
            path = Path(self.detector.evidence_dir) / os.path.basename(record.get("annotated_image", ""))
            if path.is_file():
                webbrowser.open(path.resolve().as_uri())

    def action_report(self):
        def export():
            try:
                path = self.reporter.generate()
                self._schedule(lambda: self.log(f"Đã xuất báo cáo: {path}"))
                webbrowser.open(Path(path).resolve().as_uri())
            except Exception as exc:
                message = str(exc)
                self._schedule(lambda: self.log(f"Không xuất được báo cáo: {message}"))
        threading.Thread(target=export, daemon=True).start()

    def action_reject_bug(self):
        self.engine.user_reject_bug(incident=getattr(self, "_display_incident", None))
        self.review_frame.configure(fg_color="#21262d")
        self.lbl_review_title.configure(text="🛡️ Đã bỏ qua cảnh báo (Không phải lỗi)", text_color="#8b949e")
        self.lbl_review_details.configure(text="Bot đang tiếp tục lách qua vật cản và đi quanh map.")
        self.btn_confirm_bug.configure(state="disabled")
        self.btn_reject_bug.configure(state="disabled")

    def action_reset_map(self):
        if not self.ctrl.connected or self._detecting_ld:
            self.action_detect_ld()
            return
        if not self._game_ready:
            self.log("Chưa có vị trí nhân vật mới. Hãy vào game rồi đợi trạng thái sẵn sàng.")
            return
        self.log("🔄 Đang thiết lập lại lộ trình từ đầu: 4 GÓC FULL MAP TRƯỚC -> CÁC VÒNG TRÒN SAU...")
        if self.engine.is_running:
            self.engine.stop()
            time.sleep(0.3)
        self.engine.reset_current_map()
        if self.engine.start():
            self.btn_start.configure(state="disabled")
            self._render_ld_connection()

    def action_start(self):
        if not self.ctrl.connected or self._detecting_ld:
            self.action_detect_ld()
            return
        if not self._game_ready:
            self.log("Chưa có vị trí nhân vật mới. Hãy vào game rồi đợi trạng thái sẵn sàng.")
            return
        if self.engine.start():
            self.btn_start.configure(state="disabled")
            self._render_ld_connection()

    def action_pause(self):
        if self.engine.is_paused:
            self.engine.resume()
        else:
            self.engine.pause()
        self._render_ld_connection()

    def action_stop(self):
        self.engine.stop()
        self._render_ld_connection()

    def action_open_sheet(self):
        webbrowser.open(GOOGLE_SHEET_URL)
        self.log(f"Đã mở liên kết Google Sheet trên trình duyệt: {GOOGLE_SHEET_URL}")

    def action_copy_sheet(self):
        ok, msg = self.sheet_sync.copy_all_to_clipboard()
        self.log(f"[GoogleSheetSync] {msg}")

if __name__ == "__main__":
    app = AppGUI()
    app.mainloop()
