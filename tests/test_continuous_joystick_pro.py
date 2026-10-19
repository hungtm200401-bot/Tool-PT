import unittest
import math
from unittest.mock import MagicMock, patch
from types import SimpleNamespace

from core.ld_controller import LDController, game_to_joystick_angle
from core.map_traversal_engine import MapTraversalEngine
from core.coverage_planner import CoveragePlan
import numpy as np

class TestContinuousJoystickPro(unittest.TestCase):
    def setUp(self):
        self.config = {
            "joystick": {"center_x": 384, "center_y": 784, "radius": 120},
            "ui_elements": {},
            "traversal": {"arrival_tolerance": 0.8, "vision_radius": 3.2}
        }

    def test_joystick_press_steer_release_lifecycle(self):
        ctrl = LDController(auto_connect=False)
        ctrl.config = self.config
        ctrl.joystick_center = (384, 784)
        ctrl.joystick_radius = 120
        ctrl.fast_pipe_enabled = True

        mock_pipe = MagicMock()
        mock_pipe.stdin = MagicMock()
        mock_pipe.poll.return_value = None
        ctrl._shell_pipe = mock_pipe
        ctrl._shell_pipe_device = "test_dev"
        ctrl.adb_path = "mock_adb"
        ctrl.device_id = "test_dev"

        # 1. Press
        ctrl.joystick_press(0)  # 0 deg = right
        self.assertTrue(ctrl._touch_down)
        self.assertTrue(mock_pipe.stdin.write.called)
        first_call = mock_pipe.stdin.write.call_args[0][0].decode("utf-8")
        self.assertIn("sendevent /dev/input/event2 3 53 384", first_call)
        self.assertIn("sendevent /dev/input/event2 3 53 504", first_call)

        # 2. Steer (without releasing finger)
        mock_pipe.stdin.write.reset_mock()
        ctrl.joystick_steer(90)  # 90 deg = down (y = 784 + 120 = 904)
        self.assertTrue(ctrl._touch_down)
        steer_call = mock_pipe.stdin.write.call_args[0][0].decode("utf-8")
        self.assertIn("sendevent /dev/input/event2 3 54 904", steer_call)
        self.assertNotIn("330 0", steer_call)  # Finger must not be lifted!

        # 3. Release
        mock_pipe.stdin.write.reset_mock()
        ctrl.joystick_release()
        self.assertFalse(ctrl._touch_down)
        release_call = mock_pipe.stdin.write.call_args[0][0].decode("utf-8")
        self.assertIn("sendevent /dev/input/event2 1 330 0", release_call)
        self.assertIn("sendevent /dev/input/event2 3 57 -1", release_call)

    def test_engine_continuous_movement_uses_steer_and_release(self):
        controller = SimpleNamespace(
            config={"traversal": {"arrival_tolerance": 0.5, "vision_radius": 3.0}},
            adb_path="mock_adb", device_id="mock_dev",
            capture_frame=lambda max_age_seconds=1.0: None,
            joystick_press=MagicMock(),
            joystick_steer=MagicMock(),
            joystick_release=MagicMock(),
            joystick_center=(384, 784)
        )

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

        engine = MapTraversalEngine(controller, vision, None, None, SimpleNamespace(store=MagicMock()))
        atlas = np.full((192, 384, 3), 160, dtype=np.uint8)
        known = np.full(atlas.shape[:2], 255, dtype=np.uint8)
        engine.plan = CoveragePlan.build(1, [0, 0, 384, 192], atlas, known, {"strategy": "corners_first"})
        engine.is_running = True
        engine.current_map_id = 1
        engine.current_map_name = "Phong Thần Đài"

        target = {"id": "t1", "state": "pending"}
        outcome = engine._run_path_joystick_continuous(
            target,
            path=[[11.0, 10.5], [12.0, 11.0]],
            destination=[13.0, 12.0],
            tolerance=0.5,
            max_total_seconds=10.0
        )

        self.assertEqual(outcome, "arrived")
        self.assertTrue(controller.joystick_press.called, "Must press joystick at start")
        self.assertTrue(controller.joystick_steer.called, "Must steer continuously while moving")
        self.assertTrue(controller.joystick_release.called, "Must release joystick only when arrived")

    def test_game_to_joystick_angle_alignment(self):
        # Hệ isometric 2.5D của Phong Thần:
        # East / Phải (+X): góc joystick màn hình ~ 36.3°
        self.assertAlmostEqual(game_to_joystick_angle(2.5, 0.0), 36.26, places=1)
        # South / Xuống (+Y): góc joystick màn hình ~ 129.0°
        self.assertAlmostEqual(game_to_joystick_angle(0.0, 3.0), 129.04, places=1)
        # West / Trái (-X): góc joystick màn hình ~ 216.3°
        self.assertAlmostEqual(game_to_joystick_angle(-1.5, 0.0), 216.26, places=1)
        # North / Lên (-Y): góc joystick màn hình ~ 309.0°
        self.assertAlmostEqual(game_to_joystick_angle(0.0, -4.0), 309.04, places=1)


    def test_no_false_stall_on_telemetry_batching(self):
        # Simulate realistic telemetry where position only updates every 0.35s - 0.5s
        controller = SimpleNamespace(
            config={"traversal": {"arrival_tolerance": 0.5, "vision_radius": 3.0}},
            adb_path="mock_adb", device_id="mock_dev",
            capture_frame=lambda max_age_seconds=1.0: None,
            joystick_press=MagicMock(),
            joystick_steer=MagicMock(),
            joystick_release=MagicMock(),
            joystick_center=(384, 784)
        )

        # 4 identical frames simulating a 0.4s telemetry delay before moving to destination
        positions = [
            {"position": (10.0, 10.0), "map_id": 1, "position_map_id": 1, "doing": "run", "doing_valid": True, "position_frame": 1, "position_age": 0},
            {"position": (10.0, 10.0), "map_id": 1, "position_map_id": 1, "doing": "run", "doing_valid": True, "position_frame": 1, "position_age": 0},
            {"position": (10.0, 10.0), "map_id": 1, "position_map_id": 1, "doing": "run", "doing_valid": True, "position_frame": 1, "position_age": 0},
            {"position": (10.0, 10.0), "map_id": 1, "position_map_id": 1, "doing": "run", "doing_valid": True, "position_frame": 1, "position_age": 0},
            {"position": (11.5, 10.0), "map_id": 1, "position_map_id": 1, "doing": "run", "doing_valid": True, "position_frame": 2, "position_age": 0},
            {"position": (13.0, 10.0), "map_id": 1, "position_map_id": 1, "doing": "run", "doing_valid": True, "position_frame": 3, "position_age": 0},
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

        engine = MapTraversalEngine(controller, vision, None, None, SimpleNamespace(store=MagicMock()))
        atlas = np.full((192, 384, 3), 160, dtype=np.uint8)
        known = np.full(atlas.shape[:2], 255, dtype=np.uint8)
        engine.plan = CoveragePlan.build(1, [0, 0, 384, 192], atlas, known, {"strategy": "corners_first"})
        engine.is_running = True
        engine.current_map_id = 1
        engine.current_map_name = "Phong Thần Đài"

        target = {"id": "t1", "state": "pending"}
        outcome = engine._run_path_joystick_continuous(
            target,
            path=[[11.5, 10.0]],
            destination=[13.0, 10.0],
            tolerance=0.5,
            max_total_seconds=10.0
        )

        self.assertEqual(outcome, "arrived", "Should not stall due to 0.4s file update latency")
        self.assertFalse(hasattr(engine, "_blocked_sectors") and len(engine._blocked_sectors) > 0)

if __name__ == "__main__":
    unittest.main()


