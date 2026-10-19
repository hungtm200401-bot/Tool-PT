import os
import tempfile
import threading
import unittest
from types import SimpleNamespace
from unittest.mock import Mock

import numpy as np

from core.coverage_planner import CoveragePlan
from core.map_traversal_engine import MapTraversalEngine
from core.runtime_store import RuntimeStore


def make_plan():
    atlas = np.full((192, 384, 3), 160, dtype=np.uint8)
    known = np.full(atlas.shape[:2], 255, dtype=np.uint8)
    return CoveragePlan.build(1, [0, 0, 384, 192], atlas, known, {"cell_size": 64})


def sample_for(map_id):
    return {
        "map_id": map_id,
        "position_map_id": map_id,
        "position_frame": 1,
        "position_age": 0,
        "position": (5.0, 5.0),
        "doing": "stand",
        "doing_valid": True,
        "player_identity": None,
        "map_name": f"Map {map_id}",
    }


class MapSafetyTests(unittest.TestCase):
    def make_engine(self):
        directory = tempfile.TemporaryDirectory(prefix="map_safety_")
        self.addCleanup(directory.cleanup)
        store = RuntimeStore(os.path.join(directory.name, "runtime.sqlite3"))
        controller = SimpleNamespace(
            config={"traversal": {}, "navigation": {"connections": [], "world_slot_overrides": {}}},
            adb_path="test-adb",
            device_id="test-device",
            cancel_movement=Mock(),
        )
        vision = SimpleNamespace(adb_path=None, device_id=None,
                                 get_engine_telemetry=Mock(return_value=sample_for(1)))
        engine = MapTraversalEngine(controller, vision, None, None, SimpleNamespace(store=store))
        engine.plan = make_plan()
        engine.progress_path = os.path.join(directory.name, "progress.json")
        engine.route_directory = os.path.join(directory.name, "routes")
        engine._save_progress = Mock()
        return engine

    def test_unexpected_portal_records_hazard_and_returns_to_unfinished_map(self):
        engine = self.make_engine()
        source = engine.catalog[0]
        destination = engine.catalog[1]
        engine.current_map_id = source["id"]
        engine.current_map_name = source["name"]
        engine.current_target = engine.plan.data["targets"][0]
        engine.current_target.update({"id": "target-1", "destination": [8.0, 5.0], "state": "active"})
        engine.plan.data["active_id"] = "target-1"
        engine._leg = {"to": [8.0, 5.0]}
        engine._last_source_position = [5.0, 5.0]
        engine._navigate_world_slot = Mock(return_value=True)
        engine._wait_stopped = Mock(return_value=sample_for(source["id"]))

        handled = engine._handle_unexpected_map_change(sample_for(destination["id"]))

        self.assertTrue(handled)
        self.assertIsNone(engine.pending_map_return)
        self.assertEqual(engine.current_map_id, source["id"])
        self.assertEqual(engine._navigate_world_slot.call_args.args, (source, source))
        self.assertEqual(engine.current_target["state"], "retry")
        self.assertIsNone(engine.plan.data["active_id"])
        marked = [item for item in engine.plan.data["obstacles"]
                  if item["reason"] == "unexpected map transition; temporary portal avoidance"]
        self.assertGreater(len(marked), 1)
        self.assertEqual(engine._map_results[str(source["id"])]["state"], "partial")

    def test_failed_return_keeps_source_checkpoint_and_stops_partial(self):
        engine = self.make_engine()
        source = engine.catalog[0]
        destination = engine.catalog[1]
        engine.current_map_id = source["id"]
        engine.current_map_name = source["name"]
        engine._last_source_position = [5.0, 5.0]
        engine._navigate_world_slot = Mock(return_value=False)

        handled = engine._handle_unexpected_map_change(sample_for(destination["id"]))

        self.assertFalse(handled)
        self.assertEqual(engine.pending_map_return, source["id"])
        self.assertEqual(engine.current_map_id, source["id"])
        self.assertEqual(engine.route_phase, "partial")
        engine._save_progress.assert_called()

    def test_unverified_map_after_transition_is_saved_without_resuming(self):
        engine = self.make_engine()
        source = engine.catalog[0]
        engine.current_map_id = source["id"]
        engine.current_map_name = source["name"]
        invalid = {"map_id": engine.catalog[1]["id"], "position": None}

        handled = engine._handle_unexpected_map_change(invalid)

        self.assertFalse(handled)
        self.assertEqual(engine.pending_map_return, source["id"])
        engine._navigate_world_slot = Mock()
        engine._navigate_world_slot.assert_not_called()

    def test_run_stops_on_current_map_when_any_route_target_was_not_reached(self):
        engine = self.make_engine()
        source = engine.catalog[0]
        engine.current_map_id = source["id"]
        engine.current_map_name = source["name"]
        engine.profile = "test-profile"
        engine.plan.data["targets"] = [
            {"id": "a", "state": "done"},
            {"id": "b", "state": "done"},
            {"id": "c", "state": "done"},
            {"id": "d", "state": "deferred"},
        ]
        engine._configure_profile = Mock()
        engine._prepare_plan = Mock()
        engine._cover_map = Mock(return_value="finished")
        engine._wait_active = Mock(return_value=True)
        engine._cancel_and_verify = Mock(return_value=sample_for(source["id"]))
        engine._navigate_to_map_via_link = Mock(return_value=True)

        engine._run_loop()

        self.assertEqual(engine.route_phase, "partial")
        self.assertEqual(engine._map_results[str(source["id"])]["state"], "partial")
        self.assertIn("1 mốc chưa tới", engine._map_results[str(source["id"])]["reason"])
        engine._navigate_to_map_via_link.assert_not_called()

    def test_legacy_visited_map_is_reopened_if_saved_targets_are_incomplete(self):
        engine = self.make_engine()
        map_id = engine.plan.data["map_id"]
        engine.plan.data["targets"][-1]["state"] = "deferred"
        engine.plan.save(engine.route_directory, engine.store)
        engine.visited_maps = {map_id}
        engine._map_results = {str(map_id): {"name": "Map cũ", "state": "complete"}}

        engine._reconcile_saved_completions()

        self.assertNotIn(map_id, engine.visited_maps)
        self.assertEqual(engine._map_results[str(map_id)]["state"], "partial")

    def test_inspection_calibration_updates_settings_and_current_plan(self):
        engine = self.make_engine()

        result = engine.update_inspection_calibration(6.5, True, [6.5, 7.0, 6.0, 6.8])

        self.assertEqual(result, {"radius": 6.0, "calibrated": True})
        self.assertEqual(engine.settings["inspection_radius_samples"], [6.5, 7.0, 6.0, 6.8])
        self.assertEqual(engine.plan.data["inspection_radius"], 6.0)
        self.assertTrue(engine.plan.data["inspection_calibrated"])

    def test_inspection_calibration_requires_four_real_measurements(self):
        engine = self.make_engine()

        with self.assertRaisesRegex(ValueError, "4 vị trí"):
            engine.update_inspection_calibration(6.5, True, [6.5, 6.0, 7.0])
        with self.assertRaisesRegex(ValueError, "4 số đo"):
            engine.update_inspection_calibration(6.5, True)

    def test_inspection_calibration_uses_smallest_valid_measurement(self):
        self.assertEqual(
            MapTraversalEngine.conservative_inspection_radius([7.0, 6.25, 8.0, 6.75]), 6.25
        )

    def test_inspection_calibration_rejects_unmeasured_values(self):
        engine = self.make_engine()

        with self.assertRaises(ValueError):
            engine.update_inspection_calibration(0, True)
        with self.assertRaises(ValueError):
            engine.update_inspection_calibration(101, True)
        engine.is_running = True
        with self.assertRaises(RuntimeError):
            engine.update_inspection_calibration(6, True)

    def test_stop_sends_immediate_cancel_when_session_is_bound(self):
        engine = self.make_engine()
        engine.is_running = True
        engine._bound = True
        engine._stop_event = threading.Event()
        engine._phase("walking")

        engine.stop()
        engine._stop_cancel_thread.join(timeout=2)

        engine.ctrl.cancel_movement.assert_called_once()

    def test_stop_during_startup_does_not_send_movement_cancel(self):
        engine = self.make_engine()
        engine.is_running = True
        engine._bound = True
        engine._stop_event = threading.Event()

        engine.stop()

        engine.ctrl.cancel_movement.assert_not_called()

    def test_startup_resolution_error_does_not_send_movement_cancel(self):
        engine = self.make_engine()
        engine.ctrl.ensure_connection = Mock()
        engine.ctrl.connection_status = "connected"
        engine.ctrl.lock_session = Mock()
        engine.ctrl.unlock_session = Mock()
        engine.ctrl.calibrate_resolution = Mock(side_effect=RuntimeError("resolution unavailable"))

        engine._run_loop()

        self.assertEqual(engine.route_phase, "error")
        engine.ctrl.cancel_movement.assert_not_called()
        engine.ctrl.unlock_session.assert_called_once()

    def test_startup_rejects_stale_position_before_loading_or_moving(self):
        engine = self.make_engine()
        engine.vision.get_engine_telemetry.return_value = {
            **sample_for(1), "position_age": 3600, "in_game": False
        }
        engine._configure_profile = Mock()
        engine._cancel_and_verify = Mock()

        engine._run_loop()

        self.assertEqual(engine.route_phase, "error")
        engine._configure_profile.assert_not_called()
        engine._cancel_and_verify.assert_not_called()
        engine.ctrl.cancel_movement.assert_not_called()

    def test_portal_avoidance_marks_a_small_neighborhood(self):
        plan = make_plan()

        plan.note_obstacle(
            (5.0, 5.0), (9.0, 5.0), duration=600,
            reason="portal hazard", radius=2
        )

        cells = {tuple(item["cell"]) for item in plan.data["obstacles"]}
        self.assertEqual(len(cells), 13)

    def test_portal_at_destination_is_marked_even_when_distance_is_zero(self):
        plan = make_plan()

        plan.note_obstacle(
            (5.0, 5.0), (5.0, 5.0), duration=600,
            reason="portal hazard", radius=2
        )

        self.assertEqual(len(plan.data["obstacles"]), 13)

    def test_pending_return_is_written_to_durable_checkpoint(self):
        engine = self.make_engine()
        engine.profile = "test-profile"
        engine.current_map_id = engine.catalog[0]["id"]
        engine.pending_map_return = engine.current_map_id
        engine._save_progress = MapTraversalEngine._save_progress.__get__(engine)

        engine._save_progress()

        saved = engine.store.load_checkpoint("mission:test-profile")
        self.assertEqual(saved["pending_map_return"], engine.current_map_id)


if __name__ == "__main__":
    unittest.main()
