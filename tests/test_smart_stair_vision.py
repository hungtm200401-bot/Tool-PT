import math
import unittest
import numpy as np

from core.coverage_planner import CoveragePlan


class TestSmartStairVision(unittest.TestCase):
    def setUp(self):
        atlas = np.full((192, 384, 3), 160, dtype=np.uint8)
        known = np.full(atlas.shape[:2], 255, dtype=np.uint8)
        self.plan = CoveragePlan.build(1, [0, 0, 384, 192], atlas, known, {"strategy": "corners_first"})

    def test_forward_vision_cone_sweeps_distant_target_ahead(self):
        # Target 1 is at (5.0, 0.0), which is 5.0 units away from origin (0.0, 0.0)
        # Regular vision radius is 3.2, so 5.0 is beyond 3.2.
        # But with heading (1.0, 0.0) looking directly at it (alignment = 1.0, forward_reach = 3.2 * 1.85 = 5.92),
        # it falls inside the Forward Vision Cone!
        target_ahead = {
            "id": "t_ahead",
            "options": [[5.0, 0.0]],
            "state": "pending",
            "batch": 0,
            "col": 5,
            "row": 0
        }
        # Target behind at (-5.0, 0.0)
        target_behind = {
            "id": "t_behind",
            "options": [[-5.0, 0.0]],
            "state": "pending",
            "batch": 0,
            "col": -5,
            "row": 0
        }
        self.plan.data["targets"] = [target_ahead, target_behind]

        # Call observe_position with heading looking +X: (1.0, 0.0)
        self.plan.observe_position(
            position=(0.0, 0.0),
            tolerance=1.0,
            vision_radius=3.2,
            heading=(1.0, 0.0)
        )

        # Target ahead must be swept and marked seen by forward vision cone (seen != done)
        self.assertTrue(target_ahead.get("seen"), "Target directly ahead in vision cone must be marked seen")
        self.assertEqual(target_ahead["state"], "pending", "Target 5.0 units away must remain pending until physically reached")
        # Target behind at distance 5.0 must NOT be marked seen
        self.assertFalse(target_behind.get("seen"), "Target behind outside vision radius must remain unseen")
        self.assertEqual(target_behind["state"], "pending", "Target behind outside vision radius must remain pending")

        # When character physically reaches within tolerance (4.5, 0.0), it becomes done
        self.plan.observe_position(
            position=(4.5, 0.0),
            tolerance=1.0
        )
        self.assertEqual(target_ahead["state"], "done", "Target must be marked done once reached within tolerance")

    def test_forward_vision_cone_angular_cutoff(self):
        # Target at 4.5 units away at 90 degrees (perpendicular, alignment = 0.0)
        # Beyond 3.2 radius, and outside the +/- 60 deg cone
        target_perp = {
            "id": "t_perp",
            "options": [[0.0, 4.5]],
            "state": "pending",
            "batch": 0,
            "col": 0,
            "row": 4
        }
        self.plan.data["targets"] = [target_perp]

        self.plan.observe_position(
            position=(0.0, 0.0),
            tolerance=1.0,
            vision_radius=3.2,
            heading=(1.0, 0.0) # Looking +X
        )

        self.assertEqual(target_perp["state"], "pending", "Target outside cone angle must remain pending")

    def test_render_with_heading_cone(self):
        self.plan.data["current_player_position"] = [10.0, 10.0]
        self.plan.data["current_heading"] = [0.707, 0.707] # 45 degrees along stair diagonal
        rgb = self.plan.render()
        self.assertIsNotNone(rgb)
        self.assertEqual(rgb.ndim, 3)
        self.assertGreater(rgb.shape[0], 50)
        self.assertGreater(rgb.shape[1], 50)


if __name__ == "__main__":
    unittest.main()
