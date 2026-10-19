import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from core.ld_discovery import LDDiscovery, discover_adb_paths, parse_devices, parse_instances
from core.ld_controller import LDController
from core.vision_engine import VisionEngine


def result(stdout="", code=0):
    return SimpleNamespace(stdout=stdout, stderr="", returncode=code)


class DiscoveryTests(unittest.TestCase):
    def scan(self, entries, installed=(), running=(), preferred=None, boot_ids=None, names=None):
        def fake_run(args, **kwargs):
            if args[1:] == ["devices", "-l"]:
                return result("List of devices attached\n"+"\n".join(entries))
            serial = args[2]
            if args[3:5] == ["shell", "pm"]:
                return result("package:/data/app/game/base.apk" if serial in installed else "")
            if args[3:5] == ["shell", "pidof"]:
                return result("1234" if serial in running else "", 0 if serial in running else 1)
            if args[3:5] == ["shell", "cat"]:
                return result((boot_ids or {}).get(serial, ""))
            raise AssertionError(args)

        with patch("core.ld_discovery.discover_adb_paths", return_value=["X:/Portable LD/adb.exe"]), \
                patch.object(LDDiscovery, "_instance_names", return_value=names or {}), \
                patch("core.ld_discovery.run_quiet", side_effect=fake_run):
            return LDDiscovery({"adb_path": "auto", "device_id": "auto"}).scan(preferred)

    def test_device_parser_ignores_offline_and_unauthorized(self):
        output = "List of devices attached\nemulator-5580 device model:Test\nemulator-5554 offline\nphone unauthorized\n"
        self.assertEqual(parse_devices(output), ["emulator-5580"])

    def test_instance_parser_supports_named_instances_and_ignores_closed_ones(self):
        output = '7,"LD, game",1,2,1,99,100,1920,1080,280\n0,LDPlayer,0,0,0,-1,-1\n'
        self.assertEqual(parse_instances(output), [{"index": 7, "name": "LD, game"}])

    def test_custom_drive_and_directory_with_spaces_are_detected(self):
        with tempfile.TemporaryDirectory(prefix="ld_discovery_") as directory:
            install = Path(directory)/"Portable LD 9"
            install.mkdir()
            adb = install/"adb.exe"
            adb.touch()
            with patch("core.ld_discovery._running_directories", return_value=[]), \
                    patch("core.ld_discovery._registry_directories", return_value=[str(install)]), \
                    patch("core.ld_discovery._common_directories", return_value=[]), \
                    patch("core.ld_discovery.shutil.which", return_value=None), \
                    patch.dict(os.environ, {"LDPLAYER_HOME": ""}):
                paths = discover_adb_paths({"adb_path": "Z:/Old machine/adb.exe"})
            self.assertEqual(paths, [str(adb)])

    def test_game_running_is_preferred_over_first_device(self):
        discovered = self.scan(["emulator-5554 device", "127.0.0.1:5639 device"],
                               installed=("emulator-5554", "127.0.0.1:5639"),
                               running=("127.0.0.1:5639",))
        self.assertEqual(discovered["selected"]["serial"], "127.0.0.1:5639")

    def test_one_instance_with_game_installed_is_selected(self):
        discovered = self.scan(["emulator-5554 device", "emulator-5570 device"], installed=("emulator-5570",))
        self.assertEqual(discovered["selected"]["serial"], "emulator-5570")

    def test_multiple_equally_suitable_instances_require_a_selection(self):
        discovered = self.scan(["emulator-5554 device", "emulator-5570 device"],
                               installed=("emulator-5554", "emulator-5570"),
                               running=("emulator-5554", "emulator-5570"))
        self.assertIsNone(discovered["selected"])
        self.assertEqual(len(discovered["devices"]), 2)

    def test_user_selection_is_kept_even_if_another_instance_runs_game(self):
        discovered = self.scan(["emulator-5554 device", "emulator-5570 device"],
                               running=("emulator-5554",), preferred="emulator-5570")
        self.assertEqual(discovered["selected"]["serial"], "emulator-5570")

    def test_missing_user_selection_does_not_switch_to_another_instance(self):
        discovered = self.scan(["emulator-5554 device"], preferred="emulator-5570")
        self.assertIsNone(discovered["selected"])

    def test_usb_phone_is_not_automatically_selected(self):
        discovered = self.scan(["USB-PHONE-123 device", "emulator-5570 device"], running=("USB-PHONE-123",))
        self.assertEqual(discovered["selected"]["serial"], "emulator-5570")
        self.assertEqual(len(discovered["devices"]), 1)

    def test_offline_emulator_never_becomes_a_ready_connection(self):
        discovered = self.scan(["emulator-5554 offline", "127.0.0.1:5639 unauthorized"])
        self.assertIsNone(discovered["selected"])
        self.assertEqual(discovered["devices"], [])

    def test_aliases_of_one_instance_are_not_treated_as_two_ld_windows(self):
        serials = ("emulator-5566", "127.0.0.1:5567")
        boot = "12345678-1234-1234-1234-123456789abc"
        discovered = self.scan([f"{serial} device" for serial in serials],
                               boot_ids=dict.fromkeys(serials, boot))
        self.assertEqual(len(discovered["devices"]), 1)
        self.assertIsNotNone(discovered["selected"])

    def test_missing_installation_has_no_hardcoded_fallback(self):
        with patch("core.ld_discovery.discover_adb_paths", return_value=[]):
            discovered = LDDiscovery({}).scan()
        self.assertIsNone(discovered["adb_path"])
        self.assertIsNone(discovered["selected"])

    def test_console_identified_bridge_address_is_supported(self):
        discovered = self.scan(["192.168.10.8:6341 device"], names={
            "192.168.10.8:6341": {"name": "LD cầu mạng", "index": 4}
        })
        self.assertEqual(discovered["selected"]["serial"], "192.168.10.8:6341")

    def test_distinct_console_instances_are_not_merged_by_a_cloned_boot_id(self):
        serials = ("emulator-5566", "emulator-5568")
        boot = "12345678-1234-1234-1234-123456789abc"
        discovered = self.scan([f"{serial} device" for serial in serials],
                               boot_ids=dict.fromkeys(serials, boot),
                               names={serial: {"index": i, "name": f"LD {i}"} for i, serial in enumerate(serials)})
        self.assertEqual(len(discovered["devices"]), 2)
        self.assertIsNone(discovered["selected"])


