"""Durable local state. Network and GUI code never own the source of truth."""

import contextlib
import datetime
import json
import os
import sqlite3
import threading
import time
import uuid

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def utc_now():
    return datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")


class RuntimeStore:
    def __init__(self, path=None):
        self.path = path or os.path.join(ROOT, "reports", "runtime.sqlite3")
        os.makedirs(os.path.dirname(os.path.abspath(self.path)), exist_ok=True)
        self._lock = threading.RLock()
        with self.connection() as db:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS checkpoints (
                    scope TEXT PRIMARY KEY, payload TEXT NOT NULL, updated TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS incidents (
                    id TEXT PRIMARY KEY, bug_key TEXT, payload TEXT NOT NULL,
                    revision INTEGER NOT NULL DEFAULT 1, created TEXT NOT NULL);
                CREATE INDEX IF NOT EXISTS incident_key ON incidents(bug_key);
                CREATE TABLE IF NOT EXISTS outbox (
                    id TEXT PRIMARY KEY REFERENCES incidents(id), state TEXT NOT NULL,
                    attempts INTEGER NOT NULL DEFAULT 0, next_try REAL NOT NULL DEFAULT 0,
                    error TEXT NOT NULL DEFAULT '', remote_row TEXT NOT NULL DEFAULT '',
                    revision INTEGER NOT NULL DEFAULT 1);
                CREATE TABLE IF NOT EXISTS events (
                    sequence INTEGER PRIMARY KEY AUTOINCREMENT, created TEXT NOT NULL,
                    mission TEXT, kind TEXT NOT NULL, payload TEXT NOT NULL);
            """)
            # A process may have ended during an upload. Always reconcile again.
            db.execute("UPDATE outbox SET state='queued' WHERE state='syncing'")

    @contextlib.contextmanager
    def connection(self):
        with self._lock:
            db = sqlite3.connect(self.path, timeout=10)
            db.row_factory = sqlite3.Row
            db.execute("PRAGMA foreign_keys=ON")
            db.execute("PRAGMA journal_mode=WAL")
            db.execute("PRAGMA synchronous=FULL")
            try:
                with db:
                    yield db
            finally:
                db.close()

    def checkpoint(self, scope, payload):
        with self.connection() as db:
            db.execute("INSERT OR REPLACE INTO checkpoints VALUES (?, ?, ?)",
                       (scope, json.dumps(payload, ensure_ascii=False), utc_now()))

    def load_checkpoint(self, scope):
        with self.connection() as db:
            row = db.execute("SELECT payload FROM checkpoints WHERE scope=?", (scope,)).fetchone()
        return json.loads(row[0]) if row else None

    def checkpoints(self, prefix="map:"):
        with self.connection() as db:
            rows = db.execute("SELECT scope,payload FROM checkpoints WHERE scope LIKE ?",
                              (prefix + "%",)).fetchall()
        return {row[0]: json.loads(row[1]) for row in rows}

    def event(self, mission, kind, payload):
        with self.connection() as db:
            db.execute("INSERT INTO events(created,mission,kind,payload) VALUES(?,?,?,?)",
                       (utc_now(), mission, kind, json.dumps(payload, ensure_ascii=False)))

    def put_incident(self, incident, enqueue=False, observation=False):
        incoming = dict(incident)
        if not incoming.get("id"):
            incoming["id"] = uuid.uuid4().hex
        incoming.setdefault("timestamp", utc_now())
        with self.connection() as db:
            existing = db.execute("SELECT * FROM incidents WHERE id=?", (incoming["id"],)).fetchone()
            # Group repeated observations of one defect, including across restarts.
            if existing is None and incoming.get("bug_key"):
                existing = db.execute("SELECT * FROM incidents WHERE bug_key=? ORDER BY created LIMIT 1",
                                      (incoming["bug_key"],)).fetchone()
            revision = 1
            if existing:
                old = json.loads(existing["payload"])
                incoming["id"] = existing["id"]
                revision = existing["revision"] + 1
                if old.get("status") == "rejected" and incoming.get("status") != "qa_confirmed":
                    return old
                if observation and incoming.get("observation_id") != old.get("observation_id"):
                    incoming["occurrences"] = old.get("occurrences", 1) + 1
                else:
                    incoming["occurrences"] = old.get("occurrences", 1)
                incoming.setdefault("first_seen", old.get("first_seen", old.get("timestamp")))
                incoming.setdefault("issue_status", old.get("issue_status", "Chưa fix"))
                if old.get("status") == "qa_confirmed" and incoming.get("status") != "rejected":
                    incoming["status"] = "qa_confirmed"
                incoming.setdefault("stt", old.get("stt"))
            incoming.setdefault("occurrences", 1)
            if not incoming.get("stt"):
                incoming["stt"] = db.execute("SELECT COALESCE(MAX(json_extract(payload,'$.stt')),0)+1 FROM incidents").fetchone()[0]
            incoming["revision"] = revision
            db.execute("INSERT INTO incidents VALUES(?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET "
                       "payload=excluded.payload, revision=excluded.revision",
                       (incoming["id"], incoming.get("bug_key"), json.dumps(incoming, ensure_ascii=False),
                        revision, incoming["timestamp"]))
            pending = db.execute("SELECT 1 FROM outbox WHERE id=?", (incoming["id"],)).fetchone()
            if enqueue or pending:
                db.execute("INSERT INTO outbox(id,state,revision) VALUES(?,'queued',?) "
                           "ON CONFLICT(id) DO UPDATE SET state='queued',revision=excluded.revision,"
                           "next_try=0,error=''", (incoming["id"], revision))
        return incoming

    def records(self, include_suspects=False):
        with self.connection() as db:
            rows = db.execute("SELECT i.payload,o.state,o.error,o.remote_row FROM incidents i "
                              "LEFT JOIN outbox o ON i.id=o.id ORDER BY i.created,i.id").fetchall()
        results = []
        for row in rows:
            item = json.loads(row[0])
            if not include_suspects and item.get("status") not in {"qa_confirmed", "machine_confirmed"}:
                continue
            item.update(sync_state=row[1] or "review", sync_error=row[2] or "", remote_row=row[3] or "")
            results.append(item)
        return results

    def claim(self):
        with self.connection() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT o.*,i.payload FROM outbox o JOIN incidents i ON i.id=o.id "
                             "WHERE o.state IN ('queued','retry') AND o.next_try<=? ORDER BY o.next_try LIMIT 1",
                             (time.time(),)).fetchone()
            if row:
                db.execute("UPDATE outbox SET state='syncing' WHERE id=?", (row["id"],))
                return dict(row)
        return None

    def finish_sync(self, item, state, error="", remote_row="", delay=0):
        with self.connection() as db:
            db.execute("UPDATE outbox SET state=?,attempts=attempts+1,error=?,remote_row=?,next_try=? "
                       "WHERE id=? AND revision=?",
                       (state, error[:1000], remote_row, time.time()+delay, item["id"], item["revision"]))

    def sync_summary(self):
        with self.connection() as db:
            rows = db.execute("SELECT state,COUNT(*) FROM outbox GROUP BY state").fetchall()
            error = db.execute("SELECT error FROM outbox WHERE error<>'' ORDER BY next_try DESC LIMIT 1").fetchone()
        return {**{row[0]: row[1] for row in rows}, "last_error": error[0] if error else ""}
