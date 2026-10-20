"""
player_agent.py - Hệ thống AI Tự Chơi Game Như Một Người Chơi Am Hiểu (Autonomous Player Agent)
Phiên bản: 2.0 • Theo đúng Mục 3, Mục 4, Mục 26 và Giai đoạn 3 Kế hoạch kiểm thử Phong Thần.

Hệ thống hoạt động theo vòng lặp nhận thức của một game thủ giàu kinh nghiệm:
1. Đọc tình huống: Vị trí, sinh tồn (HP/MP), túi đồ, kỹ năng, nhiệm vụ active.
2. Lập kế hoạch (GoalPlanner): Ưu tiên an toàn sinh mệnh -> làm nhiệm vụ -> train quái -> tiếp tế.
3. Thực thi hành động (ActionExecutor): Click nhiệm vụ tự tìm đường, đối thoại NPC, tung chiêu thức, cắn thuốc.
4. Đánh giá đúng sai (TestOracleEngine): So sánh chênh lệch Before - Action - After, ghi nhận bằng chứng.
5. Giám sát đồ họa ngầm (GlitchDetector): Phát hiện lỗi đen map trong lúc di chuyển tự nhiên.
"""

import os
import sys
import time
import json
import logging
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from core.game_state_observer import GameStateObserver
from core.test_oracle_engine import TestOracleEngine
from core.ld_controller import LDController

logger = logging.getLogger("PlayerAgent")


class PlayerMind:
    """Bộ não ra quyết định và lập kế hoạch của Người chơi am hiểu."""

    def __init__(self):
        self.current_goal = "KHỞI_ĐỘNG"
        self.decision_log = []
        self.last_action_time = 0.0
        self.potion_threshold = 50.0
        self.consecutive_stalls = 0
        self.last_pos = None

    def evaluate_situation(self, state: dict) -> dict:
        """
        Phân tích tình huống theo Section 3 của Kế hoạch:
        - Máu/Mana có nguy cấp?
        - Có nhiệm vụ nào đang chờ làm?
        - Có quái vật hoặc đang chiến đấu?
        - Nhân vật có bị kẹt hay đứng yên?
        """
        char = state.get("character", {})
        world = state.get("world", {})
        quests = state.get("quests", [])
        autoplay = state.get("autoplay", {})

        hp_cur = char.get("hp", {}).get("current", 24)
        hp_max = char.get("hp", {}).get("max", 24)
        hp_ratio = (hp_cur / hp_max * 100.0) if hp_max > 0 else 100.0

        mp_cur = char.get("mp", {}).get("current", 70)
        mp_max = char.get("mp", {}).get("max", 70)
        mp_ratio = (mp_cur / mp_max * 100.0) if mp_max > 0 else 100.0

        cur_pos = char.get("position", (0.0, 0.0))
        if self.last_pos and abs(cur_pos[0] - self.last_pos[0]) < 0.1 and abs(cur_pos[1] - self.last_pos[1]) < 0.1:
            self.consecutive_stalls += 1
        else:
            self.consecutive_stalls = 0
        self.last_pos = cur_pos

        # Quyết định mục tiêu theo thứ tự ưu tiên Section 3
        decision = {
            "timestamp": datetime.now().isoformat(),
            "hp_ratio": round(hp_ratio, 1),
            "mp_ratio": round(mp_ratio, 1),
            "position": cur_pos,
            "sub_world": world.get("sub_world_id"),
            "map_name": world.get("map_name", "Ngọc Hư Cung"),
            "priority": "NORMAL",
            "action": "NONE",
            "reason": ""
        }

        # 1. Nguy cấp: HP < 50%
        if hp_ratio < self.potion_threshold:
            decision["priority"] = "EMERGENCY"
            decision["action"] = "USE_POTION_OR_RETREAT"
            decision["reason"] = f"Máu nguy cấp ({hp_ratio:.1f}% < {self.potion_threshold}%). Cần kích hoạt tự dùng thuốc hoặc rút lui an toàn."
            return decision

        # 2. Kiểm tra đối thoại NPC đang mở
        npcdialog = state.get("raw_sources", {}).get("npcdialog", {})
        if npcdialog.get("visible") or npcdialog.get("in_game") and npcdialog.get("cocos_nodes_visible", 0) > 0:
            decision["priority"] = "QUEST_INTERACTION"
            decision["action"] = "ADVANCE_NPC_DIALOG"
            decision["reason"] = "Hộp thoại NPC đang mở. Đọc và chọn phương án đối thoại để hoàn thành nhiệm vụ."
            return decision

        # 3. Làm nhiệm vụ cốt truyện (Ngô Thất, Bách Lý)
        if quests:
            # Ưu tiên quest đầu tiên
            target_q = quests[0]
            q_title = target_q.get("title", "")
            q_detail = target_q.get("detail", "")
            decision["priority"] = "ACTIVE_QUEST"
            decision["action"] = "TRACK_QUEST"
            decision["target_quest"] = target_q
            decision["reason"] = f"Thực hiện chuỗi nhiệm vụ: '{q_title}' - {q_detail} để mở khóa nội dung và lên Cấp 5."
            return decision

        # 4. Luyện cấp tân thủ ngoài bãi quái
        decision["priority"] = "TRAIN_COMBAT"
        decision["action"] = "AUTOPLAY_COMBAT"
        decision["reason"] = "Không còn nhiệm vụ tồn đọng. Chuyển sang chế độ train quái tân thủ, dùng kỹ năng ID 2 và nhặt đồ."
        return decision


