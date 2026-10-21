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
    def test_npcprompt_and_dialog_parsing(self):
        fake_prompt = {
            "visible": True,
            "cocos_hit_valid": True,
            "name": "Xích Tinh Tử",
            "distance": 206
        }
        fake_dialog = {
            "visible": True,
            "message": "Tử Nha là người thông minh...",
            "answer_count": 2,
            "answers": [
                {"index": 0, "text": "Tiếp nhận"},
                {"index": 1, "text": "Từ chối"}
            ]
        }

        def mock_read(fname, timeout=2.0):
            if fname == "npcprompt-render-status.json":
                return fake_prompt, 0.1
            if fname == "npcdialog-render-status.json":
                return fake_dialog, 0.1
            return None, None

        with patch.object(self.observer, "read_remote_json", side_effect=mock_read):
            snapshot = self.observer.capture_snapshot()
            prompt = snapshot["raw_sources"].get("npcprompt", {})
            dialog = snapshot["raw_sources"].get("npcdialog", {})
            self.assertTrue(prompt.get("visible"))
            self.assertEqual(prompt.get("name"), "Xích Tinh Tử")
            self.assertTrue(dialog.get("visible"))
            self.assertEqual(len(dialog.get("answers", [])), 2)

    def test_player_mind_priorities(self):
        from core.player_agent import PlayerMind
        mind = PlayerMind()

        # 1. Emergency HP < 50%
        state_emergency = {
            "character": {"hp": {"current": 10, "max": 24}, "mp": {"current": 70, "max": 70}, "position": (213.0, 197.0)},
            "world": {"sub_world_id": 3, "map_name": "Ngọc Hư Cung"},
            "raw_sources": {}
        }
        dec1 = mind.evaluate_situation(state_emergency)
        self.assertEqual(dec1["priority"], "EMERGENCY")
        self.assertEqual(dec1["action"], "USE_POTION_OR_RETREAT")

        # 2. NPC Dialog open
        state_dialog = {
            "character": {"hp": {"current": 24, "max": 24}, "mp": {"current": 70, "max": 70}, "position": (213.0, 197.0)},
            "world": {"sub_world_id": 3, "map_name": "Ngọc Hư Cung"},
            "raw_sources": {"npcdialog": {"visible": True, "cocos_nodes_visible": 5}}
        }
        dec2 = mind.evaluate_situation(state_dialog)
        self.assertEqual(dec2["priority"], "QUEST_INTERACTION")
        self.assertEqual(dec2["action"], "ADVANCE_NPC_DIALOG")

        # 3. NPC Prompt banner visible
        state_prompt = {
            "character": {"hp": {"current": 24, "max": 24}, "mp": {"current": 70, "max": 70}, "position": (213.0, 197.0)},
            "world": {"sub_world_id": 3, "map_name": "Ngọc Hư Cung"},
            "raw_sources": {"npcprompt": {"visible": True, "cocos_hit_valid": True, "name": "Vân Trung Tử"}}
        }
        dec3 = mind.evaluate_situation(state_prompt)
        self.assertEqual(dec3["priority"], "QUEST_INTERACTION")
        self.assertEqual(dec3["action"], "TALK_TO_NPC")
        self.assertEqual(dec3["npc_name"], "Vân Trung Tử")

        # 4. Story Quest tracking
        state_quest = {
            "character": {"hp": {"current": 24, "max": 24}, "mp": {"current": 70, "max": 70}, "position": (213.0, 197.0)},
            "world": {"sub_world_id": 3, "map_name": "Ngọc Hư Cung"},
            "raw_sources": {},
            "quests": [{"title": "Bách Lý", "detail": "Thỉnh giáo Vân Trung Tử", "task_id": 1}]
        }
        dec4 = mind.evaluate_situation(state_quest)
        self.assertEqual(dec4["priority"], "ACTIVE_QUEST")
        self.assertEqual(dec4["action"], "TRACK_QUEST")

    def test_action_executor_quest_flow_x_close(self):
        from core.player_agent import ActionExecutor
        mock_ctrl = MagicMock()
        executor = ActionExecutor(mock_ctrl)

        executor.execute_quest_flow("Bách Lý")
        tapped_coords = [(call[0][0], call[0][1]) for call in mock_ctrl.tap.call_args_list]

        # Verify critical coordinates were tapped
        self.assertIn((1856, 344), tapped_coords, "Phải mở menu tính năng")
        self.assertIn((1695, 740), tapped_coords, "Phải mở cửa sổ Nhiệm vụ")
        self.assertIn((180, 210), tapped_coords, "Phải chọn nhiệm vụ Bách Lý")
        self.assertIn((1873, 32), tapped_coords, "Phải bấm X đóng bảng đôi theo hướng dẫn người dùng")
        self.assertIn((1550, 71), tapped_coords, "Phải bấm X đóng bảng đơn theo hướng dẫn người dùng")


if __name__ == "__main__":
    unittest.main()
