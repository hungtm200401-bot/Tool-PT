import math
import os
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

import numpy as np

from core.coverage_planner import CoveragePlan
from core.map_traversal_engine import MapTraversalEngine
from core.runtime_store import RuntimeStore


def plan_for_test():
    image = np.full((192, 384, 3), 160, dtype=np.uint8)
    return CoveragePlan.build(1, [0, 0, 384, 192], image,
                              np.full(image.shape[:2], 255, dtype=np.uint8), {"cell_size": 64})


def stopped(position=(12.0, 6.0), map_id=1):
    return {"map_id": map_id, "position_map_id": map_id, "position": position,
            "position_frame": 1, "position_age": 0, "doing": "stand", "doing_valid": True}


class PlannerRecoveryTests(unittest.TestCase):
    def test_shortcut_preserves_astar_detour_around_expensive_terrain(self):
        plan = plan_for_test()
        plan.terrain_cost[:20, 20:22] = 50

        route = plan.route_to((2, 4), (20, 4))

        self.assertIsNotNone(route)
        self.assertGreaterEqual(max(point[1] for point in route), 10)
        self.assertEqual(route[-1], [20, 4])

    def test_reverse_trail_keeps_the_corner_instead_of_pinning_across_it(self):
        plan = plan_for_test()
        plan.data["trace"] = [[1, 1], [1, 2], [1, 3], [2, 3], [3, 3]]

        route = plan.verified_return_path((3, 3), min_distance=2.5)

        self.assertEqual(route, [[1, 3], [1, 1]])
        self.assertTrue(all(math.dist(a, b) <= 2 for a, b in zip([(3, 3)]+route, route)))

    def test_reverse_trail_never_crosses_a_trace_break_or_position_jump(self):
        plan = plan_for_test()
        plan.data["trace"] = [[1, 1], [1, 2], None, [8, 8], [8, 9]]
        self.assertEqual(plan.verified_return_path((8, 9)), [])
        plan.data["trace"] = [[1, 1], [8, 8], [8, 9]]
        self.assertEqual(plan.verified_return_path((8, 9)), [])
        self.assertEqual(plan.verified_return_path((9, 10)), [])

    def test_stall_budget_survives_save_and_reload_without_completing_targets(self):
        plan = plan_for_test()
        before = [point["state"] for point in plan.data["targets"]]
        plan.record_stall((12, 6), (17, 6))
        plan.record_stall((13, 6), (18, 7))
        with tempfile.TemporaryDirectory() as directory:
            plan.save(directory)
            restored = CoveragePlan.load(directory, 1)
        self.assertIsNotNone(restored.stalled_area((12, 6)))
        self.assertEqual([point["state"] for point in restored.data["targets"]], before)
        self.assertIsNone(restored.stalled_area((20, 6)))

    def test_new_verified_progress_resets_the_consecutive_failure_budget(self):
        plan = plan_for_test()
        plan.record_stall((12, 6), (17, 6))
        plan.data["targets"][0]["state"] = "done"

        area = plan.record_stall((12, 6), (18, 6))

        self.assertEqual(area["failures"], 1)
        self.assertIsNone(plan.stalled_area((12, 6)))

    def test_temporary_failure_memory_expires(self):
        plan = plan_for_test()
        with patch("core.coverage_planner.time.time", return_value=1000):
            plan.record_stall((12, 6), (17, 6), duration=60)
            plan.record_stall((12, 6), (18, 6), duration=60)
        with patch("core.coverage_planner.time.time", return_value=1061):
            self.assertIsNone(plan.stalled_area((12, 6)))


