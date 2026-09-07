"""SQLite cache plus append-only audit trail for reproducible decisions."""

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path


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
            """)

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
