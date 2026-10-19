import json
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from core.vision_engine import VisionEngine


class TelemetryFreshnessTests(unittest.TestCase):
    def replies(self, now=10000, modified=10000, map_id=2, metadata=True):
        def read(command, **_kwargs):
            if "map-render-status.json" in command[-1]:
                data = {"frames": 50, "world": {"player_map": map_id}}
                mtime = now
            else:
                data = {"frames": 100, "sub_world_id": map_id,
                        "player": {"mps": [51200, 102400], "doing": "stand"}}
                mtime = modified
            raw = json.dumps(data)
            return SimpleNamespace(stdout=f"{now}\n{mtime}\n{raw}" if metadata else raw)
        return read

    def test_hour_old_stand_record_is_not_a_live_character(self):
        with patch("subprocess.run", side_effect=self.replies(modified=6400)):
            sample = VisionEngine("adb", "device").get_engine_telemetry()
        self.assertEqual(sample["position_age"], 3600)
        self.assertFalse(sample["in_game"])

    def test_stationary_character_is_fresh_when_its_file_is_still_written(self):
        vision = VisionEngine("adb", "device")
        with patch("subprocess.run", side_effect=self.replies()), \
                patch("core.vision_engine.time.monotonic", return_value=100):
            first = vision.get_engine_telemetry()
        with patch("subprocess.run", side_effect=self.replies(now=10020, modified=10019)), \
                patch("core.vision_engine.time.monotonic", return_value=120):
            second = vision.get_engine_telemetry()
        self.assertEqual(first["position_frame"], second["position_frame"])
        self.assertEqual(second["position_age"], 1)
        self.assertTrue(second["in_game"])

    def test_unverified_first_record_cannot_start_a_live_session(self):
        with patch("subprocess.run", side_effect=self.replies(metadata=False)):
            sample = VisionEngine("adb", "device").get_engine_telemetry()
        self.assertGreaterEqual(sample["position_age"], 15)
        self.assertFalse(sample["in_game"])

    def test_future_file_timestamp_cannot_prove_freshness(self):
        with patch("subprocess.run", side_effect=self.replies(modified=15000)):
            sample = VisionEngine("adb", "device").get_engine_telemetry()
        self.assertFalse(sample["in_game"])

    def test_device_switch_does_not_return_previous_devices_cached_position(self):
        controller = SimpleNamespace(adb_path="adb", device_id="first")
        vision = VisionEngine(controller=controller)
        with patch("subprocess.run", side_effect=self.replies(map_id=2)):
            first = vision.get_engine_telemetry()
        controller.device_id = "second"
        with patch("subprocess.run", side_effect=self.replies(map_id=7)) as read:
            second = vision.get_engine_telemetry()
        self.assertEqual(first["map_id"], 2)
        self.assertEqual(second["map_id"], 7)
        self.assertEqual(read.call_count, 2)
        self.assertTrue(all(call.args[0][2] == "second" for call in read.call_args_list))


if __name__ == "__main__":
    unittest.main()
