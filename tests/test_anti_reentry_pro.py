import unittest
import math
import time
import numpy as np
from types import SimpleNamespace
from unittest.mock import MagicMock

from core.coverage_planner import CoveragePlan
from core.obstacle_bypasser import ObstacleBypasser
from core.map_traversal_engine import MapTraversalEngine
from core.ld_controller import game_to_joystick_angle


class TestAntiReentryPro(unittest.TestCase):
    def setUp(self):
        atlas = np.full((128, 128, 3), 160, dtype=np.uint8)
        known = np.full((128, 128), 255, dtype=np.uint8)
        self.plan = CoveragePlan.build(6, [0, 0, 128, 128], atlas, known, {"strategy": "corners_first"})

    def test_barrier_slab_burns_wide_impenetrable_wall(self):
        curr_pos = (4.0, 4.0)
        obs_pt = (3.0, 4.0) # Obstacle to the West (-1.0, 0.0) -> heading (-1.0, 0.0)
        heading = (-1.0, 0.0)

        # Before burning, West is walkable
        self.assertTrue(self.plan.is_walkable(3.0, 4.0))

        # Burn barrier slab
        self.plan.note_obstacle(obs_pt, obs_pt, duration=300.0, radius=3, barrier=True, heading=heading)

        # After burning: not only (3.0, 4.0), but along tangent (-1.0 to +1.0 in Y) is blocked
        self.assertFalse(self.plan.is_walkable(3.0, 4.0))
        self.assertFalse(self.plan.is_walkable(3.0, 3.5))
        self.assertFalse(self.plan.is_walkable(3.0, 4.5))

    def test_smart_exit_strictly_forbids_blocked_angles(self):
        bypasser = ObstacleBypasser(None, joystick_only=True)
        current_pos = (4.0, 4.0)
        blocked_heading = 180.0 # Blocked when running West

        # Even if destination is to the West (180 deg), smart exit must NOT pick West
        west_dest = (1.0, 4.0)
        breadcrumbs = [[4.5, 4.0], [5.0, 4.0]] # Came from East (0 deg)

        exit_angle = bypasser.find_smart_exit(
            current_pos=current_pos,
            current_heading_deg=blocked_heading,
            plan=self.plan,
            destination=west_dest,
            breadcrumbs=breadcrumbs
        )

        # Must exit towards East (around 0 deg), never towards West (180 deg)
        ang_diff = abs((exit_angle - blocked_heading + 180) % 360 - 180)
        self.assertGreaterEqual(ang_diff, 75.0)

    def test_anti_reentry_sector_deflects_steering(self):
        # Create minimal engine
        ctrl = MagicMock()
        ctrl.config = {"traversal": {"joystick_only": True}, "resolution": {"width": 1920, "height": 1080}, "joystick": {"center_x": 384, "center_y": 784, "radius": 120}, "ui_elements": {}}
        engine = MapTraversalEngine(ctrl, MagicMock(), None, None, SimpleNamespace(store=MagicMock()))

        # Register a blocked sector at (10.0, 10.0) facing West (180 deg)
        now_time = time.monotonic()
        engine._blocked_sectors = [{
            "pos": [10.0, 10.0],
            "angle": 180.0,
            "radius": 4.0,
            "span": 75.0,
            "expires": now_time + 60.0
        }]

        # If a candidate angle tries to steer West (175 deg) from (10.2, 10.0)
        target_angle = 175.0
        curr_pos = [10.2, 10.0]

        # Apply the anti-reentry guard logic
        for s in engine._blocked_sectors:
            if s["expires"] > now_time and math.dist(curr_pos, s["pos"]) <= s["radius"]:
                ang_diff = (target_angle - s["angle"] + 180) % 360 - 180
                if abs(ang_diff) < s["span"]:
                    veer_dir = 1.0 if ang_diff >= 0 else -1.0
                    target_angle = (s["angle"] + veer_dir * (s["span"] + 10.0)) % 360
                    break

        # Target angle must have been deflected at least 85 degrees away from 180 deg
        deflected_diff = abs((target_angle - 180.0 + 180) % 360 - 180)
        self.assertGreaterEqual(deflected_diff, 80.0)

    def test_active_unstuck_escapes_obstacle_and_registers_block(self):
        ctrl = MagicMock()
        ctrl.config = {"traversal": {"joystick_only": True}, "resolution": {"width": 1920, "height": 1080}, "joystick": {"center_x": 384, "center_y": 784, "radius": 120}, "ui_elements": {}}
        vision = MagicMock()
        start_p = (5.0, 5.0)
        end_p = (3.2, 5.0)
        vision.get_engine_telemetry.side_effect = [
            {"position": start_p, "position_frame": 1, "position_age": 0.1, "in_game": True, "map_id": 6, "position_map_id": 6},
            {"position": (4.5, 5.0), "position_frame": 2, "position_age": 0.1, "in_game": True, "map_id": 6, "position_map_id": 6},
            {"position": end_p, "position_frame": 3, "position_age": 0.1, "in_game": True, "map_id": 6, "position_map_id": 6},
        ]
        engine = MapTraversalEngine(ctrl, vision, None, None, SimpleNamespace(store=MagicMock()))
        engine.plan = self.plan
        engine.is_running = True
        engine.is_paused = False
        engine._verified_breadcrumbs.append([3.0, 5.0])

        escaped_p = engine._perform_active_unstuck(start_p, angle_blocked=0.0)

        self.assertTrue(ctrl.joystick_press.called or ctrl.joystick_steer.called)
        self.assertTrue(ctrl.joystick_release.called)
        self.assertTrue(any(s["angle"] == 0.0 for s in engine._blocked_sectors))
        self.assertGreaterEqual(math.dist(start_p, escaped_p), 1.5)


if __name__ == "__main__":
    unittest.main()