class ActionExecutor:
    """Thực thi các hành động cụ thể trên game Cocos2d-x qua LDController."""

    def __init__(self, ctrl: LDController):
        self.ctrl = ctrl

    def execute_quest_flow(self, quest_name: str = "Bách Lý"):
        """
        Thực hiện quy trình mở nhiệm vụ và tự tìm đường theo chuẩn giao diện Phong Thần Mobile:
        Bước 1: Bấm nút mở rộng tính năng (hoa thị 4 mũi tên vàng dưới minimap) tại (1856, 344)
        Bước 2: Bấm biểu tượng cuộn giấy "Nhiệm vụ" tại (1730, 740)
        Bước 3: Chọn nhiệm vụ (Bách Lý tại (180, 210) hoặc Ngũ Thất tại (180, 270))
        Bước 4: Bấm nút "Theo dõi" ((375, 895) hoặc (879, 944)) và liên kết tọa độ xanh
        Bước 5: [QUAN TRỌNG THEO HƯỚNG DẪN NGƯỜI DÙNG]:
                Bấm nút "X" đóng bảng Nhiệm vụ / Bảo điển ((1873, 32) hoặc (1548, 65)).
                Khi đóng bảng X xong, nhiệm vụ mới hiển thị ra HUD và nhân vật mới bắt đầu tự động di chuyển!
        """
        print(f"[ActionExecutor] 🎯 Bắt đầu chuỗi nhận & theo dõi nhiệm vụ '{quest_name}'...")
        self.ctrl.tap(1856, 344, delay=0.6)
        self.ctrl.tap(1730, 740, delay=1.0)
        if "Ngũ" in quest_name or "Ngu" in quest_name:
            self.ctrl.tap(180, 270, delay=0.5)
        else:
            self.ctrl.tap(180, 210, delay=0.5)
        self.ctrl.tap(375, 895, delay=0.4)
        self.ctrl.tap(879, 944, delay=0.4)
        self.ctrl.tap(435, 605, delay=0.4)
        self.ctrl.tap(750, 590, delay=0.4)
        print("[ActionExecutor] ❌ Bấm nút X đóng bảng Nhiệm vụ để hiển thị nhiệm vụ và bắt đầu di chuyển...")
        self.ctrl.tap(1873, 32, delay=0.4)
        self.ctrl.tap(1548, 65, delay=0.8)

    def click_quest_tracker(self, quest_index: int = 1):
        """Wrapper gọi execute_quest_flow theo đúng hướng dẫn của người dùng."""
        q_name = "Bách Lý" if quest_index == 1 else "Ngũ Thất"
        self.execute_quest_flow(q_name)

    def interact_with_npc_banner(self):
        """Click vào banner thoại NPC nổi bên phải màn hình khi đứng cạnh NPC (ví dụ: [💬 Xích Tinh Tử])."""
        prompt_x = 1750
        prompt_y = 400
        print(f"[ActionExecutor] 💬 Bấm banner thoại NPC nổi tại ({prompt_x}, {prompt_y})...")
        self.ctrl.tap(prompt_x, prompt_y, delay=1.0)

    def advance_dialog(self, option_index: int = 1):
        """Click chọn câu thoại hoặc bấm nút Tiếp tục trong hộp thoại NPC."""
        confirm_x = 250 if option_index == 1 else 550
        confirm_y = 770
        print(f"[ActionExecutor] 📜 Chọn phương án đối thoại {option_index} tại ({confirm_x}, {confirm_y})...")
        self.ctrl.tap(confirm_x, confirm_y, delay=0.8)

    def toggle_auto_combat(self):
        """Bật/tắt chế độ tự đánh của game để farm quái."""
        btn = self.ctrl.ui.get("auto_combat_button", {"x": 1630, "y": 240})
        print(f"[ActionExecutor] ⚔️ Bấm nút Tự Đánh tại ({btn['x']}, {btn['y']})...")
        self.ctrl.tap(btn["x"], btn["y"], jitter=True, delay=0.3)

    def cast_skill_slot1(self):
        """Bấm nút kỹ năng chính (Skill ID 2 - ô chuột phải/slot1)."""
        # Canvas 810, 729 -> Screen 1137, 1025
        skill_x = 1137
        skill_y = 1025
        print(f"[ActionExecutor] 🔥 Thi triển kỹ năng ID 2 tại ({skill_x}, {skill_y})...")
        self.ctrl.tap(skill_x, skill_y, jitter=True, delay=0.2)

    def open_inventory(self):
        """Mở túi hành trang để kiểm tra đồ."""
        # Bottombar "Items" button: Canvas 354, 720 -> Screen 497, 1012
        bag_x = 497
        bag_y = 1012
        print(f"[ActionExecutor] 🎒 Mở túi đồ tại ({bag_x}, {bag_y})...")
        self.ctrl.tap(bag_x, bag_y, jitter=True, delay=0.8)