class ConnectionTests(unittest.TestCase):
    def controller(self):
        return LDController(auto_connect=False)

    def test_no_input_is_sent_without_selected_device(self):
        ctrl = self.controller()
        with self.assertRaisesRegex(RuntimeError, "Chưa kết nối"):
            ctrl._device_command("shell", "input", "tap", "10", "10")

    def test_input_timeout_is_not_replayed(self):
        ctrl = self.controller()
        ctrl.adb_path, ctrl.device_id = "test-adb", "emulator-5554"
        with patch("core.ld_controller.subprocess.run",
                   side_effect=subprocess.TimeoutExpired(["adb", "input"], 8)) as run:
            with self.assertRaisesRegex(RuntimeError, "không gửi lại"):
                ctrl._input("tap", 100, 200)

        run.assert_called_once()

    def test_rejected_input_is_not_replayed(self):
        ctrl = self.controller()
        ctrl.adb_path, ctrl.device_id = "test-adb", "emulator-5554"
        with patch("core.ld_controller.subprocess.run", return_value=result("", 1)) as run:
            with self.assertRaisesRegex(RuntimeError, "từ chối"):
                ctrl._input("tap", 100, 200)

        run.assert_called_once()

    def test_persistent_shell_pipe_writes_input_command_to_stdin(self):
        from unittest.mock import MagicMock
        ctrl = self.controller()
        ctrl.adb_path, ctrl.device_id = "test-adb", "emulator-5554"
        mock_pipe = MagicMock()
        mock_pipe.stdin = MagicMock()
        mock_pipe.poll.return_value = None
        ctrl._shell_pipe = mock_pipe
        ctrl._shell_pipe_device = "emulator-5554"
        with patch("core.ld_controller.subprocess.run") as run:
            ctrl._input("tap", 100, 200)
            run.assert_not_called()
        mock_pipe.stdin.write.assert_called_once_with(b"input tap 100 200\n")
        mock_pipe.stdin.flush.assert_called_once()

    def test_explicit_rescan_updates_adb_and_serial_after_offline_device_is_refused(self):
        ctrl = self.controller()
        ctrl.adb_path, ctrl.device_id = "old-adb", "old-device"
        selected = {"adb_path": "D:/New LD/adb.exe", "serial": "emulator-5582", "name": "LD phụ"}
        discovered = {"adb_path": selected["adb_path"], "devices": [selected],
                      "selected": selected, "message": "connected"}
        with patch("core.ld_controller.run_quiet", return_value=result("offline", 1)), \
                patch.object(LDDiscovery, "scan", return_value=discovered) as scan:
            with self.assertRaisesRegex(RuntimeError, "Dò lại LD"):
                ctrl.ensure_connection()
            scan.assert_not_called()
            self.assertEqual(ctrl.device_id, "old-device")
            ctrl.refresh_connection()
        self.assertEqual(ctrl._device_command("get-state"),
                         ["D:/New LD/adb.exe", "-s", "emulator-5582", "get-state"])

    def test_telemetry_follows_selected_controller_instead_of_old_defaults(self):
        ctrl = SimpleNamespace(adb_path="D:/LD/adb.exe", device_id="127.0.0.1:5659")
        vision = VisionEngine("old-adb", "old-device", controller=ctrl)
        with patch("subprocess.run", return_value=result("{}")) as run:
            vision.get_engine_telemetry()
        for call in run.call_args_list:
            self.assertEqual(call.args[0][:3], ["D:/LD/adb.exe", "-s", "127.0.0.1:5659"])

    def test_telemetry_does_not_query_an_arbitrary_device_when_disconnected(self):
        with patch("subprocess.run") as run:
            telemetry = VisionEngine().get_engine_telemetry()
        run.assert_not_called()
        self.assertIsNone(telemetry["position"])


