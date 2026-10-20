import unittest
from unittest.mock import MagicMock, patch
from types import SimpleNamespace
import numpy as np
import math

from core.coverage_planner import CoveragePlan
from core.map_traversal_engine import MapTraversalEngine
from core.obstacle_bypasser import ObstacleBypasser
from core.ld_controller import LDController, game_to_joystick_angle


class TestMovementAndMapFixes(unittest.TestCase):
    def setUp(self):
        # Create a simple 400x400 walkable atlas
        self.atlas = np.full((400, 400, 3), 160, dtype=np.uint8)
        self.known = np.full((400, 400), 255, dtype=np.uint8)

    def test_target_5_point_5_units_away_stays_pending(self):
        """
        Vấn đề 1: Tái hiện mốc cách 5.5 đơn vị (tolerance 1.0, vision 3.2, heading 1,0).
        Kiểm tra: Mốc chỉ được ghi nhận 'seen = True', KHÔNG ĐƯỢC chuyển thành 'done'.
        """
        plan = CoveragePlan.build(6, [0, 0, 200, 200], self.atlas, self.known,
                                  {"cell_size": 64, "strategy": "corners_first"})
        # Đặt một mốc giả lập tại (10.5, 6.0)
        test_target = {
            "id": "test_t1",
            "batch": 1,
            "position": [10.5, 6.0],
            "options": [[10.5, 6.0]],
            "state": "pending",
            "seen": False,
            "reached": False,
            "attempts": 0,
        }
        plan.data["targets"] = [test_target]

        char_pos = (5.0, 6.0)  # Khoảng cách tới mốc là 5.5 đơn vị
        heading = (1.0, 0.0)   # Nhìn thẳng về phía mốc
        plan.observe_position(char_pos, tolerance=1.0, vision_radius=3.2, heading=heading)

        # Mốc phải được đánh dấu nhìn thấy (seen = True) nhưng TUYỆT ĐỐI không phải là 'done'
        self.assertTrue(test_target.get("seen"), "Mốc trong nón nhìn phải được đánh dấu seen=True")
        self.assertEqual(test_target["state"], "pending", "Mốc cách 5.5 đơn vị (ngoài sai số 1.0) phải giữ trạng thái pending")
        self.assertFalse(test_target.get("reached"), "Mốc chưa tới đích thực sự (reached=False)")

        # Khi nhân vật thực sự bước tới khoảng cách <= tolerance (1.0)
        near_pos = (10.0, 6.0)  # Khoảng cách 0.5 <= 1.0
        plan.observe_position(near_pos, tolerance=1.0, vision_radius=3.2, heading=heading)
        self.assertEqual(test_target["state"], "done", "Khi nhân vật vào trong sai số tolerance=1.0, mốc mới được thành done")
        self.assertTrue(test_target.get("reached"), "Mốc được xác nhận reached=True khi tới đích thật")

    def test_wait_stopped_accepts_max_seconds_parameter(self):
        """
        Vấn đề 1: Sửa chữ ký hàm _wait_stopped(self, max_seconds=None).
        Trước đây truyền max_seconds=2.0 sẽ văng TypeError.
        """
        ctrl = MagicMock()
        vision = MagicMock()
        vision.get_engine_telemetry.return_value = {
            "position": (10.0, 10.0),
            "position_frame": 100,
            "position_age": 0.05,
            "in_game": True,
            "map_id": 6,
            "position_map_id": 6,
            "speed": 0.0,
            "is_moving": False
        }
        engine = MapTraversalEngine(ctrl, vision, None, None, None)
        engine.is_running = True
        engine.is_paused = False
        engine.current_map_id = 6

        # Lời gọi có max_seconds=2.0 không được ném Exception
        res = engine._wait_stopped(max_seconds=2.0)
        self.assertIsNotNone(res)
        self.assertEqual(res["position"], (10.0, 10.0))

    def test_phase_locking_corners_and_perimeter_before_inner_rings(self):
        """
        Vấn đề 2: Chế độ corners_first:
        - Các góc và chu vi là batch 1.
        - Khóa giai đoạn: Không được nhảy sang batch 2 khi batch 1 vẫn còn mốc 'pending'.
        """
        plan = CoveragePlan.build(6, [0, 0, 200, 200], self.atlas, self.known,
                                  {"cell_size": 40, "strategy": "corners_first"})
        targets = plan.data["targets"]

        # Kiểm tra mục tiêu đầu tiên là góc an toàn
        first_target = targets[0]
        self.assertTrue("khám phá" in first_target.get("purpose", ""), "Mục tiêu đầu tiên phải là góc biên")
        self.assertEqual(first_target["batch"], 1)

        # Kiểm tra phase locking: next_target phải trả về mục tiêu thuộc batch 1 nhỏ nhất còn pending
        target = plan.next_target(max_attempts=3)
        self.assertIsNotNone(target)
        self.assertEqual(target["batch"], 1, "next_target phải ưu tiên giải quyết hết batch 1")

        # Đánh dấu toàn bộ batch 1 thành done
        for t in targets:
            if t["batch"] == 1:
                t["state"] = "done"

        # Sau khi batch 1 đã được giải quyết, mới chuyển sang batch 2
        next_t = plan.next_target(max_attempts=3)
        if any(t["batch"] == 2 for t in targets):
            self.assertIsNotNone(next_t)
            self.assertEqual(next_t["batch"], 2, "Chỉ được chuyển sang batch 2 khi batch 1 đã giải quyết xong")

    def test_coordinate_system_in_obstacle_bypasser(self):
        """
        Vấn đề 3: Đảm bảo find_smart_exit xử lý hình học hoàn toàn trên tọa độ game (x, y),
        và chỉ đổi ra góc joystick màn hình khi trả về.
        """
        plan = CoveragePlan.build(6, [0, 0, 200, 200], self.atlas, self.known,
                                  {"cell_size": 64, "strategy": "corners_first"})
        bypasser = ObstacleBypasser(controller=MagicMock())

        curr_pos = (10.0, 10.0)
        dest_pos = (15.0, 10.0)  # Đích ở phía Đông (+X trên game coords: góc game 0 độ)
        expected_joystick_angle = game_to_joystick_angle(5.0, 0.0)

        # Giả sử góc đâm vào vật cản là 180 độ game (phía Tây)
        exit_angle = bypasser.find_smart_exit(curr_pos, current_heading_deg=180.0, plan=plan, destination=dest_pos)
        self.assertIsNotNone(exit_angle)
        # Góc joystick trả về phải hướng về phía đích (Đông)
        diff = abs((exit_angle - expected_joystick_angle + 180) % 360 - 180)
        self.assertLessEqual(diff, 60.0, "find_smart_exit phải trả về góc joystick màn hình chuẩn xác hướng tới đích")

    def test_touch_device_discovery_and_fallback_swipe_duration(self):
        """
        Vấn đề 1 (Cảm ứng):
        - LDController phát hiện thiết bị touch qua getevent -pl.
        - Thời gian swipe fallback là 160ms (tránh nghẽn hàng đợi trên chu kỳ 120ms).
        """
        ctrl = LDController(auto_connect=False)
        ctrl.adb_path = "adb.exe"
        ctrl.device_id = "emulator-5554"

        fake_getevent_output = (
            "add device 1: /dev/input/event1\n"
            "  name:     \"Power Button\"\n"
            "add device 2: /dev/input/event3\n"
            "  name:     \"Touchscreen\"\n"
            "  input props:\n"
            "    INPUT_PROP_DIRECT\n"
            "  0035  : value 0, min 0, max 1920, diff 0, flat 0, fuzz 0\n"  # ABS_MT_POSITION_X
            "  0036  : value 0, min 0, max 1080, diff 0, flat 0, fuzz 0\n"
        )
        fake_res = SimpleNamespace(stdout=fake_getevent_output)
        with patch("core.ld_controller.run_quiet", return_value=fake_res):
            dev = ctrl._detect_touch_device()
            self.assertEqual(dev, "/dev/input/event3", "Phải dò đúng thiết bị cảm ứng ABS_MT_POSITION_X")

        # Kiểm tra swipe duration trong joystick_steer fallback
        with patch.object(ctrl, "move_joystick") as mock_move:
            ctrl._touch_down = False
            ctrl.joystick_steer(45.0)
            mock_move.assert_called_once()
            _, kwargs = mock_move.call_args
            self.assertEqual(kwargs.get("duration_ms"), 160, "Fallback swipe duration phải là 160ms để tránh nghẽn hàng đợi")


if __name__ == "__main__":
    unittest.main()