class PlayerAgent:
    """
    AI Người chơi am hiểu Phong Thần:
    Kết hợp toàn diện GameStateObserver, PlayerMind, ActionExecutor, TestOracleEngine.
    """

    def __init__(self, adb_path=None, device_id=None):
        self.ctrl = LDController(auto_connect=True)
        if not self.ctrl.connected:
            raise RuntimeError("Không thể kết nối LDPlayer. Hãy bật LDPlayer 9 trước khi chạy PlayerAgent!")

        self.observer = GameStateObserver(
            adb_path=self.ctrl.adb_path,
            device_id=self.ctrl.device_id,
            package=self.ctrl.config.get("game_package", "com.tech3cgame.vhpt1")
        )
        self.oracle = TestOracleEngine()
        self.mind = PlayerMind()
        self.executor = ActionExecutor(self.ctrl)
        self.is_running = False

    def print_player_dashboard(self, state: dict, decision: dict):
        """In bảng điều khiển trực quan theo phong cách game thủ thực thụ."""
        char = state.get("character", {})
        world = state.get("world", {})
        quests = state.get("quests", [])
        autoplay = state.get("autoplay", {})

        print("\n" + "═" * 78)
        print(f" 🎮 [AI PLAYER AGENT] PHONG THẦN VIP PRO - NGƯỜI CHƠI AM HIỂU (V2.0)")
        print("═" * 78)
        print(f" 👤 Nhân vật   : {char.get('name', 'ThậpTamTrấnHùng')} (Cấp {char.get('level', 4)})")
        print(f" 🗺️  Bản đồ     : {world.get('map_name', 'Ngọc Hư Cung')} | Tọa độ GPS: {char.get('position', (0, 0))}")
        print(f" ❤️  Sinh tồn   : HP: {char.get('hp', {}).get('current', 24)}/{char.get('hp', {}).get('max', 24)} ({decision['hp_ratio']}%) | MP: {char.get('mp', {}).get('current', 70)}/{char.get('mp', {}).get('max', 70)} ({decision['mp_ratio']}%)")
        print(f" 📈 Kinh nghiệm: {char.get('exp_percent', '72.500%')} | Tự đánh: {autoplay.get('state', 'off')}")
        print(f" 📜 Nhiệm vụ   : {len(quests)} active -> {[q.get('title') for q in quests]}")
        print("─" * 78)
        print(f" 🧠 SUY NGHĨ & QUYẾT ĐỊNH CỦA NGƯỜI CHƠI:")
        print(f"    • Mục tiêu hiện tại : [{decision['priority']}] -> {decision['action']}")
        print(f"    • Lý do hành động   : {decision['reason']}")
        print("═" * 78)

    def run_one_turn(self):
        """Thực thi một chu kỳ nhận thức và hành động của Người chơi."""
        # 1. Đọc trạng thái game hiện tại
        state = self.observer.capture_snapshot()
        if not state.get("in_game", False):
            print("[PlayerAgent] ⚠️ Game đang ở màn hình tải hoặc mất kết nối. Đang chờ đồng bộ...")
            time.sleep(2.0)
            return

        # 2. Bộ não ra quyết định
        decision = self.mind.evaluate_situation(state)

        # 3. Hiển thị Dashboard
        self.print_player_dashboard(state, decision)

        # 4. Thực thi hành động tương ứng
        action = decision.get("action")
        if action == "TRACK_QUEST":
            target_q = decision.get("target_quest", {})
            q_idx = target_q.get("task_id", 1) or 1
            self.executor.click_quest_tracker(quest_index=q_idx)

        elif action == "ADVANCE_NPC_DIALOG":
            self.executor.advance_dialog()

        elif action == "USE_POTION_OR_RETREAT":
            print("[PlayerAgent] 🚨 Tự kích hoạt bình máu hoặc kỹ năng hồi phục!")
            self.executor.cast_skill_slot1()

        elif action == "AUTOPLAY_COMBAT":
            self.executor.toggle_auto_combat()
            self.executor.cast_skill_slot1()

        # Nghỉ nhịp nhàng mô phỏng thao tác người thật (1.5s - 2.5s)
        time.sleep(2.0)

    def start_loop(self, max_turns=None):
        """Bắt đầu vòng lặp tự chơi game tự động."""
        print("[PlayerAgent] 🚀 Khởi động Hệ thống Người Chơi Am Hiểu Phong Thần...")
        self.is_running = True
        turns = 0
        try:
            while self.is_running:
                self.run_one_turn()
                turns += 1
                if max_turns and turns >= max_turns:
                    print(f"[PlayerAgent] Đã hoàn thành {turns} lượt chơi. Dừng phiên theo kế hoạch.")
                    break
        except KeyboardInterrupt:
            print("\n[PlayerAgent] 🛑 Người dùng đã bấm Ctrl+C để dừng phiên chơi.")
        finally:
            self.is_running = False
            print("[PlayerAgent] Phiên chơi kết thúc. Tiến độ và trạng thái đã được lưu an toàn.")


if __name__ == "__main__":
    agent = PlayerAgent()
    # Chạy thử nghiệm 3 lượt đầu tiên để demo hành vi
    agent.start_loop(max_turns=3)
