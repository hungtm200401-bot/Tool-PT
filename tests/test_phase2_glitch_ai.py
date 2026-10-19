import os
import shutil
import tempfile
import time
import unittest
import numpy as np
import cv2
from PIL import Image

from core.glitch_detector import GlitchDetector
from core.runtime_store import RuntimeStore
from core.html_reporter import HTMLReporter


class TestPhase2GlitchAI(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.evidence_dir = os.path.join(self.temp_dir, "evidence")
        os.makedirs(self.evidence_dir, exist_ok=True)
        self.sqlite_path = os.path.join(self.temp_dir, "test_runtime.sqlite3")
        self.store = RuntimeStore(self.sqlite_path)

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def _create_synthetic_frame(self, defect_type=None, defect_size=(100, 100)):
        # 1920x1080 frame with natural variation
        frame = np.full((1080, 1920, 3), 120, dtype=np.uint8)
        # Add texture variation so std > 5
        frame[::4, ::4] = 200
        if defect_type == "black_void":
            # Dark void within ground mask: x: 500..500+w, y: 400..400+h
            w, h = defect_size
            frame[400:400+h, 500:500+w] = 0
        elif defect_type == "missing_texture":
            w, h = defect_size
            frame[400:400+h, 500:500+w] = (220, 20, 220) # Magenta/purple
        return frame

    def test_frame_buffer_rolling(self):
        detector = GlitchDetector(
            evidence_dir=self.evidence_dir,
            settings={"confirm_frames": 2, "confirm_seconds": 0.1}
        )
        try:
            for i in range(10):
                frame = self._create_synthetic_frame()
                context = {"position": (100.0, 100.0), "position_frame": i + 1, "map_id": 1}
                detector.inspect_frame_for_glitches(frame, "Test Map", "100,100", context=context)
            self.assertEqual(len(detector._frame_buffer), 6)
        finally:
            detector.close(timeout=2)

    def test_severity_classification_and_gif_creation(self):
        detector = GlitchDetector(
            evidence_dir=self.evidence_dir,
            settings={"confirm_frames": 2, "confirm_seconds": 0.1, "dedup_seconds": 0}
        )
        try:
            # Create a frame with a large black void (>12000 px) -> CRITICAL
            large_frame = self._create_synthetic_frame(defect_type="black_void", defect_size=(150, 120)) # 18,000 px
            
            # Feed frame 1
            ctx1 = {"position": (150.0, 150.0), "position_frame": 1, "map_id": 1}
            detector.inspect_frame_for_glitches(large_frame, "Phong Thần Đài", "150,150", context=ctx1)
            time.sleep(0.15)
            
            # Feed frame 2 to confirm
            ctx2 = {"position": (150.5, 150.5), "position_frame": 2, "map_id": 1}
            found, incident = detector.inspect_frame_for_glitches(large_frame, "Phong Thần Đài", "150.5,150.5", context=ctx2)
            
            self.assertTrue(found)
            self.assertIsNotNone(incident)
            self.assertEqual(incident["severity"], "CRITICAL")
            self.assertEqual(incident["severity_vi"], "NGHIÊM TRỌNG")
            self.assertIn("_clip.gif", incident["clip_gif"])
            self.assertGreater(incident["total_defect_area"], 12000)

            # Wait for evidence worker to flush
            detector.close(timeout=3)

            # Check that animated GIF was created and is valid
            gif_path = os.path.join(self.evidence_dir, incident["clip_gif"])
            self.assertTrue(os.path.isfile(gif_path))
            with Image.open(gif_path) as img:
                self.assertEqual(img.format, "GIF")
                self.assertTrue(getattr(img, "is_animated", False))
                self.assertGreaterEqual(img.n_frames, 2)
                # Width resized for efficiency
                self.assertEqual(img.size[0], 640)
        finally:
            detector.close(timeout=1)

    def test_save_gif_directly(self):
        detector = GlitchDetector(evidence_dir=self.evidence_dir)
        try:
            frames = [
                np.full((300, 400, 3), 50, dtype=np.uint8),
                np.full((300, 400, 3), 150, dtype=np.uint8),
                np.full((300, 400, 3), 250, dtype=np.uint8)
            ]
            detector._save_gif("test_direct.gif", frames, duration_ms=200)
            target = os.path.join(self.evidence_dir, "test_direct.gif")
            self.assertTrue(os.path.isfile(target))
            with Image.open(target) as img:
                self.assertEqual(img.format, "GIF")
                self.assertEqual(img.n_frames, 3)
        finally:
            detector.close(timeout=1)

    def test_html_reporter_with_animated_clip_and_badge(self):
        incident = {
            "id": "inc_test_1",
            "map_name": "Phong Thần Đài",
            "glitch_type": "VÙNG ĐEN BẤT THƯỜNG",
            "coord_x": 180.5,
            "coord_y": 195.2,
            "description": "Thủng map kiểm tra",
            "status": "suspected",
            "severity": "CRITICAL",
            "severity_vi": "NGHIÊM TRỌNG",
            "clip_gif": "inc_test_1_clip.gif",
            "annotated_image": "inc_test_1_annotated.png",
            "evidence_state": "ready"
        }
        self.store.put_incident(incident)

        report_path = os.path.join(self.temp_dir, "report.html")
        reporter = HTMLReporter(store=self.store, output_html=report_path)
        output_file = reporter.generate()

        self.assertTrue(os.path.isfile(output_file))
        with open(output_file, "r", encoding="utf-8") as f:
            html_text = f.read()

        self.assertIn("NGHIÊM TRỌNG", html_text)
        self.assertIn("inc_test_1_clip.gif", html_text)
        self.assertIn("inc_test_1_annotated.png", html_text)
        self.assertIn("[Xem ảnh tĩnh HD]", html_text)

    def test_in_flight_glitch_inspection_during_continuous_run(self):
        from types import SimpleNamespace
        from core.map_traversal_engine import MapTraversalEngine
        from core.coverage_planner import CoveragePlan

        captured = []
        frame = self._create_synthetic_frame()

        controller = SimpleNamespace(
            config={"traversal": {"arrival_tolerance": 0.5, "vision_radius": 3.0}},
            adb_path="mock_adb", device_id="mock_dev",
            capture_frame=lambda max_age_seconds=1.0: frame,
            move_joystick=lambda angle, duration_ms=550: None,
            joystick_center=(384, 784)
        )

        # Telemetry progression towards destination with position_map_id and position_age
        positions = [
            {"position": (10.0, 10.0), "map_id": 1, "position_map_id": 1, "doing": "run", "doing_valid": True, "position_frame": 1, "position_age": 0},
            {"position": (11.0, 10.5), "map_id": 1, "position_map_id": 1, "doing": "run", "doing_valid": True, "position_frame": 2, "position_age": 0},
            {"position": (12.0, 11.0), "map_id": 1, "position_map_id": 1, "doing": "run", "doing_valid": True, "position_frame": 3, "position_age": 0},
            {"position": (13.0, 12.0), "map_id": 1, "position_map_id": 1, "doing": "run", "doing_valid": True, "position_frame": 4, "position_age": 0},
        ]
        pos_idx = [0]
        def get_telemetry():
            idx = min(pos_idx[0], len(positions) - 1)
            pos_idx[0] += 1
            return positions[idx]

        vision = SimpleNamespace(
            adb_path="mock_adb", device_id="mock_dev", controller=controller,
            get_engine_telemetry=get_telemetry
        )

        detector = GlitchDetector(evidence_dir=self.evidence_dir)
        try:
            detector_inspect_called = []
            orig_inspect = detector.inspect_frame_for_glitches
            def mock_inspect(f, *args, **kwargs):
                detector_inspect_called.append(True)
                return orig_inspect(f, *args, **kwargs)
            detector.inspect_frame_for_glitches = mock_inspect

            engine = MapTraversalEngine(controller, vision, detector, None, SimpleNamespace(store=self.store))
            atlas = np.full((192, 384, 3), 160, dtype=np.uint8)
            known = np.full(atlas.shape[:2], 255, dtype=np.uint8)
            engine.plan = CoveragePlan.build(1, [0, 0, 384, 192], atlas, known, {"strategy": "corners_first"})
            engine.is_running = True
            engine.current_map_id = 1
            engine.current_map_name = "Phong Thần Đài"

            # Mock clock that advances safely
            class AdvancingClock:
                def __init__(self):
                    self._t = 100.0
                def monotonic(self):
                    self._t += 0.8
                    return self._t
                def wait(self, dur):
                    return False
                def is_set(self):
                    return False
            
            adv_clock = AdvancingClock()
            engine._stop_event = adv_clock

            orig_monotonic = time.monotonic
            time.monotonic = adv_clock.monotonic

            try:
                target = {"id": "t1", "state": "pending"}
                outcome = engine._run_path_joystick_continuous(
                    target,
                    path=[[11.0, 10.5], [12.0, 11.0]],
                    destination=[13.0, 12.0],
                    tolerance=0.5,
                    max_total_seconds=100.0
                )
            finally:
                time.monotonic = orig_monotonic

            self.assertEqual(outcome, "arrived")
            self.assertGreater(len(detector_inspect_called), 0, "Glitch detector must be called in-flight")
        finally:
            detector.close(timeout=1)


if __name__ == "__main__":
    unittest.main()
