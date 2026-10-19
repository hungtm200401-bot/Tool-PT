"""A static export of the same SQLite records used by the application."""

import html
import os
from urllib.parse import quote

from core.runtime_store import ROOT, RuntimeStore, utc_now


class HTMLReporter:
    def __init__(self, incidents_json=None, output_html=None, store=None):
        self.store = store or RuntimeStore()
        self.output_html = output_html or os.path.join(ROOT, "reports", "dashboard.html")

    def generate(self):
        escape = lambda value: html.escape(str(value), quote=True)
        incidents = self.store.records(include_suspects=True)
        maps = self.store.checkpoints()
        summary = self.store.sync_summary()
        cards = []
        for incident in reversed(incidents):
            filename = os.path.basename(incident.get("annotated_image", ""))
            image = "evidence/"+quote(filename)
            clip_name = os.path.basename(incident.get("clip_gif", ""))
            clip_url = ("evidence/"+quote(clip_name)) if clip_name else image
            sev = incident.get("severity", "MAJOR")
            sev_vi = incident.get("severity_vi", "TRUNG BÌNH")
            badge_bg = "#f85149" if sev == "CRITICAL" else "#d29922" if sev == "MAJOR" else "#58a6ff"
            cards.append(f"""<article>
                <h3><span style="background:{badge_bg};color:#ffffff;padding:2px 8px;border-radius:4px;font-size:12px;margin-right:6px;">{escape(sev_vi)}</span>{escape(incident.get('map_name', ''))} · {escape(incident.get('glitch_type', ''))}</h3>
                <p>Vị trí nhân vật: {escape(incident.get('coord_x', ''))}, {escape(incident.get('coord_y', ''))}</p>
                <p>{escape(incident.get('description', ''))}</p>
                <p>Phân loại: {escape(incident.get('status', ''))} · Bằng chứng: {escape(incident.get('evidence_state', 'legacy'))}</p>
                <p>Sheet: {escape(incident.get('sync_state', 'review'))} · Dòng: {escape(incident.get('remote_row', ''))}</p>
                <p>{escape(incident.get('sync_error', ''))}</p>
                <a href="{clip_url}" target="_blank" title="Xem clip động hoặc phóng to"><img loading="lazy" src="{clip_url}" alt="Clip bằng chứng động"></a>
                <small>ID: {escape(incident['id'])} · {escape(incident.get('timestamp', ''))} · <a href="{image}" target="_blank" style="color:#58a6ff;">[Xem ảnh tĩnh HD]</a></small>
            </article>""")
        rows = []
        for key, item in sorted(maps.items()):
            inspected = f"{item.get('inspected_fraction', 0)*100:.1f}%" if item.get("inspection_calibrated") else "Chưa hiệu chỉnh"
            rows.append(f"<tr><td>{escape(key)}</td><td>{escape(item.get('name', ''))}</td>"
                        f"<td>{escape(item.get('phase', ''))}</td><td>{item.get('done', 0)}/{item.get('total', 0)}</td>"
                        f"<td>{inspected}</td><td>{item.get('unknown_pixels', 0)}</td></tr>")
        missions = self.store.checkpoints("mission:")
        inventory = []
        for scope, mission in missions.items():
            for map_id, item in mission.get("map_results", {}).items():
                inventory.append(f"<tr><td>{escape(scope)}</td><td>{escape(map_id)}</td><td>{escape(item.get('name', ''))}</td>"
                                 f"<td>{escape(item.get('state', ''))}</td><td>{escape(item.get('reason', ''))}</td></tr>")
        metric_rows = []
        for mission_id, snapshot in sorted(self.store.checkpoints("metrics:").items()):
            for operation, values in sorted(snapshot.items()):
                metric_rows.append(
                    f"<tr><td>{escape(mission_id)}</td><td>{escape(operation)}</td>"
                    f"<td>{values.get('count', 0)}</td><td>{values.get('p50_ms', 0):.2f} ms</td>"
                    f"<td>{values.get('p95_ms', 0):.2f} ms</td></tr>"
                )
        content = f"""<!doctype html><html lang="vi"><head><meta charset="utf-8">
            <meta name="viewport" content="width=device-width,initial-scale=1">
            <title>Báo cáo khảo sát Phong Thần</title><style>
            body{{background:#0d1117;color:#c9d1d9;font:15px system-ui;margin:24px}}
            h1,h2{{color:#58a6ff}}table{{border-collapse:collapse;width:100%;margin-bottom:24px}}
            td,th{{border:1px solid #30363d;padding:8px;text-align:left}}
            .cards{{display:grid;grid-template-columns:repeat(auto-fit,minmax(320px,1fr));gap:16px}}
            article{{background:#161b22;padding:16px;border:1px solid #30363d;border-radius:8px;overflow-wrap:anywhere}}
            img{{width:100%}}small{{color:#8b949e}}</style></head><body>
            <h1>Báo cáo khảo sát Phong Thần</h1><p>Xuất lúc {escape(utc_now())}. Nguồn: SQLite cục bộ.</p>
            <p>{len(incidents)} sự kiện, gồm cả cảnh nghi ngờ. Sheet đã đối soát: {summary.get('synced', 0)};
            cần xử lý: {summary.get('blocked', 0)}. Tỷ lệ bên dưới chỉ áp dụng cho nền địa hình đã biết.</p>
            <h2>Tiến độ theo hồ sơ và map</h2><table><tr><th>Hồ sơ/map</th><th>Tên</th><th>Trạng thái</th>
            <th>Mốc đã tới</th><th>Kiểm tra hình</th><th>Pixel chưa biết</th></tr>{''.join(rows)}</table>
            <h2>Danh mục nhiệm vụ</h2><table><tr><th>Hồ sơ</th><th>Map ID</th><th>Tên</th><th>Kết quả</th><th>Phần còn thiếu</th></tr>
            {''.join(inventory)}</table><h2>Hiệu năng vận hành</h2>
            <table><tr><th>Phiên</th><th>Thao tác</th><th>Số lần</th><th>P50</th><th>P95</th></tr>
            {''.join(metric_rows) or '<tr><td colspan="5">Chưa có số đo hiệu năng.</td></tr>'}</table>
            <h2>Sự kiện và bằng chứng</h2>
            <div class="cards">{''.join(cards) or '<p>Chưa có sự kiện được lưu.</p>'}</div></body></html>"""
        os.makedirs(os.path.dirname(os.path.abspath(self.output_html)), exist_ok=True)
        temporary = self.output_html+".next"
        with open(temporary, "w", encoding="utf-8") as stream:
            stream.write(content)
        os.replace(temporary, self.output_html)
        return self.output_html
