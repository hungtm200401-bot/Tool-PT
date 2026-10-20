"""Game State Observer for Phong Than Mobile.

Parses real-time telemetry from /sdcard/Android/data/com.tech3cgame.vhpt1/files/
as specified in Section 26 of Ke_hoach_kiem_thu_Phong_Than.md.
"""

import json
import logging
import os
import subprocess
import time

logger = logging.getLogger("GameStateObserver")


class GameStateObserver:
    """Reads and aggregates live telemetry status files from Android device."""

    STATUS_FILES = {
        "pos": "pos-trace-status.json",
        "char": "charpanel-render-status.json",
        "map": "map-render-status.json",
        "quest": "questlist-render-status.json",
        "skill": "skillpanel-render-status.json",
        "skillring": "skillring-render-status.json",
        "inventory": "inventory-render-status.json",
        "settings": "settings-render-status.json",
        "autoplay": "autoplay-status.json",
        "bottombar": "bottombar-render-status.json",
        "chat": "chat-render-status.json",
        "npcdialog": "npcdialog-render-status.json",
        "team": "team-render-status.json",
    }

    def __init__(self, adb_path="adb.exe", device_id="emulator-5554", package="com.tech3cgame.vhpt1"):
        self.adb_path = adb_path
        self.device_id = device_id
        self.package = package
        self.remote_dir = f"/sdcard/Android/data/{package}/files"

    def read_remote_json(self, filename, timeout=2.0):
        """Read a remote status JSON file via ADB shell with timestamp."""
        remote_path = f"{self.remote_dir}/{filename}"
        script = f"date +%s; stat -c %Y {remote_path}; cat {remote_path}"
        cmd = [self.adb_path, "-s", self.device_id, "shell", script]
        try:
            res = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout,
                                 creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
            raw = (res.stdout or "").strip()
            if (hasattr(res, "returncode") and res.returncode != 0) or (not raw and res.stderr):
                cmd_su = [self.adb_path, "-s", self.device_id, "shell", "su", "0", "sh", "-c", f"'{script}'"]
                res_su = subprocess.run(cmd_su, capture_output=True, text=True, timeout=timeout,
                                        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
                if res_su and res_su.stdout:
                    raw = res_su.stdout.strip()

            lines = raw.split("\n", 2)
            age = None
            if len(lines) == 3 and lines[0].strip().isdigit() and lines[1].strip().isdigit():
                delta = int(lines[0].strip()) - int(lines[1].strip())
                age = float(max(0, delta)) if delta >= -2 else 3600.0
                raw = lines[2]
            data = json.loads(raw)
            return data, age
        except Exception as e:
            return None, None

    def capture_snapshot(self):
        """Capture a comprehensive, unified snapshot of active game state."""
        snapshot = {
            "timestamp": time.time(),
            "device_id": self.device_id,
            "package": self.package,
            "raw_sources": {},
            "source_ages": {},
            "character": {},
            "world": {},
            "quests": [],
            "skills": {},
            "autoplay": {},
            "ui": {},
            "in_game": False,
        }

        for key, fname in self.STATUS_FILES.items():
            data, age = self.read_remote_json(fname)
            if data is not None:
                snapshot["raw_sources"][key] = data
                snapshot["source_ages"][key] = age

        # 1. Parse position & map world info
        pos_data = snapshot["raw_sources"].get("pos")
        if pos_data:
            snapshot["in_game"] = bool(pos_data.get("in_game", False))
            snapshot["world"]["sub_world_id"] = pos_data.get("sub_world_id")
            snapshot["world"]["frames"] = pos_data.get("frames")
            player = pos_data.get("player", {})
            mps = player.get("mps")
            if isinstance(mps, list) and len(mps) == 2:
                snapshot["character"]["position"] = (round(float(mps[0]) / 256.0, 3), round(float(mps[1]) / 512.0, 3))
                snapshot["character"]["mps"] = mps
            snapshot["character"]["doing"] = player.get("doing", "unknown")
            snapshot["character"]["region_xy"] = player.get("region_xy")

        # 2. Parse character panel (Level, HP, MP, EXP, Server Name)
        char_data = snapshot["raw_sources"].get("char")
        if char_data:
            snap = char_data.get("snapshot", {})
            name_text = snap.get("Name", {}).get("text", {}).get("s")
            lvl_text = snap.get("Level", {}).get("text", {}).get("s")
            hp_text = snap.get("Life", {}).get("text", {}).get("s")
            mp_text = snap.get("Mana", {}).get("text", {}).get("s")
            exp_text = snap.get("Exp", {}).get("text", {}).get("s")
            net_text = snap.get("net", {}).get("text", {}).get("s")

            if name_text:
                snapshot["character"]["name"] = name_text
            if lvl_text and lvl_text.isdigit():
                snapshot["character"]["level"] = int(lvl_text)
            if hp_text and "/" in hp_text:
                try:
                    cur_hp, max_hp = [int(x) for x in hp_text.split("/", 1)]
                    snapshot["character"]["hp"] = {"current": cur_hp, "max": max_hp}
                except ValueError:
                    pass
            if mp_text and "/" in mp_text:
                try:
                    cur_mp, max_mp = [int(x) for x in mp_text.split("/", 1)]
                    snapshot["character"]["mp"] = {"current": cur_mp, "max": max_mp}
                except ValueError:
                    pass
            if exp_text:
                snapshot["character"]["exp_percent"] = exp_text
            if net_text:
                snapshot["world"]["server_host"] = net_text
            snapshot["ui"]["canvas"] = char_data.get("canvas", [1368, 768])

        # 3. Parse active map render status
        map_data = snapshot["raw_sources"].get("map")
        if map_data:
            mini = map_data.get("mini", {})
            snapshot["world"]["map_name"] = mini.get("name", "").strip()
            snapshot["world"]["map_pos_display"] = mini.get("pos", "").strip()
            snapshot["world"]["dialog_open"] = bool(
                map_data.get("world", {}).get("up") or map_data.get("nodes", {}).get("map", 0)
            )

        # 4. Parse active quests
        quest_data = snapshot["raw_sources"].get("quest")
        if quest_data:
            quest_info = quest_data.get("quest", {})
            rows = quest_info.get("rows", [])
            current_task = None
            for r in rows:
                if r.get("title"):
                    current_task = {"title": r.get("text", "").strip(), "detail": "", "task_id": r.get("task")}
                    snapshot["quests"].append(current_task)
                elif current_task is not None and not r.get("title"):
                    detail_text = r.get("text", "").strip()
                    current_task["detail"] = (current_task["detail"] + " " + detail_text).strip()

        # 5. Parse skills & shortcuts
        skillring = snapshot["raw_sources"].get("skillring")
        if skillring:
            snapshot["skills"]["active_right_skill"] = skillring.get("right_skill")
            snapshot["skills"]["all_ids"] = skillring.get("all_ids", [])
            snapshot["skills"]["skill_levels"] = skillring.get("skill_level_active", [])
            snapshot["skills"]["quick_slots"] = skillring.get("visible", [])

        # 6. Parse autoplay settings
        auto_data = snapshot["raw_sources"].get("autoplay")
        if auto_data:
            snapshot["autoplay"]["state"] = auto_data.get("fight_state", "off")
            snapshot["autoplay"]["settings"] = auto_data.get("settings", {})
            snapshot["autoplay"]["self_name"] = auto_data.get("self_name", "")

        return snapshot
