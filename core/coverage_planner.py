"""Survey the local map and keep a coverage ledger in game coordinates."""

import json
import heapq
import math
import os
import tempfile
import time
import hashlib

import cv2
import numpy as np


def atomic_json(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    temp_path = None
    try:
        with tempfile.NamedTemporaryFile(
            "w", encoding="utf-8", dir=os.path.dirname(path), delete=False
        ) as stream:
            temp_path = stream.name
            json.dump(data, stream, ensure_ascii=False, indent=2)
        os.replace(temp_path, path)
    finally:
        if temp_path and os.path.exists(temp_path):
            os.remove(temp_path)


class MapSurveyor:
    """Pan the map, using its reported cover rectangle to stitch observed tiles.

    The new map panel scales the legacy surface into a larger viewport. The
    reported cover is in map pixels (16 pixels per displayed game coordinate),
    so it also provides an exact conversion for destination taps.
    """

    def __init__(self, controller, vision, settings, keep_running, notify, on_progress=None):
        self.ctrl = controller
        self.vision = vision
        self.settings = settings
        self.keep_running = keep_running
        self.notify = notify
        self.on_progress = on_progress
        self.screen_size = getattr(controller, "screen_size", (
            controller.config.get("resolution", {}).get("width", 1920),
            controller.config.get("resolution", {}).get("height", 1080)
        ))

    def viewport(self):
        base = self.settings.get("map_viewport", [408, 132, 1792, 954])
        width, height = self.screen_size
        return [base[0] * width / 1920, base[1] * height / 1080,
                base[2] * width / 1920, base[3] * height / 1080]

    def read_map(self):
        telemetry = self.vision.get_engine_telemetry()
        raw = telemetry.get("map_data", {})
        surface = raw.get("surface", {})
        if (not telemetry.get("map_dialog_open") or not surface.get("have_pic")
                or surface.get("pic_pending") or telemetry.get("map_age", 0) > 15):
            raise RuntimeError("Chưa đọc được bề mặt bản đồ lân cận.")
        pic = surface.get("pic", [])
        cover = surface.get("cover", [])
        if len(pic) != 4 or len(cover) != 4 or min(pic[2:]) <= 0 or min(cover[2:]) <= 0:
            raise RuntimeError("Kích thước hoặc tọa độ vùng map không hợp lệ.")
        if pic[2] * pic[3] > int(self.settings.get("max_map_pixels", 8000000)):
            raise RuntimeError("Kích thước ảnh map vượt giới hạn khảo sát.")
        return telemetry

    def open_map(self):
        telemetry = self.vision.get_engine_telemetry()
        previous_frame = telemetry.get("map_frame")
        changed = False
        if not telemetry.get("map_dialog_open"):
            self.ctrl.open_local_map()
            changed = True
        elif telemetry.get("map_data", {}).get("world", {}).get("up"):
            tab = self.ctrl.ui["local_map_tab"]
            self.ctrl.tap(tab["x"], tab["y"], jitter=False, delay=0.3)
            changed = True
        for _ in range(24):
            if not self.keep_running():
                raise InterruptedError()
            try:
                sample = self.read_map()
                if not changed or sample.get("map_frame") != previous_frame:
                    return sample
            except RuntimeError:
                pass
            time.sleep(0.15)
        raise RuntimeError("Tool mở map nhưng chưa nhận được hình và tọa độ map.")

    def close_map(self):
        if not self.vision.get_engine_telemetry().get("map_dialog_open"):
            return
        self.ctrl.close_map_dialog()
        for _ in range(24):
            if not self.vision.get_engine_telemetry().get("map_dialog_open"):
                return
            time.sleep(0.15)
        raise RuntimeError("Bảng map chưa đóng; chưa bắt đầu giám sát chặng đi.")

    def pan_to(self, left, top, map_id, observe=None):
        unchanged = 0
        for _ in range(12):
            if not self.keep_running():
                raise InterruptedError()
            for _wait_idx in range(16):
                try:
                    telemetry = self.read_map()
                    break
                except RuntimeError:
                    tel_probe = self.vision.get_engine_telemetry() if self.vision else {}
                    if not tel_probe.get("map_dialog_open"):
                        try:
                            telemetry = self.open_map()
                            break
                        except Exception:
                            pass
                    time.sleep(0.15)
            else:
                telemetry = self.read_map()
            if telemetry["map_id"] != map_id:
                raise RuntimeError("Map thay đổi trong lúc đang quan sát.")
            surface = telemetry["map_data"]["surface"]
            cx, cy, cw, ch = surface["cover"]
            dx, dy = left - cx, top - cy
            if observe:
                observe(telemetry)
            if abs(dx) <= 8 and abs(dy) <= 8:
                return telemetry
            x1, y1, x2, y2 = self.viewport()
            vw = x2 - x1
            vh = y2 - y1
            mx, my = (x1 + x2) / 2, (y1 + y2) / 2
            pad_x = 0.15 * vw
            pad_y = 0.15 * vh
            safe_x_min, safe_x_max = x1 + pad_x, x2 - pad_x
            safe_y_min, safe_y_max = y1 + pad_y, y2 - pad_y
            max_sx = (safe_x_max - safe_x_min) / 2
            max_sy = (safe_y_max - safe_y_min) / 2
            sx = max(-max_sx, min(max_sx, -dx * vw / max(1, cw)))
            sy = max(-max_sy, min(max_sy, -dy * vh / max(1, ch)))
            end_x = int(round(max(safe_x_min, min(safe_x_max, mx + sx))))
            end_y = int(round(max(safe_y_min, min(safe_y_max, my + sy))))
            self.ctrl.swipe(int(round(mx)), int(round(my)), end_x, end_y, duration_ms=400)
            deadline = time.monotonic() + 4
            after = telemetry
            while time.monotonic() < deadline:
                if not self.keep_running():
                    raise InterruptedError()
                time.sleep(0.15)
                try:
                    after = self.read_map()
                    if (after.get("map_frame") != telemetry.get("map_frame")
                            or after.get("map_data", {}).get("surface", {}).get("cover", [])[:2] != [cx, cy]):
                        break
                except RuntimeError:
                    tel_probe = self.vision.get_engine_telemetry() if self.vision else {}
                    if not tel_probe.get("map_dialog_open"):
                        try:
                            after = self.open_map()
                            break
                        except Exception:
                            pass
            if after.get("map_data", {}).get("surface", {}).get("cover", [])[:2] == [cx, cy]:
                unchanged += 1
                if unchanged >= 2:
                    break
            else:
                unchanged = 0
        for _wait_idx in range(16):
            try:
                telemetry = self.read_map()
                break
            except RuntimeError:
                tel_probe = self.vision.get_engine_telemetry() if self.vision else {}
                if not tel_probe.get("map_dialog_open"):
                    try:
                        telemetry = self.open_map()
                        break
                    except Exception:
                        pass
                time.sleep(0.15)
        else:
            telemetry = self.read_map()
        if observe:
            observe(telemetry)
        return telemetry

    @staticmethod
    def _axis_positions(origin, extent, window):
        last = max(origin, origin + extent - window)
        values = list(range(int(origin), int(last) + 1, max(1, int(window * 0.75))))
        if not values or values[-1] != int(last):
            values.append(int(last))
        return values

    @staticmethod
    def render_survey_preview(atlas, known, max_width=1600, max_height=1200):
        """Show the original stitched map with clear overlays for read regions."""
        height, width = known.shape
        scale = min(1.0, max_width / width, max_height / height)
        size = (max(1, round(width * scale)), max(1, round(height * scale)))
        image = cv2.resize(atlas, size, interpolation=cv2.INTER_AREA)
        observed = cv2.resize(known, size, interpolation=cv2.INTER_NEAREST) > 0
        # Keep the actual game-map pixels visible underneath the overlay. The
        # darker, neutral unread area makes the blue read-area wash easy to see.
        dimmed = (image.astype(np.float32) * 0.28 + np.array([23, 29, 38], dtype=np.float32) * 0.72)
        image[~observed] = np.clip(dimmed[~observed], 0, 255).astype(np.uint8)
        if np.any(observed):
            # BGR blue overlay: distinct from the green travel trace in plan view.
            tint = np.array([195, 115, 35], dtype=np.float32)
            visible = image[observed].astype(np.float32)
            image[observed] = np.clip(visible * 0.66 + tint * 0.34, 0, 255).astype(np.uint8)
            edge = cv2.morphologyEx(observed.astype(np.uint8), cv2.MORPH_GRADIENT,
                                    np.ones((3, 3), np.uint8)) > 0
            image[edge] = (255, 220, 35)  # cyan edge after BGR -> RGB conversion
        return cv2.cvtColor(image, cv2.COLOR_BGR2RGB)

    def survey(self):
        first = self.open_map()
        pic = [int(value) for value in first["map_data"]["surface"]["pic"]]
        map_id = first["map_id"]
        px, py, pw, ph = pic
        atlas = np.zeros((ph, pw, 3), dtype=np.uint8)
        known = np.zeros((ph, pw), dtype=np.uint8)
        observed_pixels = 0

        def observe(telemetry):
            nonlocal observed_pixels
            if (first.get("position") is not None and telemetry.get("position") is not None
                    and math.dist(first["position"], telemetry["position"]) > 0.4):
                raise RuntimeError("Nhân vật đang di chuyển trong lúc đọc map; giữ tiến độ để lập lại tuyến sau.")
            frame = self.ctrl.capture_frame()
            if frame is None:
                return
            self.screen_size = (frame.shape[1], frame.shape[0])
            x1, y1, x2, y2 = map(int, self.viewport())
            crop = frame[y1:y2, x1:x2]
            if not crop.size:
                return
            cx, cy, cw, ch = map(int, telemetry["map_data"]["surface"]["cover"])
            tile = cv2.resize(crop, (cw, ch), interpolation=cv2.INTER_AREA)
            ax1, ay1 = max(0, cx-px), max(0, cy-py)
            ax2, ay2 = min(pw, cx-px+cw), min(ph, cy-py+ch)
            if ax2 <= ax1 or ay2 <= ay1:
                return
            tx, ty = ax1-(cx-px), ay1-(cy-py)
            atlas[ay1:ay2, ax1:ax2] = tile[ty:ty+ay2-ay1, tx:tx+ax2-ax1]
            known_region = known[ay1:ay2, ax1:ax2]
            observed_pixels += int(np.count_nonzero(known_region == 0))
            known_region[:] = 255
            if self.on_progress:
                self.on_progress(atlas, known, observed_pixels / known.size)

        observe(first)
        cw, ch = first["map_data"]["surface"]["cover"][2:]
        xs = self._axis_positions(px, pw, cw)
        ys = self._axis_positions(py, ph, ch)
        count = 0
        for row, top in enumerate(ys):
            for left in xs if row % 2 == 0 else reversed(xs):
                self.pan_to(left, top, map_id, observe)
                count += 1
                self.notify(f"Tự quan sát map: vùng {count}/{len(xs)*len(ys)}.")
        return map_id, pic, atlas, known

    def pin(self, world_x, world_y, map_id):
        telemetry = self.open_map()
        surface = telemetry["map_data"]["surface"]
        px, py, pw, ph = surface["pic"]
        cx, cy, cw, ch = surface["cover"]
        target_x, target_y = world_x * 16, world_y * 16
        left = max(px, min(px + max(0, pw-cw), target_x-cw/2))
        top = max(py, min(py + max(0, ph-ch), target_y-ch/2))
        telemetry = self.pan_to(left, top, map_id)
        if telemetry["map_id"] != map_id:
            raise RuntimeError("Không ghim điểm vì nhân vật đã sang map khác.")
        cx, cy, cw, ch = telemetry["map_data"]["surface"]["cover"]
        if not (cx + 2 <= target_x <= cx+cw-2 and cy + 2 <= target_y <= cy+ch-2):
            raise RuntimeError("Điểm cần đi chưa nằm trong vùng map quan sát được.")
        x1, y1, x2, y2 = self.viewport()
        screen_x = x1 + (target_x-cx) * (x2-x1) / cw
        screen_y = y1 + (target_y-cy) * (y2-y1) / ch
        self.ctrl.tap(round(screen_x), round(screen_y), jitter=False, delay=0.1)
        self.close_map()


class CoveragePlan:
    """Expanding clockwise rings with a separate ledger for actual observations."""

    VERSION = 4

    def __init__(self, data, atlas, known):
        self.data = data
        self.atlas = atlas
        self.known = known
        self.revision = 0
        self._images_saved = False
        walkable = self._ground_mask(atlas, known)
        self.ground = walkable
        self.visited = np.zeros(known.shape, np.uint8)
        self.inspected = np.zeros(known.shape, np.uint8)
        for row, left, right in data.get("visited_runs", []):
            self.visited[row, left:right] = 1
        for row, left, right in data.get("inspected_runs", []):
            self.inspected[row, left:right] = 1
        self.navigation_step = 8
        height, width = walkable.shape
        rows, cols = math.ceil(height/8), math.ceil(width/8)
        padded = np.pad(walkable, ((0, rows*8-height), (0, cols*8-width)))
        preferred = padded.reshape(rows, 8, cols, 8).mean(axis=(1, 3)) >= 0.6
        # Texture is uncertain: prefer clear corridors, but allow a costly probe
        # across ambiguous artwork. Only observed collisions become hard barriers.
        gray = cv2.cvtColor(atlas, cv2.COLOR_BGR2GRAY)
        visible = ((known > 0) & (gray > 45) & (gray < 250)).astype(np.uint8)
        padded_visible = np.pad(visible, ((0, rows*8-height), (0, cols*8-width)))
        self.navigation = padded_visible.reshape(rows, 8, cols, 8).mean(axis=(1, 3)) >= 0.15
        self.terrain_cost = np.where(preferred, 1.0, 12.0)
        self._base_navigation = self.navigation.copy()
        self._refresh_obstacles()
        _, self.components = cv2.connectedComponents(self.navigation.astype(np.uint8), connectivity=4)

    def _refresh_obstacles(self):
        now = time.time()
        self.data["obstacles"] = [item for item in self.data.get("obstacles", []) if item["expires"] > now]
        self.navigation = self._base_navigation.copy()
        for item in self.data["obstacles"]:
            row, col = item["cell"]
            if 0 <= row < self.navigation.shape[0] and 0 <= col < self.navigation.shape[1]:
                self.navigation[row, col] = False
        _, self.components = cv2.connectedComponents(self.navigation.astype(np.uint8), connectivity=4)

    def is_walkable(self, x, y):
        """Kiểm tra một tọa độ game (x, y) có phải là mặt đất thông thoáng đi được hay không."""
        bx, by = self.data["bounds"][:2]
        px, py = x * 16 - bx, y * 16 - by
        row, col = int(py // 8), int(px // 8)
        if 0 <= row < self.navigation.shape[0] and 0 <= col < self.navigation.shape[1]:
            return bool(self.navigation[row, col])
        return False

    def cast_ray(self, start_pos, angle_deg, max_dist=5.0, step=0.25):
        """
        Bắn tia tầm nhìn (Vision Raycast) từ start_pos theo hướng angle_deg:
        - Nếu xuất phát từ đường thoáng: đo cự ly tối đa trước khi chạm vật cản.
        - Nếu xuất phát từ trong hoặc sát vật cản: đo tìm hướng thoát ra bãi thoáng nhanh nhất
          kết hợp với độ rộng của hành lang mở phía ngoài.
        """
        rad = math.radians(angle_deg)
        cos_a, sin_a = math.cos(rad), math.sin(rad)
        d = 0.0
        start_free = self.is_walkable(start_pos[0], start_pos[1])
        if start_free:
            while d < max_dist:
                d += step
                tx = start_pos[0] + d * cos_a
                ty = start_pos[1] + d * sin_a
                if not self.is_walkable(tx, ty):
                    return max(0.0, d - step)
            return max_dist
        else:
            dist_to_exit = None
            open_depth = 0.0
            while d < max_dist:
                d += step
                tx = start_pos[0] + d * cos_a
                ty = start_pos[1] + d * sin_a
                if self.is_walkable(tx, ty):
                    if dist_to_exit is None:
                        dist_to_exit = d
                    open_depth += step
                elif dist_to_exit is not None:
                    break
            if dist_to_exit is not None and open_depth >= 0.5:
                return max(0.5, open_depth * 1.5 - dist_to_exit * 0.5)
            return 0.0

    def scan_exit_corridors(self, current_pos, num_rays=16, max_dist=4.5):
        """
        Quét Radar 360 độ (360° Open Space Radar) xung quanh nhân vật để tìm các hướng thoát kẹt:
        Trả về danh sách các góc (angle_deg, open_distance) sắp xếp theo độ thông thoáng giảm dần.
        """
        results = []
        angle_step = 360.0 / num_rays
        for i in range(num_rays):
            ang = (i * angle_step) % 360
            depth = self.cast_ray(current_pos, ang, max_dist=max_dist, step=0.25)
            results.append((ang, depth))
        results.sort(key=lambda item: item[1], reverse=True)
        return results


    @staticmethod
    def _ground_mask(atlas, known):
        gray = cv2.cvtColor(atlas, cv2.COLOR_BGR2GRAY)
        hsv = cv2.cvtColor(atlas, cv2.COLOR_BGR2HSV)
        values = gray.astype(np.float32)
        mean = cv2.GaussianBlur(values, (9, 9), 0)
        variance = np.maximum(0, cv2.GaussianBlur(values**2, (9, 9), 0)-mean**2)
        ground = ((gray > 65) & (gray < 249) & (hsv[:, :, 1] < 135)
                  & (variance < 24**2) & (known > 0))
        ground = cv2.morphologyEx(ground.astype(np.uint8), cv2.MORPH_CLOSE, np.ones((5, 5), np.uint8))
        ground[(known == 0) | (gray > 248)] = 0
        ground[:5, :] = ground[-5:, :] = ground[:, :5] = ground[:, -5:] = 0
        return ground

    @classmethod
    def build(cls, map_id, bounds, atlas, known, settings, anchor=None):
        size = max(16, int(settings.get("cell_size", 96)))
        spacing = max(16, int(settings.get("ring_spacing_pixels", size)))
        overlap = max(0.1, min(0.5, float(settings.get("inspection_overlap", 0.25))))
        strategy = settings.get("strategy", "corners_first")
        ground = cls._ground_mask(atlas, known)
        clearance = cv2.distanceTransform(np.pad(ground, 1), cv2.DIST_L2, 3)[1:-1, 1:-1]
        height, width = known.shape
        if not np.any(ground):
            raise RuntimeError("Ảnh map chưa cho thấy vùng có thể khảo sát; giữ nguyên tiến độ.")
        ax, ay = (width/2, height/2) if anchor is None else (anchor[0]*16-bounds[0], anchor[1]*16-bounds[1])
        valid_y, valid_x = np.where(clearance >= 3)
        if not len(valid_x):
            raise RuntimeError("Chưa tìm được mốc gốc có khoảng trống an toàn.")
        closest = np.argmin((valid_x-ax)**2 + (valid_y-ay)**2)
        ax, ay = int(valid_x[closest]), int(valid_y[closest])
        covered = np.zeros(known.shape, np.uint8)
        points = []
        occupied = set()

        def add_point(x, y, ring, purpose, is_perimeter=False, batch=None, sequence=0):
            key = (int(x)//8, int(y)//8)
            if key in occupied:
                return
            occupied.add(key)
            options = [[round((bounds[0]+x)/16, 3), round((bounds[1]+y)/16, 3)]]
            # Alternative approach stays within the same ring neighbourhood.
            for dx, dy in ((8, 0), (-8, 0), (0, 8), (0, -8)):
                nx, ny = int(x)+dx, int(y)+dy
                if 0 <= nx < width and 0 <= ny < height and clearance[ny, nx] >= 2:
                    options.append([round((bounds[0]+nx)/16, 3), round((bounds[1]+ny)/16, 3)])
                    if len(options) == 3:
                        break
            actual_batch = ring if batch is None else batch
            points.append({"id": f"r{ring}:{int(y)}:{int(x)}", "row": int(y)//size,
                           "col": int(x)//size, "batch": actual_batch, "ring": ring,
                           "angle": math.atan2(y-ay, x-ax) % (2*math.pi),
                           "purpose": purpose, "options": options, "state": "pending",
                           "is_perimeter": is_perimeter, "sequence": sequence,
                           "attempts": 0, "total_attempts": 0})
            cv2.circle(covered, (int(x), int(y)), max(8, int(spacing/(2*(1-overlap)))), 1, -1)

        max_radius = math.hypot(max(ax, width-ax), max(ay, height-ay))
        num_rings = math.ceil(max_radius/spacing)

        if strategy in {"corners_first", "perimeter_first"}:
            # Phase 1: Đi 4 góc & toàn bộ đường viền mép bản đồ trước (Full Corners & Outer Perimeter First)
            # TUYỆT ĐỐI không đi mốc gốc giữa map trước!
            num_labels, labels = cv2.connectedComponents((ground > 0).astype(np.uint8), connectivity=8)
            anchor_lbl = labels[ay, ax] if 0 <= ay < height and 0 <= ax < width and labels[ay, ax] > 0 else 0
            if anchor_lbl == 0 and num_labels > 1:
                counts = np.bincount(labels.flat)
                anchor_lbl = int(np.argmax(counts[1:]) + 1)
            main_ground = (labels == anchor_lbl).astype(np.uint8) if anchor_lbl > 0 else (ground > 0).astype(np.uint8)

            # 1.1: Định vị chính xác 4 góc map (Tây Bắc, Đông Bắc, Đông Nam, Tây Nam)
            corner_bounds = [
                (0, 0, "góc tây bắc"),
                (width - 1, 0, "góc đông bắc"),
                (width - 1, height - 1, "góc đông nam"),
                (0, height - 1, "góc tây nam")
            ]
            coords_all = np.argwhere(main_ground > 0)
            corner_pts = []
            if len(coords_all):
                for cx_bound, cy_bound, cname in corner_bounds:
                    dists = (coords_all[:, 1] - cx_bound)**2 + (coords_all[:, 0] - cy_bound)**2
                    best_c = np.argmin(dists)
                    corner_y, corner_x = coords_all[best_c]
                    corner_pts.append((corner_x, corner_y, cname))

            # Sắp xếp 4 góc map bắt đầu từ góc gần nhân vật nhất
            if corner_pts:
                start_c_idx = int(np.argmin([(p[0]-ax)**2 + (p[1]-ay)**2 for p in corner_pts]))
                ordered_corners = corner_pts[start_c_idx:] + corner_pts[:start_c_idx]
                for c_seq, (cx, cy, cname) in enumerate(ordered_corners):
                    add_point(cx, cy, ring=1, purpose=f"khám phá {cname}",
                              is_perimeter=True, batch=1, sequence=c_seq * 100)

            # 1.2: Tạo chu vi viền ngoài (Outer Perimeter Loop) liên tục khép kín kết nối quanh 4 góc
            closed = cv2.morphologyEx(main_ground, cv2.MORPH_CLOSE, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (11, 11)))
            contours, _ = cv2.findContours(closed, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
            dense_pts = []
            if contours:
                c_main = max(contours, key=cv2.contourArea)
                approx = cv2.approxPolyDP(c_main, 14.0, True)
                raw_verts = [tuple(map(int, p[0])) for p in approx]
                for i in range(len(raw_verts)):
                    p1 = raw_verts[i]
                    p2 = raw_verts[(i+1) % len(raw_verts)]
                    d = math.hypot(p2[0]-p1[0], p2[1]-p1[1])
                    steps = max(1, math.ceil(d / (spacing * 0.75)))
                    for s in range(steps):
                        f = s / steps
                        dense_pts.append((int(round(p1[0] + (p2[0]-p1[0])*f)),
                                          int(round(p1[1] + (p2[1]-p1[1])*f))))

            if dense_pts:
                start_idx = int(np.argmin([(p[0]-ax)**2 + (p[1]-ay)**2 for p in dense_pts]))
                dense_pts = dense_pts[start_idx:] + dense_pts[:start_idx]
                for seq_idx, (px, py) in enumerate(dense_pts):
                    px = max(0, min(width-1, px))
                    py = max(0, min(height-1, py))
                    if clearance[py, px] < 2:
                        patch_y = max(0, py - spacing // 2), min(height, py + spacing // 2)
                        patch_x = max(0, px - spacing // 2), min(width, px + spacing // 2)
                        sub = (main_ground[patch_y[0]:patch_y[1], patch_x[0]:patch_x[1]] > 0) & (clearance[patch_y[0]:patch_y[1], patch_x[0]:patch_x[1]] >= 2)
                        if np.any(sub):
                            coords = np.argwhere(sub)
                            dists = (coords[:, 1] + patch_x[0] - px)**2 + (coords[:, 0] + patch_y[0] - py)**2
                            best_idx = np.argmin(dists)
                            px = patch_x[0] + int(coords[best_idx][1])
                            py = patch_y[0] + int(coords[best_idx][0])
                    if ground[py, px] > 0:
                        add_point(px, py, ring=1, purpose="quét góc & viền mép",
                                  is_perimeter=True, batch=1, sequence=500 + seq_idx)

            # Phase 2: Đi các vòng tròn khoanh vùng đồng tâm mở rộng (Concentric Inner Rings)
            # Thêm mốc gốc tâm bản đồ làm mốc khởi đầu của Phase 2
            add_point(ax, ay, ring=2, purpose="mốc gốc tâm bản đồ", is_perimeter=False, batch=2, sequence=0)

            for ring in range(1, num_rings + 1):
                radius = ring * spacing
                count = max(8, math.ceil(2 * math.pi * radius / (spacing * 0.85)))
                for angle in np.linspace(0, 2*math.pi, count, endpoint=False):
                    tx = int(round(ax + radius * math.cos(angle)))
                    ty = int(round(ay + radius * math.sin(angle)))
                    tx = max(0, min(width - 1, tx))
                    ty = max(0, min(height - 1, ty))
                    if main_ground[ty, tx] > 0 and covered[ty, tx] == 0:
                        if clearance[ty, tx] >= 2:
                            add_point(tx, ty, ring=ring+2, purpose="quét vòng bên trong",
                                      is_perimeter=False, batch=ring+2)
                        else:
                            patch_y = max(0, ty - spacing // 2), min(height, ty + spacing // 2)
                            patch_x = max(0, tx - spacing // 2), min(width, tx + spacing // 2)
                            sub = (main_ground[patch_y[0]:patch_y[1], patch_x[0]:patch_x[1]] > 0) & (clearance[patch_y[0]:patch_y[1], patch_x[0]:patch_x[1]] >= 2)
                            if np.any(sub):
                                coords = np.argwhere(sub)
                                dists = (coords[:, 1] + patch_x[0] - tx)**2 + (coords[:, 0] + patch_y[0] - ty)**2
                                best_idx = np.argmin(dists)
                                bx_snap = patch_x[0] + int(coords[best_idx][1])
                                by_snap = patch_y[0] + int(coords[best_idx][0])
                                if covered[by_snap, bx_snap] == 0:
                                    add_point(bx_snap, by_snap, ring=ring+2, purpose="quét vòng bên trong",
                                              is_perimeter=False, batch=ring+2)

            for top in range(0, height, max(8, spacing)):
                for left in range(0, width, max(8, spacing)):
                    patch = (main_ground[top:top+spacing, left:left+spacing] > 0) & (covered[top:top+spacing, left:left+spacing] == 0)
                    if not np.any(patch):
                        continue
                    score = clearance[top:top+spacing, left:left+spacing].copy()
                    score[~patch] = -1
                    yy, xx = np.unravel_index(np.argmax(score), score.shape)
                    x, y = left + xx, top + yy
                    add_point(x, y, ring=num_rings+3, purpose="khép diện tích bên trong còn thiếu",
                              is_perimeter=False, batch=num_rings+3)

            points.sort(key=lambda point: (point["batch"], point.get("sequence", 0), point["angle"]))
        else:
            add_point(ax, ay, ring=0, purpose="mốc gốc", is_perimeter=False, batch=0)
            for ring in range(1, num_rings+1):
                radius = ring*spacing
                is_outer = (ring >= num_rings - 1)
                count = max(8, math.ceil(2*math.pi*radius/(spacing*0.85)))
                for angle in np.linspace(0, 2*math.pi, count, endpoint=False):
                    tx = round(ax+radius*math.cos(angle))
                    ty = round(ay+radius*math.sin(angle))
                    tx = max(0, min(width-1, tx))
                    ty = max(0, min(height-1, ty))
                    if clearance[ty, tx] >= 2:
                        add_point(tx, ty, ring, "quét vòng", is_perimeter=is_outer)
                    elif ground[ty, tx] > 0:
                        add_point(tx, ty, ring, "quét vòng mép", is_perimeter=True)
                    else:
                        patch_y = max(0, ty-spacing//2), min(height, ty+spacing//2)
                        patch_x = max(0, tx-spacing//2), min(width, tx+spacing//2)
                        g_sub = ground[patch_y[0]:patch_y[1], patch_x[0]:patch_x[1]]
                        if np.any(g_sub):
                            coords = np.argwhere(g_sub > 0)
                            dists = (coords[:, 1] + patch_x[0] - tx)**2 + (coords[:, 0] + patch_y[0] - ty)**2
                            best_idx = np.argmin(dists)
                            bx_snap = patch_x[0] + int(coords[best_idx][1])
                            by_snap = patch_y[0] + int(coords[best_idx][0])
                            add_point(bx_snap, by_snap, ring, "quét vòng mép", is_perimeter=True)

            corner_targets = [
                (0, 0, "góc tây bắc"), (width-1, 0, "góc đông bắc"),
                (0, height-1, "góc tây nam"), (width-1, height-1, "góc đông nam")
            ]
            coords_all = np.argwhere(ground > 0)
            if len(coords_all):
                for cx_bound, cy_bound, cname in corner_targets:
                    dists = (coords_all[:, 1] - cx_bound)**2 + (coords_all[:, 0] - cy_bound)**2
                    best_c = np.argmin(dists)
                    corner_y, corner_x = coords_all[best_c]
                    add_point(corner_x, corner_y, num_rings + 1, f"khám phá {cname}", is_perimeter=True)

            for top in range(0, height, max(8, spacing)):
                for left in range(0, width, max(8, spacing)):
                    patch = (ground[top:top+spacing, left:left+spacing] > 0) & (covered[top:top+spacing, left:left+spacing] == 0)
                    if not np.any(patch):
                        continue
                    score = clearance[top:top+spacing, left:left+spacing].copy()
                    score[~patch] = -1
                    yy, xx = np.unravel_index(np.argmax(score), score.shape)
                    x, y = left+xx, top+yy
                    add_point(x, y, max(1, math.ceil(math.hypot(x-ax, y-ay)/spacing)), "khép biên / nhánh còn thiếu", is_perimeter=True)
            points.sort(key=lambda point: (point["ring"], point["angle"]))

        if len(points) > 20000:
            raise RuntimeError("Map tạo quá nhiều điểm; cần hiệu chỉnh khoảng cách vòng trước khi chạy.")
        return cls({
            "version": cls.VERSION, "map_id": map_id, "bounds": bounds,
            "strategy": strategy, "anchor": [(bounds[0]+ax)/16, (bounds[1]+ay)/16],
            "cell_size": size, "ring_spacing_pixels": spacing,
            "inspection_radius": max(0, float(settings.get("inspection_radius", 0))),
            "inspection_calibrated": bool(settings.get("inspection_calibrated", False)),
            "observed_fraction": float(np.mean(known > 0)),
            "targets": points, "trace": [], "active_id": None, "active_path": [], "obstacles": []
        }, atlas, known)


    @classmethod
    def load(cls, directory, map_id, store=None):
        prefix = os.path.join(directory, f"map_{map_id}")
        if not os.path.exists(prefix + ".json"):
            for root, dirs, files in os.walk(directory):
                if f"map_{map_id}.json" in files:
                    directory = root
                    prefix = os.path.join(directory, f"map_{map_id}")
                    break
        try:
            data = None
            if os.path.exists(prefix + ".json"):
                with open(prefix + ".json", encoding="utf-8") as stream:
                    data = json.load(stream)
            elif store:
                data = store.load_checkpoint(f"route:{directory}:{map_id}")
            if data is None:
                return None
            if store and os.path.exists(prefix + ".json"):
                try:
                    store.checkpoint(f"route:{directory}:{map_id}", data)
                except Exception:
                    pass
            assets = data.get("assets", {})
            atlas_path = os.path.join(directory, os.path.basename(assets["atlas"])) if assets else prefix+".png"
            known_path = os.path.join(directory, os.path.basename(assets["known"])) if assets else prefix+"_known.png"
            atlas = cv2.imread(atlas_path)
            known = cv2.imread(known_path, cv2.IMREAD_GRAYSCALE)
            if (data.get("version") != cls.VERSION or data.get("map_id") != map_id
                    or atlas is None or known is None or not data.get("targets")):
                return None
            if list(atlas.shape[:2][::-1]) != data["bounds"][2:] or known.shape != atlas.shape[:2]:
                return None
            if assets:
                digest = hashlib.sha256(atlas.tobytes()+known.tobytes()).hexdigest()
                if digest != assets.get("digest"):
                    return None
            for point in data["targets"]:
                if point["state"] not in {"done", "deferred"}:
                    point["state"] = "pending"
                if point["state"] != "deferred":
                    point["attempts"] = 0
            data["resume_target_id"] = data.get("resume_target_id") or data.get("active_id")
            data["active_id"] = None
            data["active_path"] = []
            data["trace"].append(None)  # Never draw a trip across an app restart.
            plan = cls(data, atlas, known)
            plan._images_saved = True
            return plan
        except (OSError, ValueError, KeyError, TypeError):
            return None

    def save(self, directory, store=None):
        prefix = os.path.join(directory, f"map_{self.data['map_id']}")
        os.makedirs(directory, exist_ok=True)
        if not self._images_saved:
            digest = hashlib.sha256(self.atlas.tobytes()+self.known.tobytes()).hexdigest()
            stem = os.path.basename(prefix)+"_"+digest[:16]
            atlas_path = os.path.join(directory, stem+".png")
            known_path = os.path.join(directory, stem+"_known.png")
            if not cv2.imwrite(atlas_path + ".next.png", self.atlas):
                raise OSError("Không lưu được ảnh map đã quan sát.")
            os.replace(atlas_path + ".next.png", atlas_path)
            if not cv2.imwrite(known_path+".next.png", self.known):
                raise OSError("Không lưu được vùng map đã quan sát.")
            os.replace(known_path+".next.png", known_path)
            self.data["assets"] = {"atlas": os.path.basename(atlas_path), "known": os.path.basename(known_path), "digest": digest}
            self._images_saved = True
        self.data["visited_runs"] = self._runs(self.visited)
        self.data["inspected_runs"] = self._runs(self.inspected)
        if store:
            store.checkpoint(f"route:{directory}:{self.data['map_id']}", self.data)
        atomic_json(prefix + ".json", self.data)

    @staticmethod
    def _runs(mask):
        results = []
        for row in np.flatnonzero(np.any(mask, axis=1)):
            changes = np.diff(np.pad(mask[row].astype(np.int8), (1, 1)))
            results.extend([[int(row), int(left), int(right)] for left, right in
                            zip(np.flatnonzero(changes == 1), np.flatnonzero(changes == -1))])
        return results

    def coverage(self):
        denominator = max(1, int(np.count_nonzero(self.ground)))
        return {"travelled_fraction": float(np.count_nonzero((self.visited > 0) & (self.ground > 0))/denominator),
                "inspected_fraction": float(np.count_nonzero((self.inspected > 0) & (self.ground > 0))/denominator),
                "inspection_calibrated": self.data.get("inspection_calibrated", False),
                "unknown_pixels": int(np.count_nonzero(self.known == 0))}

    def complete(self):
        stats = self.coverage()
        return (all(point["state"] == "done" for point in self.data["targets"])
                and stats["unknown_pixels"] == 0 and stats["inspection_calibrated"]
                and stats["inspected_fraction"] >= 0.99)

    def is_route_complete(self):
        """True only when every planned point was reached and verified."""
        targets = self.data.get("targets", [])
        return bool(targets) and all(point["state"] == "done" for point in targets)

    def progress_summary(self):
        targets = self.data.get("targets", [])
        total = len(targets)
        done = sum(point["state"] == "done" for point in targets)
        retry = sum(point["state"] == "retry" for point in targets)
        pending = sum(point["state"] == "pending" for point in targets)
        percent = (done / max(1, total)) * 100
        max_ring = max((p.get("batch", 0) for p in targets), default=0)
        return {
            "total": total, "done": done, "retry": retry, "pending": pending,
            "percent": percent, "max_ring": max_ring, "is_complete": self.is_route_complete()
        }

    def next_target(self, max_attempts):
        eligible = []
        for point in self.data["targets"]:
            if point["state"] in {"pending", "retry"} and point["attempts"] < max_attempts:
                has_walkable = any(self.is_walkable(opt[0], opt[1]) for opt in point.get("options", []))
                if not has_walkable and point.get("options"):
                    point["state"] = "deferred"
                    point["reason"] = "Mốc nằm trong vùng chướng ngại vật/vật cản"
                    continue
                eligible.append(point)

        resume = self.data.get("resume_target_id")
        if resume:
            interrupted = next((point for point in eligible if point["id"] == resume), None)
            if interrupted:
                return interrupted
            self.data["resume_target_id"] = None
        if eligible:
            # Ưu tiên tuyệt đối theo đúng luật chỉ định:
            # 1. 4 góc chính của bản đồ (khám phá góc đông bắc/tây bắc/đông nam/tây nam)
            # 2. Toàn bộ viền mép chu vi bên ngoài (is_perimeter = True)
            # 3. Các vòng tròn khoanh vùng đồng tâm bên trong (batch 2, 3, 4...)
            def priority_key(p):
                is_corner = 0 if "khám phá góc" in p.get("purpose", "").lower() else 1
                is_perim = 0 if p.get("is_perimeter") else 1
                state_prio = 0 if p["state"] == "pending" else 1
                return (p["batch"], is_corner, is_perim, state_prio, p.get("sequence", 0))

            eligible.sort(key=priority_key)
            return eligible[0]
        return None

    def add_inspection_gaps(self):
        """After the rings, revisit uncovered visible ground with a finite budget."""
        if (not self.data.get("inspection_calibrated") or self.data.get("gap_passes", 0) >= 2
                or self.data.get("inspection_radius", 0) <= 0):
            return 0
        missing = (self.ground > 0) & (self.inspected == 0)
        if not np.any(missing) or self.coverage()["inspected_fraction"] >= 0.99:
            return 0
        self.data["gap_passes"] = self.data.get("gap_passes", 0)+1
        radius = max(8, round(self.data["inspection_radius"]*16))
        stride = max(8, radius)
        batch = max(point["batch"] for point in self.data["targets"])+1
        bx, by = self.data["bounds"][:2]
        added = []
        for top in range(0, missing.shape[0], stride):
            for left in range(0, missing.shape[1], stride):
                candidates = np.argwhere(missing[top:top+stride, left:left+stride])
                if not len(candidates):
                    continue
                y, x = candidates[len(candidates)//2]+(top, left)
                added.append({"id": f"gap:{self.data['gap_passes']}:{y}:{x}", "row": int(y)//self.data["cell_size"],
                              "col": int(x)//self.data["cell_size"], "batch": batch, "ring": batch,
                              "purpose": "kiểm tra phần hình ảnh còn thiếu", "state": "pending",
                              "options": [[float((x+bx)/16), float((y+by)/16)]], "attempts": 0, "total_attempts": 0})
                if len(added) >= 512:
                    break
            if len(added) >= 512:
                break
        self.data["targets"].extend(added)
        self.revision += 1
        return len(added)

    @staticmethod
    def destination(target):
        return target["options"][target["attempts"] % len(target["options"])]

    def _snap(self, position, radius):
        bx, by = self.data["bounds"][:2]
        px, py = position[0]*16-bx, position[1]*16-by
        row, col = int(py//8), int(px//8)
        reach = math.ceil(radius/8)
        y1, x1 = max(0, row-reach), max(0, col-reach)
        y2, x2 = min(self.navigation.shape[0], row+reach+1), min(self.navigation.shape[1], col+reach+1)
        if x2 <= x1 or y2 <= y1:
            return None
        free = np.argwhere(self.navigation[y1:y2, x1:x2])
        if not len(free):
            return None
        free += (y1, x1)
        distances = (free[:, 0]*8+4-py)**2 + (free[:, 1]*8+4-px)**2
        nearest = int(np.argmin(distances))
        return tuple(map(int, free[nearest])) if distances[nearest] <= radius**2 else None

    def _line_clear(self, start, end):
        steps = max(abs(end[0]-start[0]), abs(end[1]-start[1]))*2+1
        previous = start
        for fraction in np.linspace(0, 1, steps):
            current = (round(start[0]+(end[0]-start[0])*fraction),
                       round(start[1]+(end[1]-start[1])*fraction))
            if not self.navigation[current]:
                return False
            if current[0] != previous[0] and current[1] != previous[1]:
                if not self.navigation[previous[0], current[1]] or not self.navigation[current[0], previous[1]]:
                    return False
            previous = current
        return True

    def _line_cost(self, start, end):
        steps = max(abs(end[0]-start[0]), abs(end[1]-start[1]))*2+1
        visited = {start}
        total = 0.0
        for fraction in np.linspace(0, 1, steps):
            node = (round(start[0]+(end[0]-start[0])*fraction),
                    round(start[1]+(end[1]-start[1])*fraction))
            if node not in visited:
                visited.add(node)
                total += self.terrain_cost[node]
        return total

    def route_to(self, position, destination):
        """A* through observed corridors, with short, visible turns as pins."""
        self._refresh_obstacles()
        start = self._snap(position, 32)
        goal = self._snap(destination, 14)
        if start is None or goal is None or self.components[start] != self.components[goal]:
            return None
        queue = [(0, start)]
        costs = {start: 0}
        parents = {}
        while queue:
            _, current = heapq.heappop(queue)
            if current == goal:
                break
            row, col = current
            for dr, dc in ((-1, 0), (1, 0), (0, -1), (0, 1)):
                nxt = row+dr, col+dc
                if not (0 <= nxt[0] < self.navigation.shape[0] and 0 <= nxt[1] < self.navigation.shape[1]):
                    continue
                next_cost = costs[current]+self.terrain_cost[nxt]
                if not self.navigation[nxt] or costs.get(nxt, math.inf) <= next_cost:
                    continue
                costs[nxt] = next_cost
                parents[nxt] = current
                priority = costs[nxt]+abs(goal[0]-nxt[0])+abs(goal[1]-nxt[1])
                heapq.heappush(queue, (priority, nxt))
        if goal != start and goal not in parents:
            return None
        path = [goal]
        while path[-1] != start:
            path.append(parents[path[-1]])
        path.reverse()
        path_cost = [0.0]
        for node in path[1:]:
            path_cost.append(path_cost[-1]+float(self.terrain_cost[node]))
        turns = [path[0]]
        index = 0
        while index < len(path)-1:
            best = index+1
            for candidate in range(index+2, len(path)):
                if (math.dist(path[index], path[candidate]) > 64
                        or not self._line_clear(path[index], path[candidate])):
                    break
                # Keep the terrain preference found by A*. A visible shortcut
                # can still cross a wall/building represented by a high cost.
                original_cost = path_cost[candidate]-path_cost[index]
                if self._line_cost(path[index], path[candidate]) <= original_cost*1.05:
                    best = candidate
            turns.append(path[best])
            index = best
        bx, by = self.data["bounds"][:2]
        waypoints = [[(col*8+4+bx)/16, (row*8+4+by)/16] for row, col in turns]
        if math.dist(waypoints[-1], destination) > 0.15:
            waypoints.append(list(destination))
        else:
            waypoints[-1] = list(destination)
        if len(waypoints) > 1 and math.dist(waypoints[0], position) <= 1.2:
            waypoints = waypoints[1:]
        return waypoints

    def verified_return_path(self, position, min_distance=3.0, max_distance=7.0,
                             max_step=2.0, max_waypoints=4):
        """Reverse the latest continuous trace, preserving observed turns."""
        trace = self.data.get("trace", [])
        segment = []
        for point in reversed(trace):
            if point is None:
                break
            segment.append(list(point))
            if len(segment) >= 256:
                break
        if not segment or math.dist(position, segment[0]) > 0.75:
            return []
        route, previous, travelled, index = [], list(position), 0.0, 0
        while index < len(segment) and len(route) < max_waypoints:
            if math.dist(previous, segment[index]) < 0.3:
                index += 1
                continue
            best = index
            for candidate in range(index+1, len(segment)):
                end = segment[candidate]
                distance = math.dist(previous, end)
                if distance > max_step or distance < 0.3:
                    break
                dx, dy = end[0]-previous[0], end[1]-previous[1]
                projections = [((p[0]-previous[0])*dx+(p[1]-previous[1])*dy)/distance**2
                               for p in segment[index:candidate+1]]
                deviations = [abs((p[0]-previous[0])*dy-(p[1]-previous[1])*dx)/distance
                              for p in segment[index:candidate+1]]
                if (max(deviations) > 0.12 or min(projections) < 0
                        or max(projections) > 1.01
                        or any(b < a-0.01 for a, b in zip(projections, projections[1:]))):
                    break
                best = candidate
            point = segment[best]
            distance = math.dist(previous, point)
            if distance > max_step or travelled+distance > max_distance:
                break
            route.append(point)
            travelled += distance
            previous, index = point, best+1
            if math.dist(position, point) >= min_distance:
                return route
        return []

    def stalled_area(self, position, radius=4.0, limit=2):
        now = time.time()
        done = sum(point["state"] == "done" for point in self.data["targets"])
        self.data["stalled_areas"] = [area for area in self.data.get("stalled_areas", [])
                                      if area["expires"] > now]
        return next((area for area in self.data["stalled_areas"]
                     if area["failures"] >= limit and area["done_count"] >= done
                     and math.dist(position, area["position"]) <= radius), None)

    def record_stall(self, position, destination, radius=4.0, duration=600):
        self.stalled_area(position, radius)
        areas = self.data["stalled_areas"]
        area = next((item for item in areas if math.dist(position, item["position"]) <= radius), None)
        done = sum(point["state"] == "done" for point in self.data["targets"])
        if area is None:
            area = {"position": list(position), "failures": 0, "done_count": done}
            areas.append(area)
        if done > area["done_count"]:
            area["failures"] = 0
            area["position"] = list(position)
        area.update(failures=area["failures"]+1, done_count=done,
                    destination=list(destination), expires=time.time()+duration)
        self.data["stalled_areas"] = areas[-32:]
        self.revision += 1
        return area

    def note_obstacle(self, position, destination, duration=120, reason="verified stall; temporary avoidance",
                      radius=0, barrier=False, heading=None):
        distance = math.dist(position, destination)
        radius = max(0, int(radius))
        if distance < 0.5 and radius == 0 and not barrier:
            return
        bx, by = self.data["bounds"][:2]
        ahead = (list(position) if distance < 0.5 else
                 [position[i]+(destination[i]-position[i])*0.6/distance for i in (0, 1)])
        row, col = int((ahead[1]*16-by)//8), int((ahead[0]*16-bx)//8)
        if 0 <= row < self.navigation.shape[0] and 0 <= col < self.navigation.shape[1]:
            cells = []
            for dy in range(-radius, radius+1):
                for dx in range(-radius, radius+1):
                    if dx*dx+dy*dy > radius**2:
                        continue
                    r, c = row+dy, col+dx
                    if 0 <= r < self.navigation.shape[0] and 0 <= c < self.navigation.shape[1]:
                        cells.append([r, c])

            # Nếu barrier=True: Đốt thành một bức tường chắn (Barrier Slab) vuông góc với vector đâm vào
            # để thuật toán A* không thể lách 1 bước rồi chui vào lại
            if barrier:
                if heading and (heading[0] != 0 or heading[1] != 0):
                    h_len = math.hypot(heading[0], heading[1])
                    hx, hy = heading[0] / h_len, heading[1] / h_len
                elif distance >= 0.1:
                    hx = (destination[0] - position[0]) / distance
                    hy = (destination[1] - position[1]) / distance
                else:
                    hx, hy = 1.0, 0.0
                tx, ty = -hy, hx
                barrier_t_reach = max(2, radius + 2)
                barrier_n_reach = max(2, radius + 1)
                for t_step in range(-barrier_t_reach, barrier_t_reach + 1):
                    for n_step in range(0, barrier_n_reach + 1):
                        wx = ahead[0] + tx * (t_step * 0.5) + hx * (n_step * 0.5)
                        wy = ahead[1] + ty * (t_step * 0.5) + hy * (n_step * 0.5)
                        br = int((wy * 16 - by) // 8)
                        bc = int((wx * 16 - bx) // 8)
                        if 0 <= br < self.navigation.shape[0] and 0 <= bc < self.navigation.shape[1]:
                            cells.append([br, bc])

            expires = time.time()+duration
            obstacles = self.data.setdefault("obstacles", [])
            existing = {tuple(item["cell"]) for item in obstacles if item.get("reason") == reason}
            obstacles.extend({"cell": cell, "expires": expires, "reason": reason}
                             for cell in cells if tuple(cell) not in existing)
            self._refresh_obstacles()

    def observe_position(self, position, tolerance, active_id=None, vision_radius=None, heading=None):
        trace = self.data["trace"]
        if not trace or trace[-1] is None or math.dist(trace[-1], position) >= 0.2:
            # A teleport cannot prove coverage of the straight line between samples.
            if trace and trace[-1] is not None and math.dist(trace[-1], position) > 12:
                trace.append(None)
            if trace and trace[-1] is not None:
                previous = trace[-1]
                previous_node = self._snap(previous, 14)
                current_node = self._snap(position, 14)
                if previous_node is None or current_node is None or not self._line_clear(previous_node, current_node):
                    trace.append(None)
                else:
                    bx, by = self.data["bounds"][:2]
                    start = (round(previous[0] * 16 - bx), round(previous[1] * 16 - by))
                    end = (round(position[0] * 16 - bx), round(position[1] * 16 - by))
                    cv2.line(self.visited, start, end, 1, 7)
            trace.append([round(value, 3) for value in position])
            self.revision += 1
        bx, by = self.data["bounds"][:2]
        cv2.circle(self.visited, (round(position[0]*16-bx), round(position[1]*16-by)), 4, 1, -1)
        effective_radius = max(float(tolerance), float(vision_radius or 0.0))
        # Nón tầm nhìn định hướng phía trước: mở rộng tầm xa lên tới 1.85 lần khi nhìn thẳng hướng chạy
        forward_reach = effective_radius * 1.85 if effective_radius > 0 else 0.0
        h_norm = None
        if heading and (heading[0] != 0 or heading[1] != 0):
            h_len = math.hypot(heading[0], heading[1])
            if h_len > 1e-4:
                h_norm = (heading[0] / h_len, heading[1] / h_len)

        for point in self.data["targets"]:
            if point["state"] == "done":
                continue
            is_seen = False
            for option in point["options"]:
                dx = option[0] - position[0]
                dy = option[1] - position[1]
                dist = math.hypot(dx, dy)
                # Tầm nhìn 360 độ gần (Proximity Sphere):
                if dist <= effective_radius:
                    is_seen = True
                    break
                # Nón tầm nhìn định hướng phía trước (Forward Vision Cone +/- 60 độ):
                if h_norm is not None and dist <= forward_reach:
                    alignment = (dx * h_norm[0] + dy * h_norm[1]) / max(1e-6, dist)
                    if alignment >= 0.45:
                        is_seen = True
                        break
            if is_seen:
                point["state"] = "done"
                self.revision += 1

    def observe_inspection(self, position, radius_override=None, heading=None):
        radius = float(radius_override if radius_override is not None else self.data.get("inspection_radius", 0))
        if radius <= 0 or (radius_override is None and not self.data.get("inspection_calibrated")):
            return
        bx, by = self.data["bounds"][:2]
        footprint = np.zeros(self.known.shape, np.uint8)
        cv2.circle(footprint, (round(position[0]*16-bx), round(position[1]*16-by)), round(radius*16), 1, -1)
        # Quét tầm nhìn nón phía trước dọc theo hướng di chuyển
        if heading and (heading[0] != 0 or heading[1] != 0):
            h_len = math.hypot(heading[0], heading[1])
            if h_len > 1e-4:
                vx = heading[0] / h_len
                vy = heading[1] / h_len
                f_dist = radius * 1.5
                fx = round((position[0] + vx * f_dist * 0.45) * 16 - bx)
                fy = round((position[1] + vy * f_dist * 0.45) * 16 - by)
                axes = (max(1, round(f_dist * 16 * 0.75)), max(1, round(radius * 16 * 0.7)))
                angle_deg = math.degrees(math.atan2(vy, vx))
                cv2.ellipse(footprint, (fx, fy), axes, angle_deg, -60, 60, 1, -1)
        # Restrict the calibrated footprint to direct visible navigation rays.
        node = self._snap(position, 16)
        if node is None or self.components[node] == 0:
            return
        visible_nodes = np.zeros(self.navigation.shape, np.uint8)
        radius_nodes = math.ceil(radius*2.2)
        for row in range(max(0, node[0]-radius_nodes), min(self.navigation.shape[0], node[0]+radius_nodes+1)):
            for col in range(max(0, node[1]-radius_nodes), min(self.navigation.shape[1], node[1]+radius_nodes+1)):
                if math.dist(node, (row, col)) <= radius_nodes and self._line_clear(node, (row, col)):
                    visible_nodes[row, col] = 1
        visible_pixels = cv2.resize(visible_nodes, (self.navigation.shape[1]*8, self.navigation.shape[0]*8), interpolation=cv2.INTER_NEAREST)
        footprint &= visible_pixels[:self.known.shape[0], :self.known.shape[1]]
        self.inspected |= footprint

    def render(self):
        height, width = self.atlas.shape[:2]
        scale = min(1.0, 1600/width, 1200/height)
        image = cv2.resize(self.atlas, (max(1, round(width*scale)), max(1, round(height*scale))), interpolation=cv2.INTER_AREA)
        bx, by = self.data["bounds"][:2]

        def pixel(position):
            return (round((position[0]*16-bx)*scale), round((position[1]*16-by)*scale))

        colors = {"done": (70, 210, 70), "active": (255, 180, 30),
                  "pending": (50, 220, 245), "retry": (20, 140, 255),
                  "unreachable": (70, 70, 245), "deferred": (70, 70, 245)}
        tint = image.copy()
        size = self.data["cell_size"]
        for point in self.data["targets"]:
            x, y = round(point["col"] * size*scale), round(point["row"] * size*scale)
            side = max(1, round(size*scale))
            cv2.rectangle(tint, (x, y), (x+side-1, y+side-1), colors[point["state"]], -1)
        image = cv2.addWeighted(image, 0.76, tint, 0.24, 0)
        # The stored footprint is at map resolution; enlarge only the display mask
        # so short, verified travel segments remain visible in the dashboard preview.
        travelled = cv2.resize(self.visited, (image.shape[1], image.shape[0]), interpolation=cv2.INTER_AREA)
        travelled = cv2.dilate((travelled > 0).astype(np.uint8), np.ones((5, 5), np.uint8)) > 0
        if np.any(travelled):
            green = np.zeros_like(image)
            green[:] = (45, 220, 60)
            image[travelled] = cv2.addWeighted(image[travelled], 0.43, green[travelled], 0.57, 0)
        previous_point = None
        for point in self.data["targets"]:
            if previous_point and previous_point["batch"] == point["batch"]:
                cv2.arrowedLine(image, pixel(previous_point["options"][0]),
                               pixel(point["options"][0]), (200, 140, 60), 1, tipLength=0.12)
            previous_point = point
        previous = None
        active_path = self.data.get("active_path", [])
        for start, end in zip(active_path, active_path[1:]):
            cv2.arrowedLine(image, pixel(start), pixel(end), (255, 130, 20), 3, tipLength=0.18)
        for position in self.data["trace"]:
            if position is None:
                previous = None
                continue
            current = pixel(position)
            if previous is not None:
                cv2.line(image, previous, current, (25, 245, 45), 6)
            cv2.circle(image, current, 5, (25, 245, 45), -1)
            previous = current
        for point in self.data["targets"]:
            x, y = pixel(point.get("destination", point["options"][0]))
            color = colors[point["state"]]
            cv2.circle(image, (x, y), 7 if point["id"] == self.data["active_id"] else 4, color, -1)

        # Vẽ vị trí nhân vật thực tế (chấm đỏ viền trắng nổi bật) kèm nón tầm nhìn tìm đường phía trước
        live_pos = self.data.get("current_player_position")
        if live_pos is not None:
            lx, ly = pixel(live_pos)
            heading = self.data.get("current_heading")
            if heading and (heading[0] != 0 or heading[1] != 0):
                h_len = math.hypot(heading[0], heading[1])
                if h_len > 1e-4:
                    vx, vy = heading[0] / h_len, heading[1] / h_len
                    cone_dist = 40
                    cx_tip = lx + round(vx * cone_dist)
                    cy_tip = ly + round(vy * cone_dist)
                    cos_a, sin_a = 0.819, 0.573
                    lx_l = lx + round((vx * cos_a - vy * sin_a) * cone_dist * 0.85)
                    ly_l = ly + round((vx * sin_a + vy * cos_a) * cone_dist * 0.85)
                    lx_r = lx + round((vx * cos_a + vy * sin_a) * cone_dist * 0.85)
                    ly_r = ly + round((-vx * sin_a + vy * cos_a) * cone_dist * 0.85)

                    cone_poly = np.array([[lx, ly], [lx_l, ly_l], [cx_tip, cy_tip], [lx_r, ly_r]], np.int32)
                    overlay = image.copy()
                    cv2.fillPoly(overlay, [cone_poly], (0, 240, 255))
                    cv2.addWeighted(overlay, 0.32, image, 0.68, 0, image)
                    cv2.polylines(image, [cone_poly], True, (0, 220, 255), 1)

            cv2.circle(image, (lx, ly), 9, (255, 255, 255), -1)
            cv2.circle(image, (lx, ly), 6, (30, 30, 240), -1)

        return cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
