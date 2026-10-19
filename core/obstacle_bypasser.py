import time
import math
import random

class ObstacleBypasser:
    """
    VIP PRO MAX Obstacle Bypass & Wall-Sliding Engine
    - Gặp vật cản (cây, đá, vách núi thông thường) -> TỰ TÌM ĐƯỜNG ĐI TIẾP
    - Tuyệt đối không coi vật cản hợp lệ là lỗi game!
    - Sử dụng thuật toán bám tường (Wall-sliding) và Minimap Pathfinding
    """

    def __init__(self, controller, joystick_only=True):
        self.ctrl = controller
        self.consecutive_blocks = 0
        self.joystick_only = joystick_only

    def reset(self):
        self.consecutive_blocks = 0

    def find_smart_exit(self, current_pos, current_heading_deg, plan=None, destination=None, breadcrumbs=None):
        """
        VIP PRO MAX Vision-Guided Smart Exit Finder:
        Tìm lối thoát tối ưu bằng Radar tầm nhìn 360 độ và bản đồ địa hình:
        1. Tuyệt đối loại trừ mọi góc trong phạm vi +/- 70 độ của góc đâm vào vật cản (current_heading_deg).
        2. Nếu đích đến (destination) cũng nằm cùng hướng với vật cản, TỪ CHỐI hướng về đích để không chui vào lại.
        3. Ưu tiên rút lui dọc theo vệt đường thông thoáng đã đi qua (Verified Breadcrumbs).
        4. Quét Radar tìm hành lang mở sâu nhất lệch xa vật cản.
        """
        self.consecutive_blocks += 1
        from core.ld_controller import game_to_joystick_angle
        blocked_ang = (current_heading_deg or 0.0) % 360
        print(f"[ObstacleBypasser] 👁️ Radar tầm nhìn 360° kích hoạt quét lối thoát (Lần {self.consecutive_blocks}, góc cản: {blocked_ang:.1f}°)...")

        # Ưu tiên 1: Lùi theo vệt di chuyển đã xác minh (Breadcrumbs)
        if breadcrumbs and len(breadcrumbs) >= 1 and current_pos:
            for bc in reversed(breadcrumbs):
                if math.dist(current_pos, bc) >= 0.55:
                    escape_ang = game_to_joystick_angle(bc[0] - current_pos[0], bc[1] - current_pos[1])
                    ang_diff = abs((escape_ang - blocked_ang + 180) % 360 - 180)
                    if ang_diff >= 75.0:
                        print(f"[ObstacleBypasser] 🔙 Rút lui theo vệt mở gần nhất hướng {escape_ang:.1f}° ra khỏi góc kẹt.")
                        return escape_ang

        # Ưu tiên 2: Quét Radar 360 độ và lọc góc an toàn
        if plan and hasattr(plan, "scan_exit_corridors") and current_pos:
            candidates = plan.scan_exit_corridors(current_pos, num_rays=16, max_dist=4.5)
            # Lọc các hướng có lối ra thực sự (open >= 1.0) VÀ lệch ít nhất 70 độ so với góc cản
            valid_exits = []
            for ang, depth in candidates:
                ang_diff = abs((ang - blocked_ang + 180) % 360 - 180)
                if ang_diff >= 70.0 and depth >= 1.0:
                    valid_exits.append((ang, depth, ang_diff))

            if valid_exits:
                if destination:
                    dest_ang = game_to_joystick_angle(destination[0] - current_pos[0], destination[1] - current_pos[1])
                    dest_diff = abs((dest_ang - blocked_ang + 180) % 360 - 180)
                    # Chỉ hướng về destination nếu destination KHÔNG nằm cùng hướng với góc cản
                    if dest_diff >= 65.0:
                        def score_exit(item):
                            ang, depth, _ = item
                            diff = abs((ang - dest_ang + 180) % 360 - 180)
                            return depth * 2.0 - (diff / 45.0)
                        valid_exits.sort(key=score_exit, reverse=True)
                        best_exit_angle = valid_exits[0][0]
                        print(f"[ObstacleBypasser] 🎯 Phát hiện lối thoát an toàn hướng {best_exit_angle:.1f}° (mở {valid_exits[0][1]:.2f} đơn vị).")
                        return best_exit_angle

                # Nếu destination cũng nằm sau vật cản hoặc không có destination, chọn góc mở sâu nhất lệch xa góc cản nhất
                valid_exits.sort(key=lambda it: it[1] * 1.5 + (it[2] / 60.0), reverse=True)
                best_exit_angle = valid_exits[0][0]
                print(f"[ObstacleBypasser] 🎯 Lối thoát an toàn nhất hướng {best_exit_angle:.1f}° (mở {valid_exits[0][1]:.2f} đơn vị, lệch cản {valid_exits[0][2]:.1f}°).")
                return best_exit_angle

        # Fallback an toàn: Quay 180 độ lùi lại
        return (blocked_ang + 180) % 360


    def bypass(self, current_heading_deg):
        """
        Khi bị chặn bởi vật cản thông thường, tìm góc thoát phù hợp nhất:
        - Nhịp 1: Bẻ góc 45 độ trượt dọc theo thân vật cản (Wall-slide phải)
        - Nhịp 2: Bẻ góc -45 độ trượt sang bên kia (Wall-slide trái)
        - Nhịp 3: Lùi nhẹ 1 bước rồi bẻ góc 90 độ
        - Nhịp 4: Nhấp điểm thoáng trên Minimap (hoặc lùi sâu nếu joystick_only)
        """
        self.consecutive_blocks += 1
        print(f"[ObstacleBypasser] 🔄 Gặp vật cản địa hình bình thường -> Tự động tìm đường lách qua (Lần {self.consecutive_blocks})...")

        def _safe_move(angle, dur):
            if hasattr(self.ctrl, "move_joystick"):
                self.ctrl.move_joystick(angle, duration_ms=dur)

        if self.consecutive_blocks == 1:
            new_heading = (current_heading_deg + 45) % 360
            _safe_move(new_heading, 400)
            time.sleep(0.05)
            return new_heading

        elif self.consecutive_blocks == 2:
            new_heading = (current_heading_deg - 90) % 360
            _safe_move(new_heading, 450)
            time.sleep(0.05)
            return new_heading

        elif self.consecutive_blocks == 3:
            # Lùi nhẹ 1 bước rồi bẻ vuông góc
            reverse_angle = (current_heading_deg + 180) % 360
            _safe_move(reverse_angle, 350)
            time.sleep(0.05)
            turn_angle = (current_heading_deg + 90) % 360
            _safe_move(turn_angle, 450)
            time.sleep(0.05)
            return turn_angle

        else:
            if self.joystick_only:
                # 100% Joystick: không mở minimap, lùi nhanh rồi bẻ góc đối diện
                reverse_angle = (current_heading_deg + 180) % 360
                _safe_move(reverse_angle, 400)
                time.sleep(0.05)
                turn_angle = (current_heading_deg - 90) % 360
                _safe_move(turn_angle, 450)
                time.sleep(0.05)
                self.reset()
                return turn_angle
            else:
                # Nhấp Minimap để Game Pathfinding kéo nhân vật vòng qua chướng ngại vật
                print("[ObstacleBypasser] 🗺️ Nhấp Minimap lân cận để tự động tìm đường vòng qua vật cản...")
                # Click vào vùng thoáng gần nhân vật trên Minimap
                self.ctrl.tap(1780, 160) # Mở map
                time.sleep(0.4)
                # Click điểm trung tâm thoáng
                self.ctrl.tap(600, 480)
                time.sleep(0.8)
                self.reset()
                return (current_heading_deg + 90) % 360
