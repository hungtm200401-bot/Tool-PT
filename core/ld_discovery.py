"""Find local LDPlayer installations and ready ADB connections on this PC."""

import csv
import json
import os
import re
import shutil
import subprocess


AUTO_VALUES = {"", "auto", "automatic"}
LOCAL_SERIAL = re.compile(r"^(?:emulator-\d+|(?:127\.0\.0\.1|localhost|\[::1\]):\d+)$")


def explicit(value):
    value = str(value or "").strip()
    return None if value.casefold() in AUTO_VALUES else value


def run_quiet(args, timeout=4):
    try:
        return subprocess.run(
            args, capture_output=True, text=True, encoding="utf-8", errors="replace",
            timeout=timeout, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0)
        )
    except (OSError, subprocess.TimeoutExpired):
        return None


def _running_directories():
    if os.name != "nt":
        return []
    powershell = os.path.join(os.environ.get("SystemRoot", r"C:\Windows"),
                              "System32", "WindowsPowerShell", "v1.0", "powershell.exe")
    script = (
        "[Console]::OutputEncoding=[System.Text.UTF8Encoding]::new(); "
        "@(Get-Process -Name dnplayer,ldplayer,ldconsole,dnconsole,LdVBoxHeadless "
        "-ErrorAction SilentlyContinue | ForEach-Object { try { $_.Path } catch {} }) "
        "| ConvertTo-Json -Compress"
    )
    result = run_quiet([powershell, "-NoProfile", "-NonInteractive", "-Command", script])
    if result is None:
        return []
    try:
        paths = json.loads(result.stdout or "[]") or []
        return [os.path.dirname(path) for path in ([paths] if isinstance(paths, str) else paths) if path]
    except (ValueError, TypeError):
        return []


def _install_directory(value):
    value = os.path.expandvars(str(value or "").strip())
    if not value:
        return None
    if value.startswith('"'):
        value = value.split('"', 2)[1]
    else:
        value = re.sub(r",\s*-?\d+\s*$", "", value)
    if value.lower().endswith(".exe"):
        value = os.path.dirname(value)
    return value


def _registry_directories():
    if os.name != "nt":
        return []
    import winreg
    directories = []
    uninstall = r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall"
    for hive in (winreg.HKEY_CURRENT_USER, winreg.HKEY_LOCAL_MACHINE):
        for view in (winreg.KEY_WOW64_64KEY, winreg.KEY_WOW64_32KEY):
            try:
                with winreg.OpenKey(hive, uninstall, 0, winreg.KEY_READ | view) as root:
                    for index in range(winreg.QueryInfoKey(root)[0]):
                        try:
                            with winreg.OpenKey(root, winreg.EnumKey(root, index)) as entry:
                                name = str(winreg.QueryValueEx(entry, "DisplayName")[0]).casefold()
                                if not any(token in name for token in ("ldplayer", "leidian", "雷电", "雷電")):
                                    continue
                                for field in ("InstallLocation", "DisplayIcon", "UninstallString"):
                                    try:
                                        directory = _install_directory(winreg.QueryValueEx(entry, field)[0])
                                        if directory:
                                            directories.append(directory)
                                    except OSError:
                                        pass
                        except OSError:
                            continue
            except OSError:
                continue
            for executable in ("dnplayer.exe", "ldplayer.exe", "ldconsole.exe"):
                key = rf"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\{executable}"
                try:
                    with winreg.OpenKey(hive, key, 0, winreg.KEY_READ | view) as entry:
                        directory = _install_directory(winreg.QueryValueEx(entry, None)[0])
                        if directory:
                            directories.append(directory)
                except OSError:
                    pass
    return directories


def _common_directories():
    bases = [os.environ.get(key) for key in ("ProgramFiles", "ProgramFiles(x86)", "LOCALAPPDATA")]
    if os.name == "nt":
        import ctypes
        drive_mask = ctypes.windll.kernel32.GetLogicalDrives()
        for index in range(26):
            drive = chr(65+index) + ":\\"
            if drive_mask & (1 << index) and ctypes.windll.kernel32.GetDriveTypeW(drive) == 3:
                bases.extend([drive, os.path.join(drive, "Games"), os.path.join(drive, "Apps")])
    directories = []
    for base in filter(None, bases):
        try:
            for entry in os.scandir(base):
                if entry.is_dir() and entry.name.casefold().startswith(("ldplayer", "leidian", "changzhi")):
                    directories.append(entry.path)
                    for child in os.scandir(entry.path):
                        if child.is_dir() and child.name.casefold().startswith(("ldplayer", "leidian")):
                            directories.append(child.path)
        except OSError:
            continue
    return directories


def discover_adb_paths(config):
    paths = []
    manual = explicit(config.get("adb_path"))
    if manual:
        paths.append(os.path.expandvars(os.path.expanduser(manual)))
    directories = [_install_directory(os.environ.get("LDPLAYER_HOME"))]
    directories += _running_directories() + _registry_directories() + _common_directories()
    for directory in filter(None, directories):
        for relative in ("adb.exe", os.path.join("adb", "adb.exe"), os.path.join("platform-tools", "adb.exe")):
            paths.append(os.path.join(directory, relative))
    from_path = shutil.which("adb.exe") or shutil.which("adb")
    if from_path:
        paths.append(from_path)
    unique = []
    seen = set()
    for path in paths:
        path = os.path.abspath(path)
        key = os.path.normcase(path)
        if key not in seen and os.path.isfile(path):
            seen.add(key)
            unique.append(path)
    return unique


