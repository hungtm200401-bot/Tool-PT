import unittest
import math
import numpy as np
from types import SimpleNamespace
from unittest.mock import MagicMock

from core.coverage_planner import CoveragePlan
from core.obstacle_bypasser import ObstacleBypasser
from core.map_traversal_engine import MapTraversalEngine


class TestSmartExitVision(unittest.TestCase):
    def setUp(self):
        # Create a 64x64 grid where center is open, right side is walled off
        atlas = np.full((64, 64, 3), 160, dtype=np.uint8)
        known = np.full((64, 64), 255, dtype=np.uint8)
        # Bounds: [0, 0, 64, 64] -> each unit is 16 pixels, 8 pixels per cell -> 8x8 navigation cells
        self.plan = CoveragePlan.build(1, [0, 0, 64, 64], atlas, known, {"strategy": "corners_first"})
        # Place a hard obstacle wall in cells col >= 6
        self.plan.navigation[:, 6:] = False
        self.plan.navigation[:2, :] = False
        self.plan.navigation[6:, :] = False

    def test_coverage_plan_is_walkable_and_cast_ray(self):
        # Center of arena: (2.0, 2.0) -> col = 4, row = 4 (Walkable)
        self.assertTrue(self.plan.is_walkable(2.0, 2.0))
        # Wall at col = 6 -> x = 3.25 (Not walkable)
        self.assertFalse(self.plan.is_walkable(3.5, 2.0))

        # Raycast East (0 deg) towards the wall at x=3.0:
        # Distance to wall should be around 1.0 unit
        ray_east = self.plan.cast_ray((2.0, 2.0), 0.0, max_dist=4.0)
        self.assertLess(ray_east, 1.5)

        # Raycast West (180 deg) towards open corridor:
        ray_west = self.plan.cast_ray((2.0, 2.0), 180.0, max_dist=4.0)
        self.assertGreater(ray_west, ray_east)

    def test_scan_exit_corridors_sorts_by_open_depth(self):
        pos = (2.8, 2.0) # Very close to the wall on the East (0 deg)
        exits = self.plan.scan_exit_corridors(pos, num_rays=8, max_dist=4.0)
        self.assertEqual(len(exits), 8)
        # The best exit should be West (180 deg), not East (0 deg)
        best_angle, best_depth = exits[0]
        self.assertNotEqual(best_angle, 0.0)
        self.assertGreaterEqual(best_depth, 1.5)

    def test_smart_exit_finder_selects_open_exit_toward_destination(self):
        bypasser = ObstacleBypasser(None, joystick_only=True)
        current_pos = (2.8, 2.0)
        dest = (1.0, 2.0) # Destination is to the West

        best_exit = bypasser.find_smart_exit(
            current_pos=current_pos,
            current_heading_deg=0.0, # Facing East into wall
            plan=self.plan,
            destination=dest
        )
        # Should steer toward West (around 180 deg)
        self.assertAlmostEqual(best_exit, 180.0, delta=45.0)

    def test_smart_exit_finder_falls_back_to_breadcrumbs_when_trapped(self):
        bypasser = ObstacleBypasser(None, joystick_only=True)
        # Surrounded by walls
        mock_plan = SimpleNamespace(
            scan_exit_corridors=lambda pos, **kwargs: [(0.0, 0.2), (90.0, 0.1), (180.0, 0.3), (270.0, 0.2)]
        )
        breadcrumbs = [[10.0, 10.0], [10.0, 12.0]]
        current_pos = [10.0, 13.0]
        exit_angle = bypasser.find_smart_exit(
            current_pos=current_pos,
            current_heading_deg=90.0,
            plan=mock_plan,
            breadcrumbs=breadcrumbs
        )
        # Breadcrumb [10.0, 12.0] is North (dy < 0) of current_pos [10.0, 13.0] -> ~309.0 deg in isometric
        self.assertAlmostEqual(exit_angle, 309.0, delta=15.0)



if __name__ == "__main__":
    unittest.main()
