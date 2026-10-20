"""Unit tests for GameStateObserver and TestOracleEngine.

Validates that GameStateObserver correctly extracts live telemetry
and TestOracleEngine accurately classifies the 33 domains (500 items).
"""

import unittest
from unittest.mock import MagicMock, patch

from core.game_state_observer import GameStateObserver
from core.test_oracle_engine import TestOracleEngine


class TestGameStateAndOracle(unittest.TestCase):
    def setUp(self):
        self.observer = GameStateObserver(adb_path="adb.exe", device_id="emulator-5554")
        self.engine = TestOracleEngine()

    def test_mock_snapshot_parsing(self):
        fake_pos = {
            "frames": 70350,
            "in_game": True,
            "sub_world_id": 3,
            "player": {
                "mps": [54528, 100865],
                "doing": "stand",
                "region_xy": [106, 98]
            }
        }
        fake_char = {
            "snapshot": {
                "Name": {"text": {"s": "ThậpTamTrấnHùng"}},
                "Level": {"text": {"s": "4"}},
                "Life": {"text": {"s": "24/24"}},
                "Mana": {"text": {"s": "70/70"}},
                "Exp": {"text": {"s": "72.500%"}},
                "net": {"text": {"s": "thaptuyettran.vn"}}
            },
            "canvas": [1368, 768]
        }
        fake_map = {
            "mini": {"name": "Ngọc Hư Cung", "pos": "213,197"},
            "world": {"up": 0, "player_map": 3}
        }

        def mock_read(fname, timeout=2.0):
            if fname == "pos-trace-status.json":
                return fake_pos, 0.1
            if fname == "charpanel-render-status.json":
                return fake_char, 0.1
            if fname == "map-render-status.json":
                return fake_map, 0.1
            return None, None

        with patch.object(self.observer, "read_remote_json", side_effect=mock_read):
            snapshot = self.observer.capture_snapshot()
            self.assertTrue(snapshot["in_game"])
            self.assertEqual(snapshot["character"]["name"], "ThậpTamTrấnHùng")
            self.assertEqual(snapshot["character"]["level"], 4)
            self.assertEqual(snapshot["character"]["hp"]["current"], 24)
            self.assertEqual(snapshot["character"]["mp"]["max"], 70)
            self.assertEqual(snapshot["character"]["position"], (213.0, 197.002))
            self.assertEqual(snapshot["world"]["sub_world_id"], 3)
            self.assertEqual(snapshot["world"]["server_host"], "thaptuyettran.vn")

    def test_oracle_engine_evaluates_all_500_items(self):
        snapshot = {
            "timestamp": 1729400000.0,
            "character": {
                "name": "ThậpTamTrấnHùng",
                "level": 4,
                "hp": {"current": 24, "max": 24},
                "mp": {"current": 70, "max": 70},
                "exp_percent": "72.500%",
                "doing": "stand",
            },
            "world": {
                "sub_world_id": 3,
                "server_host": "thaptuyettran.vn",
                "map_name": "Ngọc Hư Cung",
            },
            "quests": [{"title": "Ngô Thất", "detail": "Lấy Lửa và Băng"}],
            "skills": {"active_right_skill": 2},
            "autoplay": {"state": "off", "settings": {"pick_in_town": 0}},
            "ui": {"canvas": [1368, 768]},
            "in_game": True,
        }

        eval_result = self.engine.evaluate_live_state(snapshot)
        self.assertEqual(len(eval_result["domains"]), 33, "Phải có đầy đủ 33 miền kiểm thử")
        self.assertEqual(eval_result["summary"]["TOTAL"], 500, "Tổng số điểm kiểm tra phải là 500")

        # Verify PASS counts are > 0
        self.assertGreater(eval_result["summary"]["PASS"], 15)
        # Verify BLOCKED counts for advanced features at level 4
        self.assertGreater(eval_result["summary"]["BLOCKED"], 100)


if __name__ == "__main__":
    unittest.main()
