import sys
import argparse
import atexit
import os

sys.dont_write_bytecode = True

def main():
    parser = argparse.ArgumentParser(description="Phong Thần — Khảo sát vòng mở rộng và ghi nhận bất thường")
    parser.add_argument("--cli", action="store_true", help="Chạy chế độ dòng lệnh (Headless CLI) không dùng GUI")
    args = parser.parse_args()

    from core.single_instance import SingleInstanceLock
    root = os.path.dirname(os.path.abspath(__file__))
    process_lock = SingleInstanceLock(os.path.join(root, "reports", "tool-instance.lock"))
    if not process_lock.acquire():
        print("Tool đã có một phiên đang chạy. Hãy dùng cửa sổ hiện tại để điều khiển phiên đó.")
        return 2
    atexit.register(process_lock.release)

    if args.cli:
        print("=" * 60)
        print("  PHONG THẦN AUTO MAP TRAVELER & LAG HUNTER (CLI MODE)")
        print("=" * 60)
        from core.ld_controller import LDController
        from core.vision_engine import VisionEngine
        from core.glitch_detector import GlitchDetector
        from core.obstacle_bypasser import ObstacleBypasser
        from core.google_sheet_sync import GoogleSheetSync
        from core.map_traversal_engine import MapTraversalEngine

        ctrl = LDController()
        vision = VisionEngine(controller=ctrl)
        detector = GlitchDetector(settings=ctrl.config.get("detection", {}))
        bypasser = ObstacleBypasser(ctrl)
        sheet_sync = GoogleSheetSync()
        engine = MapTraversalEngine(ctrl, vision, detector, bypasser, sheet_sync)

        print("[CLI] Khởi động động cơ khảo sát...")
        engine.start()
        try:
            while engine.is_running:
                import time
                time.sleep(1)
        except KeyboardInterrupt:
            print("\n[CLI] Đang dừng hệ thống...")
            engine.stop()
        finally:
            if engine.worker_thread:
                engine.worker_thread.join()
            detector.close(timeout=5)
            sheet_sync.close(timeout=3)
            sheet_sync.export()
            from core.html_reporter import HTMLReporter
            HTMLReporter(store=sheet_sync.store).generate()
            print(f"[CLI] Kết thúc: {engine.route_phase}. Tiến độ và hàng chờ đã lưu.")
    else:
        from gui.app_gui import AppGUI
        app = AppGUI()
        app.mainloop()

if __name__ == "__main__":
    main()