class EngineRecoveryTests(unittest.TestCase):
    def engine(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        store = RuntimeStore(os.path.join(directory.name, "runtime.sqlite3"))
        ctrl = SimpleNamespace(adb_path="test", device_id="device", config={"traversal": {}},
                               move_joystick=Mock(), cancel_movement=Mock())
        vision = SimpleNamespace(get_engine_telemetry=Mock(return_value=stopped()))
        engine = MapTraversalEngine(ctrl, vision, None, None, SimpleNamespace(store=store))
        engine.plan = plan_for_test()
        engine.current_map_id = 1
        engine.is_running = True
        engine._wait_stopped = Mock(return_value=stopped())
        engine._save_progress = Mock()
        engine._publish = Mock()
        engine.surveyor.pin = Mock()
        return engine

    def test_saturated_stall_area_stops_before_another_pin(self):
        engine = self.engine()
        engine.plan.data["targets"] = [engine.plan.data["targets"][0]]
        engine.plan.data["targets"][0].update(state="pending", options=[[2, 2]])
        engine.plan.record_stall((12, 6), (17, 6))
        engine.plan.record_stall((12, 6), (18, 6))

        result = engine._cover_map()

        self.assertEqual(result, "blocked")
        self.assertEqual(engine.route_phase, "partial")
        self.assertIn("2 lần", engine.plan.data["blocked_reason"])
        self.assertNotEqual(engine.plan.data["targets"][0]["state"], "done")
        engine.surveyor.pin.assert_not_called()
        engine.ctrl.move_joystick.assert_not_called()

    def test_two_failed_targets_in_one_area_do_not_trigger_a_third_attempt(self):
        engine = self.engine()
        targets = engine.plan.data["targets"][:2]
        for index, target in enumerate(targets):
            target.update(state="pending", options=[[2+index, 2], [2+index, 3]])
        engine.plan.data["targets"] = targets
        engine.plan.route_to = Mock(return_value=[[3, 3]])
        engine._walk_target = Mock(return_value="retry")
        engine._backtrack_from_obstacle = Mock(return_value="unavailable")

        result = engine._cover_map()

        self.assertEqual(result, "blocked")
        self.assertEqual(engine._walk_target.call_count, 2)
        engine._backtrack_from_obstacle.assert_called_once()
        self.assertFalse(any(point["state"] == "done" for point in targets))

    def test_recovery_follows_verified_turns_and_does_not_open_the_map(self):
        engine = self.engine()
        engine.plan.data["trace"] = [[4, 2], [4, 3], [5, 3], [6, 3], [6, 4], [6, 5]]
        engine._wait_stopped.side_effect = [stopped((6, 5)), stopped((6, 5)),
                                             stopped((6, 3)), stopped((4, 3))]
        engine._walk_joystick_direct = Mock(return_value="arrived")

        result = engine._backtrack_from_obstacle()

        self.assertEqual(result, "escaped")
        destinations = [call.args[1] for call in engine._walk_joystick_direct.call_args_list]
        self.assertEqual(destinations, [[6, 3], [4, 3], [4, 2]])
        engine.surveyor.pin.assert_not_called()

    def test_recovery_aborts_as_soon_as_the_map_changes(self):
        engine = self.engine()
        engine._wait_stopped.return_value = stopped(map_id=2)
        self.assertEqual(engine._backtrack_from_obstacle(), "map_changed")
        engine.ctrl.move_joystick.assert_not_called()
        engine.surveyor.pin.assert_not_called()

    def test_stop_interrupts_joystick_wait_without_reading_or_sending_more(self):
        engine = self.engine()
        engine.vision.get_engine_telemetry.return_value = stopped((0, 0))
        engine._stop_event = SimpleNamespace(wait=lambda _: setattr(engine, "is_running", False))

        result = engine._walk_joystick_direct({"id": "target"}, (2, 0))

        self.assertEqual(result, "interrupted")
        engine.ctrl.move_joystick.assert_called_once()
        engine.vision.get_engine_telemetry.assert_called_once()
        self.assertTrue(engine._movement_may_be_active)

    def test_stop_waits_for_queued_cancel_before_claiming_stationary(self):
        engine = self.engine()
        engine.profile = "test"
        engine._movement_may_be_active = True
        engine._configure_profile = Mock()
        engine._prepare_plan = Mock()
        engine._cover_map = Mock(return_value="interrupted")
        pending = SimpleNamespace(is_alive=Mock(side_effect=[True, False]), join=Mock())
        engine._stop_cancel_thread = pending
        engine._cancel_and_verify = Mock(side_effect=lambda: pending.join.assert_called_once())

        engine._run_loop()

        pending.join.assert_called_once_with(timeout=10)
        engine._cancel_and_verify.assert_called_once()
        self.assertEqual(engine.route_phase, "stopped")

    def test_interrupted_input_does_not_announce_stopped_before_verification(self):
        engine = self.engine()
        engine.profile = "test"
        engine._movement_may_be_active = True
        engine._configure_profile = Mock()
        engine._prepare_plan = Mock()
        engine._cover_map = Mock(side_effect=InterruptedError())
        engine._cancel_and_verify = Mock(
            side_effect=lambda: self.assertEqual(engine.route_phase, "stopping"))

        engine._run_loop()

        engine._cancel_and_verify.assert_called_once()
        self.assertEqual(engine.route_phase, "stopped")


if __name__ == "__main__":
    unittest.main()
