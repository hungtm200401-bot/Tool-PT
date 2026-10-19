import tempfile
import unittest
from unittest.mock import patch
from unittest.mock import Mock
from types import SimpleNamespace
import math
import os

import numpy as np

from core.coverage_planner import CoveragePlan, MapSurveyor
from core.map_traversal_engine import MapTraversalEngine
from core.vision_engine import VisionEngine
from core.runtime_store import RuntimeStore


def make_plan():
    atlas = np.full((192, 384, 3), 160, dtype=np.uint8)
    known = np.full(atlas.shape[:2], 255, dtype=np.uint8)
    return CoveragePlan.build(10, [0, 0, 384, 192], atlas, known,
                              {"cell_size": 64, "batch_rows": 1, "strategy": "expanding_rings"})


class PlannerTests(unittest.TestCase):
    def test_path_turns_around_a_wall_instead_of_crossing_it(self):
        atlas = np.full((192, 384, 3), 160, dtype=np.uint8)
        atlas[30:150, 160:184] = 20
        known = np.full(atlas.shape[:2], 255, dtype=np.uint8)
        plan = CoveragePlan.build(10, [0, 0, 384, 192], atlas, known, {"cell_size": 64, "strategy": "expanding_rings"})
        path = plan.route_to((5, 5), (16, 5))
        self.assertIsNotNone(path)
        self.assertTrue(any(y < 30/16 or y > 150/16 for x, y in path))
        for start, end in zip(path, path[1:]):
            for fraction in np.linspace(0, 1, 50):
                x = round((start[0]+(end[0]-start[0])*fraction)*16)
                y = round((start[1]+(end[1]-start[1])*fraction)*16)
                self.assertFalse(160 <= x < 184 and 30 <= y < 150)

    def test_rings_expand_in_clockwise_order(self):
        plan = make_plan()
        points = plan.data["targets"]
        self.assertEqual(plan.data["strategy"], "expanding_rings")
        self.assertEqual([point["batch"] for point in points], sorted(point["batch"] for point in points))
        for ring in {point["batch"] for point in points}:
            angles = [point["angle"] for point in points if point["batch"] == ring]
            self.assertEqual(angles, sorted(angles))
        self.assertEqual(points[0]["purpose"], "mốc gốc")

    def test_corners_first_traverses_perimeter_and_corners_before_inner_rings(self):
        atlas = np.full((192, 384, 3), 160, dtype=np.uint8)
        known = np.full(atlas.shape[:2], 255, dtype=np.uint8)
        plan = CoveragePlan.build(10, [0, 0, 384, 192], atlas, known,
                                  {"cell_size": 64, "strategy": "corners_first"})
        self.assertEqual(plan.data["strategy"], "corners_first")
        targets = plan.data["targets"]
        self.assertTrue(targets[0]["purpose"].startswith("khám phá góc"))
        self.assertEqual(targets[0]["batch"], 1)
        # Batch 1 must be corners and perimeter
        batch1 = [t for t in targets if t["batch"] == 1]
        self.assertTrue(len(batch1) > 0)
        self.assertTrue(all(t["is_perimeter"] for t in batch1))
        self.assertTrue(all("quét góc & viền mép" in t["purpose"] or "khám phá góc" in t["purpose"] for t in batch1))
        # Inner rings must have batch > 1
        inner = [t for t in targets if t["batch"] > 1]
        self.assertTrue(len(inner) > 0)
        self.assertTrue(all("bên trong" in t["purpose"] or "tâm bản đồ" in t["purpose"] for t in inner))
        # Verify execution order: Batch 1 comes before Batch 2
        batches = [t["batch"] for t in targets]
        self.assertEqual(batches, sorted(batches))

    def test_corners_first_perimeter_points_follow_continuous_order(self):
        atlas = np.full((192, 384, 3), 160, dtype=np.uint8)
        known = np.full(atlas.shape[:2], 255, dtype=np.uint8)
        plan = CoveragePlan.build(10, [0, 0, 384, 192], atlas, known,
                                  {"cell_size": 64, "strategy": "corners_first"})
        batch1 = [t for t in plan.data["targets"] if t["batch"] == 1 and "quét góc & viền mép" in t["purpose"]]
        sequences = [t["sequence"] for t in batch1]
        self.assertEqual(sequences, sorted(sequences))

    def test_arrived_points_do_not_prove_uncalibrated_image_coverage(self):
        plan = make_plan()
        for point in plan.data["targets"]:
            point["state"] = "done"
        self.assertFalse(plan.complete())
        self.assertFalse(plan.coverage()["inspection_calibrated"])

    def test_deferred_points_do_not_count_as_a_completed_route(self):
        plan = make_plan()
        plan.data["targets"] = [
            {"id": "a", "state": "done"},
            {"id": "b", "state": "done"},
            {"id": "c", "state": "done"},
            {"id": "d", "state": "deferred"},
        ]

        self.assertFalse(plan.is_route_complete())

    def test_route_is_complete_only_when_every_target_was_reached(self):
        plan = make_plan()
        for point in plan.data["targets"]:
            point["state"] = "done"

        self.assertTrue(plan.is_route_complete())
        self.assertFalse(plan.complete())  # Visual coverage still needs calibration.

    def test_blank_and_unobserved_regions_are_not_targets(self):
        atlas = np.full((192, 384, 3), 255, dtype=np.uint8)
        atlas[16:170, 16:170] = 160
        known = np.full(atlas.shape[:2], 255, dtype=np.uint8)
        known[:, 90:180] = 0
        plan = CoveragePlan.build(10, [0, 0, 384, 192], atlas, known, {"cell_size": 64})
        for target in plan.data["targets"]:
            for x, y in target["options"]:
                self.assertLess(x * 16, 90)
                self.assertLess(y * 16, 170)

    def test_teleport_does_not_complete_cells_between_samples(self):
        plan = make_plan()
        first, middle = plan.data["targets"][:2]
        plan.observe_position(first["options"][0], 0.3)
        plan.observe_position((100, 100), 0.3)
        self.assertEqual(first["state"], "done")
        self.assertEqual(middle["state"], "pending")
        self.assertIn(None, plan.data["trace"])

    def test_verified_travel_segment_is_recorded_in_coverage_mask(self):
        plan = make_plan()
        plan.observe_position((4.0, 4.0), 0.1)
        plan.observe_position((5.0, 4.0), 0.1)
        midpoint = (round(4.5 * 16), round(4.0 * 16))
        self.assertEqual(int(plan.visited[midpoint[1], midpoint[0]]), 1)
        rendered = plan.render()
        self.assertEqual(rendered.shape[2], 3)

    def test_live_survey_preview_dims_unobserved_regions(self):
        atlas = np.full((32, 48, 3), 140, dtype=np.uint8)
        known = np.zeros((32, 48), dtype=np.uint8)
        known[:, :24] = 255
        preview = MapSurveyor.render_survey_preview(atlas, known)
        self.assertEqual(preview.shape, (32, 48, 3))
        self.assertGreater(int(preview[16, 12, 1]), int(preview[16, 36, 1]))

    def test_retries_in_current_batch_precede_the_next_batch(self):
        plan = make_plan()
        batch = [point for point in plan.data["targets"] if point["batch"] == 0]
        for point in batch:
            point["state"] = "done"
        batch[-1]["state"] = "retry"
        self.assertIs(plan.next_target(3), batch[-1])

    def test_resume_keeps_interrupted_target_before_other_pending_points(self):
        plan = make_plan()
        target = plan.data["targets"][2]
        target["state"] = "retry"
        plan.data["resume_target_id"] = target["id"]
        self.assertIs(plan.next_target(3), target)

    def test_restart_keeps_active_target_as_first_work(self):
        plan = make_plan()
        target = plan.data["targets"][2]
        target["state"] = "active"
        plan.data["active_id"] = target["id"]
        with tempfile.TemporaryDirectory(prefix="resume_target_") as directory:
            plan.save(directory)
            resumed = CoveragePlan.load(directory, 10)
        self.assertEqual(resumed.next_target(3)["id"], target["id"])

    def test_resume_preserves_done_and_recovers_interrupted_leg(self):
        plan = make_plan()
        plan.data["targets"][0]["state"] = "done"
        plan.data["targets"][1]["state"] = "active"
        with tempfile.TemporaryDirectory(prefix="coverage_plan_") as directory:
            plan.save(directory)
            resumed = CoveragePlan.load(directory, 10)
        self.assertEqual(resumed.data["targets"][0]["state"], "done")
        self.assertEqual(resumed.data["targets"][1]["state"], "pending")
        self.assertIsNone(resumed.data["active_id"])

    def test_observed_obstacle_survives_resume(self):
        plan = make_plan()
        plan.note_obstacle((4, 4), (8, 4))
        self.assertTrue(plan.data["obstacles"])
        row, col = plan.data["obstacles"][0]["cell"]
        with tempfile.TemporaryDirectory(prefix="coverage_obstacle_") as directory:
            plan.save(directory)
            resumed = CoveragePlan.load(directory, 10)
        self.assertFalse(resumed.navigation[row, col])

    def test_temporary_stall_obstacle_expires(self):
        plan = make_plan()
        with patch("core.coverage_planner.time.time", return_value=1000):
            plan.note_obstacle((4, 4), (8, 4))
        row, col = plan.data["obstacles"][0]["cell"]
        self.assertFalse(plan.navigation[row, col])
        with patch("core.coverage_planner.time.time", return_value=1121):
            plan._refresh_obstacles()
        self.assertTrue(plan.navigation[row, col])
        self.assertFalse(plan.data["obstacles"])

    def test_game_pixel_to_map_tap_uses_reported_cover(self):
        telemetry = {"map_id": 10, "map_data": {"surface": {
            "pic": [1920, 2720, 1536, 896], "cover": [2275, 2889, 640, 380]
        }}}
        calls = []
        controller = SimpleNamespace(
            config={}, tap=lambda *args, **kwargs: calls.append(args),
            close_map_dialog=lambda: None
        )
        surveyor = MapSurveyor(controller, None, {}, lambda: True, lambda _: None)
        surveyor.open_map = lambda: telemetry
        surveyor.pan_to = lambda *args: telemetry
        surveyor.close_map = lambda: None
        # Actual map surface sample: its centre is (2595, 3079) map pixels.
        surveyor.pin(2595/16, 3079/16, 10)
        self.assertEqual(calls, [(1100, 543)])

    def test_pan_to_swipe_stays_within_safe_viewport_bounds(self):
        swipes = []
        controller = SimpleNamespace(
            config={}, swipe=lambda *args, **kwargs: swipes.append(args),
            close_map_dialog=lambda: None
        )
        telemetry = {
            "map_id": 10, "map_dialog_open": True, "map_frame": 1,
            "map_data": {"surface": {"have_pic": 1, "pic_pending": 0,
                                     "pic": [0, 0, 4000, 4000], "cover": [2000, 2000, 400, 400]}}
        }
        after_telemetry = {
            "map_id": 10, "map_dialog_open": True, "map_frame": 2,
            "map_data": {"surface": {"have_pic": 1, "pic_pending": 0,
                                     "pic": [0, 0, 4000, 4000], "cover": [1000, 1000, 400, 400]}}
        }
        samples = [telemetry, after_telemetry, after_telemetry]
        surveyor = MapSurveyor(controller, None, {}, lambda: True, lambda _: None)
        surveyor.read_map = lambda: samples.pop(0) if samples else after_telemetry
        # Extreme target (0, 0) relative to cover (2000, 2000)
        surveyor.pan_to(1000, 1000, 10)
        self.assertTrue(len(swipes) >= 1)
        sx1, sy1, sx2, sy2 = swipes[0][:4]
        # Viewport is [408, 132, 1792, 954]. Safe box is ~[616, 255, 1584, 831].
        self.assertGreaterEqual(sx1, 408)
        self.assertLessEqual(sx1, 1792)
        self.assertGreaterEqual(sx2, 600)
        self.assertLessEqual(sx2, 1600)
        self.assertGreaterEqual(sy2, 240)
        self.assertLessEqual(sy2, 850)
        # Verify it stays far away from close button (1830, 71)
        self.assertLess(sx2, 1800)
        self.assertGreater(sy2, 100)

    def test_pan_to_reopens_map_if_dialog_unexpectedly_closed(self):
        controller = SimpleNamespace(config={}, swipe=lambda *a, **k: None)
        closed_telemetry = {"map_id": 10, "map_dialog_open": False}
        open_telemetry = {
            "map_id": 10, "map_dialog_open": True, "map_frame": 5,
            "map_data": {"surface": {"have_pic": 1, "pic_pending": 0,
                                     "pic": [0, 0, 2000, 2000], "cover": [500, 500, 200, 200]}}
        }
        reopened = []
        vision = SimpleNamespace(get_engine_telemetry=lambda: closed_telemetry)
        surveyor = MapSurveyor(controller, vision, {}, lambda: True, lambda _: None)
        call_count = [0]
        def fake_read():
            call_count[0] += 1
            if call_count[0] == 1:
                raise RuntimeError("Map dialog closed")
            return open_telemetry
        surveyor.read_map = fake_read
        surveyor.open_map = lambda: (reopened.append(True) or open_telemetry)
        res = surveyor.pan_to(500, 500, 10)
        self.assertEqual(res["map_id"], 10)
        self.assertTrue(reopened)

    def test_local_map_is_open_even_when_world_tab_is_closed(self):
        replies = [
            SimpleNamespace(stdout='{"frames": 20, "nodes": {"map": 24}, "world": {"up": 0, "player_map": 10}}'),
            SimpleNamespace(stdout='{"frames": 19, "sub_world_id": 10, "player": {"mps": [41521,98551], "doing": "stand"}}')
        ]
        with patch("subprocess.run", side_effect=replies):
            telemetry = VisionEngine("adb", "test-device").get_engine_telemetry()
        self.assertTrue(telemetry["map_dialog_open"])
        self.assertTrue(telemetry["doing_valid"])
        self.assertAlmostEqual(telemetry["position"][0], 41521/256)
        self.assertAlmostEqual(telemetry["position"][1], 98551/512)