def parse_devices(output):
    devices = []
    for line in output.splitlines():
        parts = line.split()
        if len(parts) >= 2 and parts[1] == "device":
            devices.append(parts[0])
    return devices


def parse_instances(output):
    instances = []
    for row in csv.reader(output.splitlines()):
        if len(row) < 7 or not row[0].strip().isdigit():
            continue
        if row[4].strip() == "1":
            instances.append({"index": int(row[0]), "name": row[1].strip() or f"LD {row[0]}"})
    return instances


class LDDiscovery:
    def __init__(self, config):
        self.config = config

    def _instance_names(self, adb_path):
        directory = os.path.dirname(adb_path)
        console = next((os.path.join(directory, name) for name in ("ldconsole.exe", "dnconsole.exe")
                        if os.path.isfile(os.path.join(directory, name))), None)
        if console is None:
            return {}
        result = run_quiet([console, "list2"])
        if result is None or result.returncode != 0:
            return {}
        names = {}
        for instance in parse_instances(result.stdout):
            serial_result = run_quiet([
                console, "adb", "--index", str(instance["index"]), "--command", "get-serialno"
            ])
            if serial_result and serial_result.returncode == 0:
                for line in serial_result.stdout.splitlines():
                    if (re.fullmatch(r"[A-Za-z0-9_.:\[\]-]+", line.strip())
                            and line.strip() not in {"unknown", "offline"}):
                        names[line.strip()] = instance
        return names

    def scan(self, preferred_device=None):
        candidates = discover_adb_paths(self.config)
        devices = []
        working_adb = None
        preferred = explicit(preferred_device) or explicit(self.config.get("device_id"))
        package = self.config.get("game_package", "com.tech3cgame.vhpt1")
        if not re.fullmatch(r"[A-Za-z0-9_]+(?:\.[A-Za-z0-9_]+)+", package):
            raise ValueError("Tên gói game trong cấu hình không hợp lệ.")
        for adb_path in candidates:
            names = self._instance_names(adb_path)
            result = run_quiet([adb_path, "devices", "-l"])
            if result is None or result.returncode != 0:
                continue
            working_adb = working_adb or adb_path
            serials = [serial for serial in parse_devices(result.stdout)
                       if LOCAL_SERIAL.fullmatch(serial) or serial in names or serial == preferred]
            for serial in serials:
                prefix = [adb_path, "-s", serial, "shell"]
                installed = run_quiet(prefix + ["pm", "path", package])
                running = run_quiet(prefix + ["pidof", package])
                boot = run_quiet(prefix + ["cat", "/proc/sys/kernel/random/boot_id"])
                boot_id = boot.stdout.strip() if boot and boot.returncode == 0 else ""
                if not re.fullmatch(r"[0-9a-fA-F-]{36}", boot_id):
                    boot_id = ""
                instance = names.get(serial, {})
                alias = next((device for device in devices
                              if boot_id and device.get("boot_id") == boot_id
                              and not (instance.get("index") is not None and device.get("index") is not None
                                       and instance["index"] != device["index"])), None)
                if alias:
                    if serial == preferred:
                        devices.remove(alias)
                    else:
                        continue
                devices.append({
                    "serial": serial, "adb_path": adb_path,
                    "name": instance.get("name", "LDPlayer"), "index": instance.get("index"),
                    "boot_id": boot_id,
                    "game_installed": bool(installed and installed.returncode == 0
                                           and "package:" in installed.stdout),
                    "game_running": bool(running and running.returncode == 0
                                         and re.search(r"\d", running.stdout))
                })
            if devices:
                break  # One ADB server lists the ready devices; avoid swapping server versions.
        selected = None
        if preferred:
            selected = next((device for device in devices if device["serial"] == preferred), None)
        elif devices:
            ranked = sorted(devices, key=lambda device: (device["game_running"], device["game_installed"]), reverse=True)
            score = (ranked[0]["game_running"], ranked[0]["game_installed"])
            best = [device for device in ranked if (device["game_running"], device["game_installed"]) == score]
            if len(best) == 1:
                selected = best[0]
        if selected:
            message = f"Đã kết nối {selected['name']} — {selected['serial']}."
        elif not candidates:
            message = "Chưa tìm thấy LDPlayer. Mở LDPlayer trên máy rồi bấm ‘Dò lại LD’."
        elif preferred and devices:
            message = f"LD đã chọn ({preferred}) chưa sẵn sàng. Chọn một LD đang online trong danh sách."
        elif devices:
            message = f"Có {len(devices)} LD đang online; chọn LD cần điều khiển trong danh sách."
        else:
            message = "Đã tìm thấy ADB nhưng LD chưa online. Mở LDPlayer và bật kết nối ADB, rồi dò lại."
        return {"adb_path": selected["adb_path"] if selected else working_adb,
                "devices": devices, "selected": selected, "message": message}
