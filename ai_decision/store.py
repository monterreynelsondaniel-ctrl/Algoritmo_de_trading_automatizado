"""SQLite cache plus append-only audit trail for reproducible decisions."""

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path


class PendingAIRequestError(RuntimeError):
    pass


class DecisionStore:
    def __init__(self, path="ai_decisions.db"):
        self.path = str(path)
        self._memory_connection = sqlite3.connect(":memory:") if self.path == ":memory:" else None
        if self.path != ":memory:":
            Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def _connect(self):
        return self._memory_connection or sqlite3.connect(self.path)

    def _initialize(self):
        with self._connect() as connection:
            connection.executescript("""
                CREATE TABLE IF NOT EXISTS ai_decision_cache (
                    cache_key TEXT PRIMARY KEY, decision_type TEXT NOT NULL,
                    request_json TEXT NOT NULL, response_json TEXT NOT NULL,
                    metadata_json TEXT NOT NULL, created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS ai_decision_audit (
                    id INTEGER PRIMARY KEY AUTOINCREMENT, cache_key TEXT NOT NULL,
                    source TEXT NOT NULL, status TEXT NOT NULL,
                    detail_json TEXT NOT NULL, created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS ai_pending_requests (
                    cache_key TEXT PRIMARY KEY, run_id TEXT, decision_type TEXT NOT NULL,
                    status TEXT NOT NULL, attempt INTEGER NOT NULL,
                    detail_json TEXT NOT NULL, updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS ai_runs (
                    run_id TEXT PRIMARY KEY, identity_json TEXT NOT NULL,
                    identity_hash TEXT NOT NULL, status TEXT NOT NULL,
                    created_at TEXT NOT NULL, started_at TEXT, completed_at TEXT,
                    last_processed_event TEXT, live_calls INTEGER NOT NULL DEFAULT 0,
                    cache_hits INTEGER NOT NULL DEFAULT 0,
                    input_tokens INTEGER NOT NULL DEFAULT 0,
                    output_tokens INTEGER NOT NULL DEFAULT 0,
                    estimated_cost_usd REAL NOT NULL DEFAULT 0,
                    actual_cost_usd REAL NOT NULL DEFAULT 0,
                    detail_json TEXT NOT NULL DEFAULT '{}'
                );
            """)
            columns = {row[1] for row in connection.execute("PRAGMA table_info(ai_runs)")}
            if "actual_cost_usd" not in columns:
                connection.execute(
                    "ALTER TABLE ai_runs ADD COLUMN actual_cost_usd REAL NOT NULL DEFAULT 0"
                )

    def get(self, cache_key):
        with self._connect() as connection:
            row = connection.execute(
                "SELECT response_json, metadata_json FROM ai_decision_cache WHERE cache_key=?",
                (cache_key,),
            ).fetchone()
        return None if row is None else (json.loads(row[0]), json.loads(row[1]))

    def put(self, cache_key, decision_type, request, response, metadata):
        now = datetime.now(timezone.utc).isoformat()
        with self._connect() as connection:
            connection.execute(
                "INSERT OR IGNORE INTO ai_decision_cache VALUES (?, ?, ?, ?, ?, ?)",
                (cache_key, decision_type, json.dumps(request, sort_keys=True),
                 json.dumps(response, sort_keys=True), json.dumps(metadata, sort_keys=True), now),
            )

    def audit(self, cache_key, source, status, detail):
        with self._connect() as connection:
            connection.execute(
                "INSERT INTO ai_decision_audit(cache_key,source,status,detail_json,created_at) VALUES(?,?,?,?,?)",
                (cache_key, source, status, json.dumps(detail, sort_keys=True),
                datetime.now(timezone.utc).isoformat()),
            )

    def count(self):
        with self._connect() as connection:
            return connection.execute("SELECT COUNT(*) FROM ai_decision_cache").fetchone()[0]

    def mark_pending(self, cache_key, run_id, decision_type, attempt, detail=None):
        now = datetime.now(timezone.utc).isoformat()
        with self._connect() as connection:
            existing = connection.execute(
                "SELECT status FROM ai_pending_requests WHERE cache_key=?", (cache_key,)
            ).fetchone()
            if existing and existing[0] in {"PENDING", "UNKNOWN"}:
                raise PendingAIRequestError(
                    f"Unresolved AI request exists for cache key {cache_key}"
                )
            connection.execute("""
                INSERT INTO ai_pending_requests VALUES (?, ?, ?, 'PENDING', ?, ?, ?)
                ON CONFLICT(cache_key) DO UPDATE SET run_id=excluded.run_id,
                    decision_type=excluded.decision_type, status='PENDING',
                    attempt=excluded.attempt, detail_json=excluded.detail_json,
                    updated_at=excluded.updated_at
            """, (cache_key, run_id, decision_type, attempt,
                  json.dumps(detail or {}, sort_keys=True), now))

    def mark_pending_failed(self, cache_key, detail=None):
        with self._connect() as connection:
            connection.execute(
                "UPDATE ai_pending_requests SET status='FAILED', detail_json=?, updated_at=? WHERE cache_key=?",
                (json.dumps(detail or {}, sort_keys=True), datetime.now(timezone.utc).isoformat(), cache_key),
            )

    def mark_pending_unknown(self, cache_key, detail=None):
        with self._connect() as connection:
            connection.execute(
                "UPDATE ai_pending_requests SET status='UNKNOWN', detail_json=?, updated_at=? WHERE cache_key=?",
                (json.dumps(detail or {}, sort_keys=True), datetime.now(timezone.utc).isoformat(), cache_key),
            )

    def persist_decision(self, cache_key, decision_type, request, response, metadata, source="live"):
        """Atomically cache the response, close pending state, and append audit."""
        now = datetime.now(timezone.utc).isoformat()
        with self._connect() as connection:
            connection.execute(
                "INSERT OR IGNORE INTO ai_decision_cache VALUES (?, ?, ?, ?, ?, ?)",
                (cache_key, decision_type, json.dumps(request, sort_keys=True),
                 json.dumps(response, sort_keys=True), json.dumps(metadata, sort_keys=True), now),
            )
            connection.execute(
                "UPDATE ai_pending_requests SET status='COMPLETED', detail_json=?, updated_at=? WHERE cache_key=?",
                (json.dumps(metadata, sort_keys=True), now, cache_key),
            )
            connection.execute(
                "INSERT INTO ai_decision_audit(cache_key,source,status,detail_json,created_at) VALUES(?,?,?,?,?)",
                (cache_key, source, "OK", json.dumps({**metadata, "cache_hit": False}, sort_keys=True), now),
            )

    def create_run(self, run_id, identity_json, identity_hash):
        now = datetime.now(timezone.utc).isoformat()
        with self._connect() as connection:
            connection.execute(
                "INSERT INTO ai_runs(run_id,identity_json,identity_hash,status,created_at,detail_json) "
                "VALUES(?,?,?,'CREATED',?,'{}')",
                (run_id, identity_json, identity_hash, now),
            )

    def get_run(self, run_id):
        with self._connect() as connection:
            connection.row_factory = sqlite3.Row
            row = connection.execute("SELECT * FROM ai_runs WHERE run_id=?", (run_id,)).fetchone()
        return None if row is None else dict(row)

    def update_run(self, run_id, *, status=None, last_event=None, detail=None,
                   live_calls=0, cache_hits=0, input_tokens=0, output_tokens=0,
                   estimated_cost_usd=0.0, actual_cost_usd=0.0):
        now = datetime.now(timezone.utc).isoformat()
        assignments = [
            "live_calls=live_calls+?", "cache_hits=cache_hits+?",
            "input_tokens=input_tokens+?", "output_tokens=output_tokens+?",
            "estimated_cost_usd=estimated_cost_usd+?",
            "actual_cost_usd=actual_cost_usd+?",
        ]
        values = [live_calls, cache_hits, input_tokens, output_tokens,
                  estimated_cost_usd, actual_cost_usd]
        if status is not None:
            assignments.append("status=?")
            values.append(status)
            if status == "RUNNING":
                assignments.append("started_at=COALESCE(started_at, ?)")
                values.append(now)
            if status == "COMPLETED":
                assignments.append("completed_at=?")
                values.append(now)
        if last_event is not None:
            assignments.append("last_processed_event=?")
            values.append(last_event)
        if detail is not None:
            assignments.append("detail_json=?")
            values.append(json.dumps(detail, sort_keys=True))
        values.append(run_id)
        with self._connect() as connection:
            connection.execute(f"UPDATE ai_runs SET {', '.join(assignments)} WHERE run_id=?", values)