class ConnectionControlTests(unittest.TestCase):
    def test_device_switching_is_disabled_during_a_route(self):
        from gui.app_gui import AppGUI
        from unittest.mock import Mock
        widgets = {name: Mock() for name in ("ld_selector", "btn_detect_ld", "btn_start",
                                              "lbl_connection_info", "lbl_device_summary")}
        app = SimpleNamespace(
            ctrl=SimpleNamespace(available_devices=[{
                "name": "LD 2", "serial": "emulator-5582", "game_running": True, "game_installed": True
            }], device_id="emulator-5582", device_name="LD 2", connected=True,
                connection_status="connected", adb_path="D:/LD/adb.exe"),
            engine=SimpleNamespace(is_running=True), _detecting_ld=False, **widgets
        )
        AppGUI._render_ld_connection(app)
        self.assertEqual(app.ld_selector.configure.call_args.kwargs["state"], "disabled")
        self.assertEqual(app.btn_detect_ld.configure.call_args.kwargs["state"], "disabled")
        self.assertEqual(app.btn_start.configure.call_args.kwargs["state"], "disabled")

    def test_selection_callback_cannot_change_the_device_while_running(self):
        from gui.app_gui import AppGUI
        from unittest.mock import Mock
        ctrl = SimpleNamespace(select_device=Mock())
        app = SimpleNamespace(ctrl=ctrl, _detecting_ld=False, engine=SimpleNamespace(is_running=True))
        AppGUI.action_select_ld(app, "LD khác")
        ctrl.select_device.assert_not_called()

    def test_selection_remains_locked_until_stopping_worker_has_exited(self):
        from gui.app_gui import AppGUI
        from unittest.mock import Mock
        ctrl = SimpleNamespace(select_device=Mock())
        worker = SimpleNamespace(is_alive=lambda: True)
        app = SimpleNamespace(ctrl=ctrl, _detecting_ld=False,
                              engine=SimpleNamespace(is_running=False, worker_thread=worker))
        AppGUI.action_select_ld(app, "LD khác")
        ctrl.select_device.assert_not_called()


if __name__ == "__main__":
    unittest.main()
