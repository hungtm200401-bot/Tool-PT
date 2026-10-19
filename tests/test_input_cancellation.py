import threading
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from core.ld_controller import LDController


class InputCancellationTests(unittest.TestCase):
    def controller(self):
        controller = LDController(auto_connect=False)
        controller.adb_path, controller.device_id = "test-adb", "test-device"
        return controller

    def test_stopped_mission_cannot_send_a_new_tap(self):
        controller = self.controller()
        controller.set_input_gate(lambda: False)
        with patch("core.ld_controller.subprocess.run") as send:
            with self.assertRaises(InterruptedError):
                controller.tap(100, 200, jitter=False, delay=0)
        send.assert_not_called()
        self.assertEqual(controller.input_sequence, 0)

    def test_cancel_still_works_after_normal_input_has_been_blocked(self):
        controller = self.controller()
        controller.set_input_gate(lambda: False)
        with patch("core.ld_controller.subprocess.run", return_value=SimpleNamespace(returncode=0)) as send:
            controller.cancel_movement()
            controller.close_map_dialog(_cancel=True)
        self.assertEqual(send.call_count, 2)

    def test_stop_during_session_check_cannot_release_the_original_tap(self):
        controller = self.controller()
        allowed = {"running": True}
        controller._session = ("test-adb", "test-device", "boot")
        controller.set_input_gate(lambda: allowed["running"])
        def session_check():
            allowed["running"] = False
            return "boot"
        controller._boot_id = session_check
        with patch("core.ld_controller.subprocess.run") as send:
            with self.assertRaises(InterruptedError):
                controller.tap(100, 200, jitter=False, delay=0)
        send.assert_not_called()

    def test_a_tap_queued_before_stop_is_rejected_when_the_channel_unblocks(self):
        controller = self.controller()
        allowed = {"running": True}
        controller.set_input_gate(lambda: allowed["running"])
        started = threading.Event()
        errors = []
        def queued_tap():
            started.set()
            try:
                controller.tap(100, 200, jitter=False, delay=0)
            except Exception as error:
                errors.append(error)
        with patch("core.ld_controller.subprocess.run") as send:
            with controller._command_lock:
                worker = threading.Thread(target=queued_tap)
                worker.start()
                self.assertTrue(started.wait(1))
                allowed["running"] = False
            worker.join(timeout=2)
            self.assertFalse(worker.is_alive())
            send.assert_not_called()
        self.assertEqual(len(errors), 1)
        self.assertIsInstance(errors[0], InterruptedError)


if __name__ == "__main__":
    unittest.main()
