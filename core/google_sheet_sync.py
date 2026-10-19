"""SQLite outbox and a reconciled Apps Script writer; no clipboard success claims."""

import base64
import csv
import json
import hashlib
import os
import random
import threading
import urllib.error
import urllib.parse
import urllib.request

from core.coverage_planner import atomic_json
from core.runtime_store import ROOT, RuntimeStore

HEADERS = ["STT", "TÊN MAP", "TỌA ĐỘ X", "TỌA ĐỘ Y", "ẢNH MINH CHỨNG", "MÔ TẢ / GHI CHÚ", "TRẠNG THÁI"]


class SyncError(Exception):
    def __init__(self, message, permanent=False):
        super().__init__(message)
        self.permanent = permanent


class GoogleSheetSync:
    def __init__(self, json_path=None, csv_path=None, store=None, config=None):
        self.json_path = json_path or os.path.join(ROOT, "reports", "verified_bugs.json")
        self.csv_path = csv_path or os.path.join(ROOT, "reports", "google_sheet_records.csv")
        self.store = store or RuntimeStore()
        if config is None:
            with open(os.path.join(ROOT, "config", "settings.json"), encoding="utf-8") as stream:
                config = json.load(stream).get("sheet_sync", {})
        self.config = config
        self._stop = threading.Event()
        self._wake = threading.Event()
        self._thread = None
        self._export_lock = threading.Lock()
        self._legacy_error = ""
        # Import legacy local records once, without sending them automatically.
        if not self.store.load_checkpoint("legacy_sheet_import"):
            try:
                if os.path.exists(self.json_path):
                    with open(self.json_path, encoding="utf-8") as stream:
                        legacy = json.load(stream)
                    if not isinstance(legacy, list) or not all(isinstance(record, dict) for record in legacy):
                        raise ValueError("Dữ liệu cũ không phải danh sách bản ghi.")
                    for record in legacy:
                        record.setdefault("issue_status", record.get("status", "Chưa fix"))
                        record["status"] = "qa_confirmed"
                        self.store.put_incident(record, enqueue=False)
                self.store.checkpoint("legacy_sheet_import", {"done": True})
            except (ValueError, OSError) as exc:
                self._legacy_error = f"Chưa nhập được JSON cũ; giữ nguyên file nguồn: {exc}"

    @property
    def records(self):
        return self.store.records()

    @property
    def configured(self):
        url = self.config.get("endpoint", "") or os.environ.get("PHONG_THAN_SHEET_ENDPOINT", "")
        return bool(url and os.environ.get(self.config.get("token_env", "PHONG_THAN_SYNC_TOKEN")))

    def summary(self):
        return {**self.store.sync_summary(), "configured": self.configured,
                "worker_error": self._legacy_error or getattr(self, "_last_worker_error", "")}

    def start(self):
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._loop, name="sheet-outbox", daemon=True)
        self._thread.start()

    def close(self, timeout=3):
        self._stop.set()
        self._wake.set()
        if self._thread:
            self._thread.join(timeout)

    def add_observation(self, incident):
        confirmed = (incident.get("status") in {"machine_confirmed", "qa_confirmed"}
                     and incident.get("evidence_state") == "ready")
        record = self.store.put_incident(incident, enqueue=confirmed, observation=True)
        if confirmed:
            self._wake.set()
        return record

    def add_confirmed_bug(self, bug_info, custom_note=None):
        record = dict(bug_info)
        record["status"] = "qa_confirmed"
        if custom_note:
            record["description"] = custom_note
        record = self.store.put_incident(record, enqueue=True)
        self._wake.set()
        return record

    def reject(self, incident):
        record = dict(incident)
        record["status"] = "rejected"
        # If already sent, queue an explicit correction of that same ID.
        return self.store.put_incident(record, enqueue=False)

    def _request(self, action, **payload):
        endpoint = self.config.get("endpoint", "") or os.environ.get("PHONG_THAN_SHEET_ENDPOINT", "")
        parsed = urllib.parse.urlparse(endpoint)
        if parsed.scheme != "https" or parsed.hostname != "script.google.com" or not parsed.path.endswith("/exec"):
            raise SyncError("Cần URL triển khai Apps Script dạng https://script.google.com/macros/s/.../exec.", True)
        secret = os.environ.get(self.config.get("token_env", "PHONG_THAN_SYNC_TOKEN"))
        if not secret:
            raise SyncError("Chưa cấu hình token đồng bộ trong biến môi trường.", True)
        body = json.dumps({"action": action, "token": secret, **payload}).encode("utf-8")
        request = urllib.request.Request(endpoint, data=body, headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                raw = response.read(2_000_000)
            result = json.loads(raw)
        except urllib.error.HTTPError as exc:
            raise SyncError(f"Dịch vụ trả HTTP {exc.code}.", exc.code in {400, 401, 403, 404}) from None
        except (ValueError, urllib.error.URLError, TimeoutError, OSError):
            raise SyncError("Chưa nhận được phản hồi JSON hợp lệ; sẽ đối soát ID trước khi thử lại.") from None
        if not isinstance(result, dict) or not result.get("ok"):
            raise SyncError(str(result.get("error", "Phản hồi dịch vụ không hợp lệ")) if isinstance(result, dict)
                            else "Phản hồi dịch vụ không hợp lệ", bool(result.get("permanent")) if isinstance(result, dict) else False)
        expected = self.config.get("spreadsheet_id")
        if expected and result.get("spreadsheet_id") != expected:
            raise SyncError("Dịch vụ đang trỏ tới Sheet khác cấu hình.", True)
        if str(result.get("gid")) != str(self.config.get("gid", 0)):
            raise SyncError("Dịch vụ đang trỏ tới tab khác cấu hình.", True)
        return result

    def _evidence(self, incident):
        filename = incident.get("annotated_image") or incident.get("evidence_image")
        if not filename:
            raise SyncError("Sự kiện thiếu ảnh minh chứng.", True)
        directory = os.path.realpath(os.path.join(ROOT, "reports", "evidence"))
        path = os.path.realpath(os.path.join(directory, filename))
        if os.path.commonpath([directory, path]) != directory or not os.path.isfile(path):
            raise SyncError("Không tìm thấy ảnh trong thư mục bằng chứng.", True)
        if os.path.getsize(path) > 5_000_000:
            raise SyncError("Ảnh vượt giới hạn 5 MB của gói đồng bộ; cần xuất ảnh nhỏ hơn.", True)
        with open(path, "rb") as stream:
            raw = stream.read()
        content = base64.b64encode(raw).decode("ascii")
        evidence_hash = hashlib.sha256(raw).hexdigest()
        result = self._request("evidence", incident_id=incident["id"], evidence_hash=evidence_hash, content=content)
        if result.get("evidence_hash") != evidence_hash:
            raise SyncError("Dịch vụ trả ảnh khác dấu băm đã gửi.")
        url = result.get("url", "")
        if not url.startswith("https://drive.google.com/"):
            raise SyncError("Dịch vụ chưa trả liên kết Drive hợp lệ.")
        return url

    def sync_one(self):
        item = self.store.claim()
        if item is None:
            return False
        try:
            incident = json.loads(item["payload"])
            existing = self._request("lookup", incident_id=incident["id"])
            if int(existing.get("revision", 0)) > item["revision"]:
                raise SyncError("Sheet có phiên bản sự kiện mới hơn dữ liệu máy này; cần đối soát.", True)
            url = (existing.get("evidence_url") if incident.get("status") == "rejected" else None) or self._evidence(incident)
            fields = [str(incident.get("stt", "")), str(incident.get("map_name", "")),
                      str(incident.get("coord_x", "")), str(incident.get("coord_y", "")), url,
                      str(incident.get("description", "")), self._business_status(incident)]
            previous_fields = existing.get("fields", [])
            if len(previous_fields) == 7 and incident.get("status") != "rejected" and previous_fields[6] != "Không phải lỗi":
                fields[6] = previous_fields[6]  # Preserve the team's existing fix workflow.
            self._request("upsert", incident_id=incident["id"], revision=item["revision"], fields=fields,
                          timestamp=incident.get("timestamp", ""), confidence=incident.get("status", "")+":"+str(incident.get("confidence", "")))
            checked = self._request("lookup", incident_id=incident["id"])
            # STT is allocated by the central writer; all business fields must match.
            if (not checked.get("found") or int(checked.get("revision", 0)) != item["revision"]
                    or checked.get("fields", [])[1:] != fields[1:]):
                raise SyncError("Dòng đọc lại chưa khớp sự kiện; chưa xác nhận đồng bộ.")
            self.store.finish_sync(item, "synced", remote_row=str(checked["row"]))
        except SyncError as exc:
            delay = min(900, 2**min(item["attempts"]+1, 9)) + random.uniform(0, 2)
            self.store.finish_sync(item, "blocked" if exc.permanent else "retry", str(exc), delay=delay)
        except Exception as exc:
            self.store.finish_sync(item, "blocked", f"Lỗi xử lý công việc đồng bộ: {exc}")
        return True

    def retry_blocked(self):
        with self.store.connection() as db:
            db.execute("UPDATE outbox SET state='queued',next_try=0,error='' WHERE state='blocked'")
        self._wake.set()

    def _loop(self):
        while not self._stop.is_set():
            try:
                if self.configured and self.sync_one():
                    continue
                self.export()
                self._last_worker_error = ""
            except Exception as exc:
                # A failed local write remains visible; it is never converted to success.
                self._last_worker_error = str(exc)
            self._wake.wait(3)
            self._wake.clear()

    def export(self):
        if self._legacy_error:
            raise OSError(self._legacy_error)
        records = self.records
        with self._export_lock:
            signature = [(record["id"], record.get("revision"), record.get("sync_state"), record.get("remote_row")) for record in records]
            if signature == getattr(self, "_export_signature", None):
                return
            atomic_json(self.json_path, records)
            os.makedirs(os.path.dirname(os.path.abspath(self.csv_path)), exist_ok=True)
            temporary = self.csv_path + ".next"
            with open(temporary, "w", encoding="utf-8-sig", newline="") as stream:
                writer = csv.writer(stream)
                writer.writerow(HEADERS)
                writer.writerows(self._columns(record) for record in records)
            os.replace(temporary, self.csv_path)
            self._export_signature = signature

    @staticmethod
    def _business_status(record):
        return "Không phải lỗi" if record.get("status") == "rejected" else str(record.get("issue_status", "Chưa fix"))

    @staticmethod
    def _columns(record):
        return [record.get("stt", ""), record.get("map_name", ""), record.get("coord_x", ""),
                record.get("coord_y", ""), record.get("annotated_image", ""), record.get("description", ""),
                GoogleSheetSync._business_status(record)]

    def copy_latest_to_clipboard(self):
        return self._copy(self.records[-1:])

    def copy_all_to_clipboard(self):
        return self._copy(self.records)

    def _copy(self, records):
        if not records:
            return False, "Chưa có lỗi đã xác nhận."
        import pyperclip
        pyperclip.copy("\n".join("\t".join(str(value).replace("\t", " ").replace("\n", " ")
                                        for value in self._columns(record)) for record in records))
        return True, f"Đã copy {len(records)} dòng; thao tác này chưa ghi lên Sheet."