class DefeatDetectionTests(unittest.TestCase):
    def test_sandy_map_background_is_not_mistaken_for_revive_button(self):
        frame = np.full((1080, 1920, 3), (112, 151, 175), dtype=np.uint8)
        self.assertFalse(VisionEngine().is_defeated(frame))

    def test_saturated_button_shaped_gold_region_is_detected(self):
        frame = np.full((1080, 1920, 3), (112, 151, 175), dtype=np.uint8)
        frame[602:628, 662:758] = (20, 165, 245)
        frame[611:619, 686:735] = (35, 35, 35)  # Simulated label text.
        self.assertTrue(VisionEngine().is_defeated(frame))


class FakeVision:
    def __init__(self, samples, fresh=True):
        self.samples = samples
        self.calls = 0
        self.fresh = fresh

    def get_engine_telemetry(self):
        position, doing = self.samples[min(self.calls, len(self.samples)-1)]
        self.calls += 1
        return {"position": position, "doing": doing, "doing_valid": True,
                "position_frame": self.calls if self.fresh else 1,
                "map_id": 10, "position_map_id": 10}


class FakeClock:
    def __init__(self):
        self.now = 0.0

    def monotonic(self):
        return self.now

    def wait(self, seconds):
        self.now += seconds


class LegCompletionTests(unittest.TestCase):
    def engine(self, vision, clock):
        controller = SimpleNamespace(
            config={"traversal": {}}, adb_path="unused", device_id="unused",
            capture_frame=lambda: None, joystick_center=(384, 784),
            tap=lambda *args, **kwargs: self.fail("A running leg must not issue map or movement taps")
        )
        directory = tempfile.TemporaryDirectory(prefix="engine_tests_")
        self.addCleanup(directory.cleanup)
        store = RuntimeStore(os.path.join(directory.name, "runtime.sqlite3"))
        engine = MapTraversalEngine(controller, vision, None, None, SimpleNamespace(store=store))
        engine.plan = make_plan()
        engine.is_running = True
        engine.current_map_id = 10
        engine._stop_event = clock
        engine._save_progress = lambda: setattr(engine, "_last_save", clock.now)
        target = engine.plan.data["targets"][0]
        target["state"] = "active"
        return engine, target

    def test_long_leg_continues_past_seven_seconds_until_reaching_destination(self):
        samples = [((index * 0.2, 4), "run") for index in range(60)]
        samples += [((12, 4), "stand")] * 3
        vision, clock = FakeVision(samples), FakeClock()
        engine, target = self.engine(vision, clock)
        with patch("core.map_traversal_engine.time.monotonic", clock.monotonic):
            result = engine._walk_target(target, (12, 4))
        self.assertEqual(result, "arrived")
        self.assertGreater(clock.now, 7)
        self.assertGreaterEqual(vision.calls, 62)

    def test_standing_far_from_destination_is_retry_not_arrival(self):
        vision, clock = FakeVision([((1, 1), "stand")]), FakeClock()
        engine, target = self.engine(vision, clock)
        with patch("core.map_traversal_engine.time.monotonic", clock.monotonic):
            result = engine._walk_target(target, (12, 4))
        self.assertEqual(result, "retry")
        self.assertNotEqual(target["state"], "done")

    def test_stale_telemetry_never_completes_a_leg(self):
        vision, clock = FakeVision([((12, 4), "stand")], fresh=False), FakeClock()
        engine, target = self.engine(vision, clock)
        with patch("core.map_traversal_engine.time.monotonic", clock.monotonic):
            with self.assertRaisesRegex(RuntimeError, "Mất dữ liệu"):
                engine._walk_target(target, (12, 4))
        self.assertNotEqual(target["state"], "done")

    def test_position_loop_is_detected_when_actor_returns_to_same_area(self):
        clock = FakeClock()
        points = [((1.0, 1.0), "run"), ((2.0, 1.0), "run")] * 8
        vision = FakeVision(points)
        engine, target = self.engine(vision, clock)
        engine.settings = {
            "stuck_seconds": 1.5, "loop_window_seconds": 3.0,
            "loop_min_samples": 8, "loop_revisit_threshold": 3,
            "loop_cell_size": 0.75, "loop_net_distance": 1.5,
        }
        engine._cancel_and_verify = Mock()

        with patch("core.map_traversal_engine.time.monotonic", clock.monotonic), \
                patch("core.map_traversal_engine.time.sleep", side_effect=clock.wait):
            outcome = engine._walk_target(target, (10.0, 1.0))

        self.assertEqual(outcome, "retry")
        engine._cancel_and_verify.assert_called_once()

    def test_position_loop_detector_does_not_flag_a_path_that_keeps_advancing(self):
        samples = [(index * 0.5, (float(index), 0.0)) for index in range(10)]
        self.assertFalse(MapTraversalEngine._is_position_loop(samples))

    def test_single_transient_map_frame_does_not_interrupt_the_active_leg(self):
        clock = FakeClock()
        class FlakyMapVision:
            def __init__(self):
                self.calls = 0
                self.samples = [
                    (10, (1.0, 1.0), "run"),
                    (20, (50.0, 50.0), "run"),
                    (10, (12.0, 4.0), "stand"),
                    (10, (12.0, 4.0), "stand"),
                ]

            def get_engine_telemetry(self):
                map_id, position, doing = self.samples[min(self.calls, len(self.samples)-1)]
                self.calls += 1
                return {"map_id": map_id, "position_map_id": map_id,
                        "position_frame": self.calls, "position_age": 0,
                        "position": position, "doing": doing, "doing_valid": True}

        engine, target = self.engine(FlakyMapVision(), clock)
        engine._stop_event = clock
        with patch("core.map_traversal_engine.time.monotonic", clock.monotonic):
            outcome = engine._walk_target(target, (12.0, 4.0))

        self.assertEqual(outcome, "arrived")

    def test_repeated_fresh_foreign_map_frames_confirm_a_transition(self):
        clock = FakeClock()
        class SwitchingMapVision:
            def __init__(self):
                self.calls = 0

            def get_engine_telemetry(self):
                self.calls += 1
                map_id = 10 if self.calls == 1 else 20
                return {"map_id": map_id, "position_map_id": map_id,
                        "position_frame": self.calls, "position_age": 0,
                        "position": (50.0, 50.0), "doing": "run", "doing_valid": True}

        engine, target = self.engine(SwitchingMapVision(), clock)
        engine._stop_event = clock
        with patch("core.map_traversal_engine.time.monotonic", clock.monotonic):
            outcome = engine._walk_target(target, (12.0, 4.0))

        self.assertEqual(outcome, "map_changed")

    def test_stopped_proof_reuse_requires_same_device_input_and_fresh_state(self):
        clock = FakeClock()
        engine, _ = self.engine(FakeVision([((1, 1), "stand")]), clock)
        engine.ctrl.input_sequence = 4
        sample = engine.vision.get_engine_telemetry()
        with patch("core.map_traversal_engine.time.monotonic", clock.monotonic):
            engine._remember_stopped(sample)
            self.assertTrue(engine._can_reuse_stopped(sample))
            engine.ctrl.input_sequence = 5
            self.assertFalse(engine._can_reuse_stopped(sample))
            engine.ctrl.input_sequence = 4
            self.assertFalse(engine._can_reuse_stopped({**sample, "doing": "run"}))
            self.assertFalse(engine._can_reuse_stopped({**sample, "auto_move": 1}))
            self.assertFalse(engine._can_reuse_stopped({**sample, "position_age": 20}))
            self.assertFalse(engine._can_reuse_stopped({**sample, "map_id": 20, "position_map_id": 20}))
            clock.now = 3.1
            self.assertFalse(engine._can_reuse_stopped(sample))

    def test_completion_is_published_and_saved_as_soon_as_arrival_is_verified(self):
        clock = FakeClock()
        engine, target = self.engine(FakeVision([((1, 1), "stand")]), clock)
        events = []
        engine._publish = lambda **kwargs: events.append(("publish", target["state"]))
        engine._save_progress = lambda: events.append(("save", target["state"]))
        engine._complete_target(target)
        self.assertEqual(target["state"], "done")
        self.assertEqual(events, [("publish", "done"), ("save", "done")])

    def test_surveying_snapshot_contains_live_partial_map(self):
        clock = FakeClock()
        engine, _ = self.engine(FakeVision([((1, 1), "stand")]), clock)
        engine.route_phase = "surveying"
        engine._last_survey_render = 0
        updates = []
        engine.cb_route_progress = updates.append
        atlas = np.full((192, 384, 3), 140, dtype=np.uint8)
        known = np.zeros((192, 384), dtype=np.uint8)
        known[:, :192] = 255
        engine._on_survey_progress(atlas, known, 0.5)
        self.assertEqual(len(updates), 1)
        self.assertEqual(updates[0]["phase"], "surveying")
        self.assertEqual(updates[0]["observed_fraction"], 0.5)
        self.assertIsNotNone(updates[0]["preview_rgb"])

    def test_joystick_arrival_confirmation_rejects_stopped_sample_outside_tolerance(self):
        clock = FakeClock()
        engine, target = self.engine(FakeVision([((1, 1), "stand")]), clock)
        engine._wait_stopped = lambda: {
            "map_id": 10, "position_map_id": 10, "position_frame": 2,
            "position": (10.0, 10.0), "doing": "stand", "doing_valid": True
        }
        self.assertFalse(engine._confirm_joystick_arrival((12.0, 10.0), 0.5, target["id"]))
        self.assertNotEqual(target["state"], "done")

    def test_direct_walk_stops_if_telemetry_switches_maps(self):
        clock = FakeClock()
        engine, target = self.engine(FakeVision([((10.0, 10.0), "stand")]), clock)
        class SwitchingVision:
            calls = 0

            def get_engine_telemetry(self):
                self.calls += 1
                map_id = 10 if self.calls == 1 else 20
                return {"map_id": map_id, "position_map_id": map_id,
                        "position_frame": self.calls, "position_age": 0,
                        "position": (10.0, 10.0), "doing": "stand", "doing_valid": True}

        engine.vision = SwitchingVision()
        engine.ctrl.move_joystick = Mock()
        with patch("core.map_traversal_engine.time.sleep", side_effect=clock.wait):
            outcome = engine._walk_joystick_direct(target, (12.0, 10.0))
        self.assertEqual(outcome, "map_changed")
        self.assertEqual(engine.ctrl.move_joystick.call_count, 1)

    def test_direct_walk_stops_after_first_no_progress_sample(self):
        clock = FakeClock()
        vision = FakeVision([
            ((10.0, 10.0), "stand"),
            ((10.0, 11.0), "run"),
            ((10.0, 10.0), "run"),
        ])
        engine, target = self.engine(vision, clock)
        engine._wait_stopped = lambda: {
            "map_id": 10, "position_map_id": 10, "position_frame": 4,
            "position_age": 0, "position": (10.0, 10.0),
            "doing": "stand", "doing_valid": True
        }
        engine.ctrl.move_joystick = Mock()
        with patch("core.map_traversal_engine.time.sleep", side_effect=clock.wait):
            outcome = engine._walk_joystick_direct(target, (20.0, 10.0))
        self.assertEqual(outcome, "stalled")
        self.assertEqual(engine.ctrl.move_joystick.call_count, 1)
        self.assertLessEqual(engine.ctrl.move_joystick.call_args.kwargs["duration_ms"], 500)
        self.assertNotEqual(target["state"], "done")

    def test_single_option_target_without_progress_is_deferred_after_one_route_attempt(self):
        clock = FakeClock()
        engine, target = self.engine(FakeVision([((0.0, 0.0), "stand")]), clock)
        engine.plan.data["targets"] = [target]
        target.update({"state": "pending", "attempts": 0, "total_attempts": 0,
                       "options": [[2.0, 1.0]]})
        engine.settings = {"max_target_attempts": 3, "arrival_tolerance": 1.0}
        engine.plan.route_to = lambda *args: None
        engine._wait_stopped = lambda: {
            "map_id": 10, "position_map_id": 10, "position_frame": 2,
            "position_age": 0, "position": (0.0, 0.0),
            "doing": "stand", "doing_valid": True
        }
        engine._walk_joystick_direct = Mock(return_value="stalled")
        engine._save_progress = lambda: None
        engine._publish = lambda **kwargs: None
        engine._backtrack_from_obstacle = Mock()
        self.assertEqual(engine._cover_map(), "finished")
        self.assertEqual(engine._walk_joystick_direct.call_count, 1)
        self.assertEqual(target["state"], "deferred")
        engine._backtrack_from_obstacle.assert_not_called()

    def test_ring_distance_skips_joystick_and_plans_from_current_position(self):
        clock = FakeClock()
        engine, target = self.engine(FakeVision([((0.0, 0.0), "stand")]), clock)
        engine.plan.data["targets"] = [target]
        target.update({"state": "pending", "attempts": 0, "total_attempts": 0,
                       "options": [[5.0, 1.0]]})
        engine.settings = {"max_target_attempts": 1, "arrival_tolerance": 1.0}
        samples = iter([
            (0.0, 0.0),  # Starting position
            (0.5, 0.0),  # Direct joystick stopped here
            (0.5, 0.0),  # Check for final joystick segment
            (0.5, 0.0),  # Failed route progress check
        ])
        def stopped_sample():
            frame = stopped_sample.calls + 1
            stopped_sample.calls = frame
            return {
                "map_id": 10, "position_map_id": 10, "position_frame": frame,
                "position_age": 0, "position": next(samples),
                "doing": "stand", "doing_valid": True
            }
        stopped_sample.calls = 0
        engine._wait_stopped = stopped_sample
        engine._walk_joystick_direct = Mock(return_value="walked")
        route_starts = []
        engine.plan.route_to = lambda start, end: route_starts.append(start) or None
        engine._save_progress = lambda: None
        engine._publish = lambda **kwargs: None
        engine._backtrack_from_obstacle = Mock()
        self.assertEqual(engine._cover_map(), "finished")
        self.assertEqual(route_starts, [(0.0, 0.0)])
        engine._walk_joystick_direct.assert_not_called()
        engine._backtrack_from_obstacle.assert_not_called()

    def test_resumed_single_option_retry_skips_repeating_direct_joystick(self):
        clock = FakeClock()
        engine, target = self.engine(FakeVision([((0.0, 0.0), "stand")]), clock)
        engine.plan.data["targets"] = [target]
        target.update({"state": "retry", "attempts": 1, "total_attempts": 1,
                       "options": [[2.0, 1.0]]})
        engine.settings = {"max_target_attempts": 3, "arrival_tolerance": 1.0}
        engine.plan.route_to = lambda *args: None
        engine._wait_stopped = lambda: {
            "map_id": 10, "position_map_id": 10, "position_frame": 2,
            "position_age": 0, "position": (0.0, 0.0),
            "doing": "stand", "doing_valid": True
        }
        engine._walk_joystick_direct = Mock()
        engine._save_progress = lambda: None
        engine._publish = lambda **kwargs: None
        engine._backtrack_from_obstacle = Mock()
        self.assertEqual(engine._cover_map(), "finished")
        engine._walk_joystick_direct.assert_not_called()
        self.assertEqual(target["state"], "deferred")
        engine._backtrack_from_obstacle.assert_not_called()

    def test_deferred_target_is_not_retried_in_final_sweep(self):
        clock = FakeClock()
        engine, target = self.engine(FakeVision([((0.0, 0.0), "stand")]), clock)
        engine.plan.data["targets"] = [target]
        target.update({"state": "deferred", "attempts": 3, "options": [[2.0, 1.0]]})
        engine.plan.add_inspection_gaps = lambda: 0
        engine._walk_joystick_direct = Mock()
        engine._save_progress = lambda: None
        engine._publish = lambda **kwargs: None
        engine._revisits = []
        self.assertEqual(engine._cover_map(), "finished")
        engine._walk_joystick_direct.assert_not_called()

    def test_pause_releases_movement_and_returns_repin_without_completing_target(self):
        clock = FakeClock()
        engine, target = self.engine(FakeVision([((1, 1), "stand")]), clock)
        engine.ctrl.cancel_movement = Mock()
        engine._bound = True
        engine.current_target = target
        engine._publish = lambda **kwargs: None
        engine.is_paused = True
        def wait(seconds):
            clock.now += seconds
            if engine._pause_ack:
                engine.resume()
        engine._stop_event.wait = wait
        with patch("core.map_traversal_engine.time.monotonic", clock.monotonic), \
                patch("core.map_traversal_engine.time.sleep", side_effect=wait):
            outcome = engine._walk_target(target, (5, 5))
        self.assertEqual(outcome, "repin")
        engine.ctrl.cancel_movement.assert_called_once()
        self.assertNotEqual(target["state"], "done")
        self.assertEqual(engine.plan.data["resume_target_id"], target["id"])

    def test_cancel_cannot_acknowledge_repeated_old_position(self):
        clock = FakeClock()
        engine, _ = self.engine(FakeVision([((1, 1), "stand")], fresh=False), clock)
        engine.ctrl.cancel_movement = Mock()
        with patch("core.map_traversal_engine.time.monotonic", clock.monotonic), \
                patch("core.map_traversal_engine.time.sleep", side_effect=clock.wait):
            with self.assertRaisesRegex(RuntimeError, "chưa xác minh"):
                engine._cancel_and_verify()

    def _run_two_segment_route(self, outcome):
        clock = FakeClock()
        engine, target = self.engine(FakeVision([((0, 0), "stand")]), clock)
        engine.plan.data["targets"] = [target]
        target["state"] = "pending"
        engine.settings = {"max_target_attempts": 1}
        engine.plan.route_to = lambda *args: [[1, 1], [3, 3]]
        engine._wait_stopped = lambda: {"map_id": 10, "position": (0, 0)}
        engine._save_progress = lambda: None
        engine._publish = lambda **kwargs: None
        calls = []
        engine.surveyor = SimpleNamespace(pin=lambda *args: calls.append(args))
        engine._walk_target = lambda *args: outcome
        engine._cover_map()
        return target, calls

    def test_failed_first_segment_cannot_pin_the_second_or_complete_the_cell(self):
        target, calls = self._run_two_segment_route("retry")
        self.assertEqual(calls, [(1, 1, 10)])
        self.assertEqual(target["state"], "deferred")

    def test_cell_completes_only_after_all_automatic_segments_arrive(self):
        target, calls = self._run_two_segment_route("arrived")
        self.assertEqual(calls, [(1, 1, 10), (3, 3, 10)])
        self.assertEqual(target["state"], "done")

    def test_already_at_verified_target_does_not_open_map_again(self):
        clock = FakeClock()
        engine, target = self.engine(FakeVision([((0, 0), "stand")]), clock)
        engine.plan.data["targets"] = [target]
        target["state"] = "pending"
        engine._wait_stopped = lambda: {"map_id": 10, "position": target["options"][0]}
        engine._save_progress = lambda: None
        engine._publish = lambda **kwargs: None
        engine.surveyor.pin = Mock()
        self.assertEqual(engine._cover_map(), "finished")
        self.assertEqual(target["state"], "done")
        engine.surveyor.pin.assert_not_called()

    def test_cancel_movement_swipes_joystick(self):
        from core.ld_controller import LDController
        ctrl = LDController()
        ctrl.joystick_center = (384, 784)
        ctrl.swipe = Mock()
        ctrl.cancel_movement()
        ctrl.swipe.assert_called_once_with(384, 784, 419, 784, duration_ms=150, _cancel=True)

    def test_natural_detour_around_obstacle_does_not_trigger_deviation(self):
        clock = FakeClock()
        # Origin (179, 196), Destination (180, 198)
        # Detour swings west to (174, 196) around cliff, then approaches (179, 198)
        steps = [
            ((179.0, 196.0), "run"),
            ((177.0, 195.5), "run"),
            ((174.5, 195.5), "run"),
            ((174.0, 196.5), "run"),
            ((176.0, 197.5), "run"),
            ((178.5, 198.0), "run"),
            ((179.8, 198.0), "stand"),
            ((179.8, 198.0), "stand"),
        ]
        engine, target = self.engine(FakeVision(steps), clock)
        engine._leg = {"id": "leg1", "from": [179.0, 196.0], "to": [180.0, 198.0]}
        engine.settings = {"arrival_tolerance": 1.0, "corridor_tolerance": 10.0, "detour_budget": 12.0}
        with patch("core.map_traversal_engine.time.monotonic", clock.monotonic), \
                patch("core.map_traversal_engine.time.sleep", side_effect=clock.wait):
            outcome = engine._walk_target(target, (180.0, 198.0))
        self.assertEqual(outcome, "arrived")

    def test_walk_joystick_direct_calls_move_joystick(self):
        clock = FakeClock()
        engine, target = self.engine(FakeVision([((10.0, 10.0), "stand"), ((12.0, 10.0), "stand")]), clock)
        engine._wait_stopped = lambda: {
            "map_id": 10, "position_map_id": 10, "position_frame": 2,
            "position": (12.0, 10.0), "doing": "stand", "doing_valid": True
        }
        engine.ctrl.move_joystick = Mock()
        outcome = engine._walk_joystick_direct(target, (12.0, 10.0))
        engine.ctrl.move_joystick.assert_called_once()

    def test_probe_corner_crevice_pushes_joystick(self):
        clock = FakeClock()
        steps = [((180.0, 198.0), "stand"), ((181.0, 198.0), "stand"), ((182.0, 198.0), "stand")]
        engine, target = self.engine(FakeVision(steps), clock)
        engine._wait_stopped = lambda: {"position": (180.0, 198.0)}
        engine.ctrl.move_joystick = Mock()
        target["is_perimeter"] = True
        engine._probe_corner_crevice(target)
    def test_joystick_only_mode_never_pins_and_walks_via_joystick(self):
        clock = FakeClock()
        engine, target = self.engine(FakeVision([((0, 0), "stand")]), clock)
        engine.plan.data["targets"] = [target]
        target["state"] = "pending"
        engine.settings = {"max_target_attempts": 1, "joystick_only": True}
        engine.plan.route_to = lambda *args: [[1, 1], [3, 3]]
        engine._wait_stopped = lambda: {"map_id": 10, "position": (0, 0)}
        engine._save_progress = lambda: None
        engine._publish = lambda **kwargs: None
        calls = []
        engine.surveyor = SimpleNamespace(pin=lambda *args: calls.append(args))
        engine._run_path_joystick_continuous = Mock(return_value="arrived")
        engine._cover_map()
        self.assertEqual(calls, [])
        engine._run_path_joystick_continuous.assert_called_once()
        self.assertEqual(target["state"], "done")

    def test_joystick_continuous_skips_immediately_on_stalled_obstacle(self):
        clock = FakeClock()
        engine, target = self.engine(FakeVision([((0, 0), "stand")]), clock)
        engine.plan.data["targets"] = [target]
        target["state"] = "pending"
        engine.settings = {"max_target_attempts": 1, "joystick_only": True}
        engine.plan.route_to = lambda *args: [[1, 1]]
        engine._wait_stopped = lambda: {"map_id": 10, "position": (0, 0)}
        engine._save_progress = lambda: None
        engine._publish = lambda **kwargs: None
        engine._run_path_joystick_continuous = Mock(return_value="stalled")
        engine._cover_map()
        self.assertEqual(target["state"], "deferred")

    def test_direct_vision_radius_sweeps_and_marks_nearby_targets_done(self):
        clock = FakeClock()
        engine, target1 = self.engine(FakeVision([((0, 0), "run")]), clock)
        target2 = dict(target1)
        target2["id"] = "target_2"
        target2["options"] = [[2.5, 0.0]]
        target2["state"] = "pending"
        engine.plan.data["targets"] = [target1, target2]

        # Target2 is 2.5 units away. With vision_radius 3.2, it is seen directly and marked done.
        engine.plan.observe_position((0.0, 0.0), tolerance=1.0, vision_radius=3.2)
        self.assertEqual(target2["state"], "done")

    def test_joystick_continuous_updates_live_player_position_and_publishes(self):
        clock = FakeClock()
        engine, target = self.engine(FakeVision([
            ((1.0, 1.0), "run"),
            ((2.0, 2.0), "run"),
            ((3.0, 3.0), "stand")
        ]), clock)
        engine.settings["vision_radius"] = 3.5
        engine.ctrl.move_joystick = Mock()
        publishes = []
        engine._publish = lambda **kwargs: publishes.append(engine.plan.data.get("current_player_position"))
        outcome = engine._run_path_joystick_continuous(target, [[2.0, 2.0]], [3.0, 3.0], tolerance=1.0, max_total_seconds=5.0)
        self.assertEqual(outcome, "arrived")
        self.assertIsNotNone(engine.plan.data.get("current_player_position"))


if __name__ == "__main__":
    unittest.main()

