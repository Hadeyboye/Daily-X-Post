"""
memory/history.py

SQLite-backed structured memory and audit log.

Stores:
- Every published post + metadata
- Performance metrics over time
- Scheduler jobs
- Human feedback
- Full run history (for self-improvement)
- RL signals

Upgradable to Postgres with zero code changes (swap engine).
"""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import structlog

logger = structlog.get_logger(__name__)


class SQLiteHistory:
    def __init__(self, db_path: str):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.conn: Optional[sqlite3.Connection] = None

    def _connect(self) -> sqlite3.Connection:
        if self.conn is None:
            self.conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
            self.conn.row_factory = sqlite3.Row
        return self.conn

    def initialize_schema(self) -> None:
        conn = self._connect()
        c = conn.cursor()

        c.execute("""
            CREATE TABLE IF NOT EXISTS posts (
                id TEXT PRIMARY KEY,
                url TEXT,
                platform TEXT DEFAULT 'x',
                draft_id TEXT,
                text TEXT,
                format TEXT,
                posted_at TEXT,
                predicted_virality REAL,
                image_paths TEXT,
                raw_json TEXT
            )
        """)

        c.execute("""
            CREATE TABLE IF NOT EXISTS metrics (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                post_id TEXT,
                impressions INTEGER,
                engagements INTEGER,
                likes INTEGER,
                reposts INTEGER,
                replies INTEGER,
                saves INTEGER,
                profile_visits INTEGER,
                link_clicks INTEGER,
                engagement_rate REAL,
                collected_at TEXT,
                FOREIGN KEY(post_id) REFERENCES posts(id)
            )
        """)

        c.execute("""
            CREATE TABLE IF NOT EXISTS runs (
                run_id TEXT PRIMARY KEY,
                trigger TEXT,
                started_at TEXT,
                completed_at TEXT,
                posts_generated INTEGER,
                posts_published INTEGER,
                avg_predicted_score REAL,
                audit_trail TEXT,
                final_state TEXT
            )
        """)

        c.execute("""
            CREATE TABLE IF NOT EXISTS human_feedback (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                draft_id TEXT,
                action TEXT,
                score REAL,
                notes TEXT,
                created_at TEXT
            )
        """)

        c.execute("""
            CREATE TABLE IF NOT EXISTS events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                event_type TEXT,
                payload TEXT,
                created_at TEXT
            )
        """)

        conn.commit()
        logger.info("sqlite_schema_initialized", db=str(self.db_path))

    def log_post(self, post: Dict[str, Any]) -> None:
        conn = self._connect()
        c = conn.cursor()
        c.execute(
            """INSERT OR REPLACE INTO posts
               (id, url, platform, draft_id, text, format, posted_at, predicted_virality, image_paths, raw_json)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                post.get("id"),
                post.get("url"),
                post.get("platform", "x"),
                post.get("draft_id"),
                post.get("text", "")[:2000],
                post.get("format"),
                post.get("posted_at") or datetime.utcnow().isoformat(),
                post.get("predicted_virality"),
                json.dumps(post.get("image_paths", [])),
                json.dumps(post),
            ),
        )
        conn.commit()

    def log_metrics(self, metrics: List[Any]) -> None:
        conn = self._connect()
        c = conn.cursor()
        for m in metrics:
            if hasattr(m, "model_dump"):
                m = m.model_dump()
            c.execute(
                """INSERT INTO metrics
                   (post_id, impressions, engagements, likes, reposts, replies, saves, engagement_rate, collected_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    m.get("post_id"),
                    m.get("impressions", 0),
                    m.get("engagements", 0),
                    m.get("likes", 0),
                    m.get("reposts", 0),
                    m.get("replies", 0),
                    m.get("saves", 0),
                    m.get("engagement_rate", 0.0),
                    m.get("collected_at") or datetime.utcnow().isoformat(),
                ),
            )
        conn.commit()

    def log_event(self, event_type: str, payload: Dict[str, Any]) -> None:
        conn = self._connect()
        c = conn.cursor()
        c.execute(
            "INSERT INTO events (event_type, payload, created_at) VALUES (?, ?, ?)",
            (event_type, json.dumps(payload), datetime.utcnow().isoformat()),
        )
        conn.commit()

    def get_recent_high_performers(self, limit: int = 8) -> List[Dict[str, Any]]:
        conn = self._connect()
        c = conn.cursor()
        rows = c.execute(
            "SELECT * FROM posts ORDER BY posted_at DESC LIMIT ?",
            (limit,),
        ).fetchall()
        return [dict(r) for r in rows]

    def get_engagement_history(self, limit: int = 20) -> List[float]:
        conn = self._connect()
        c = conn.cursor()
        rows = c.execute(
            "SELECT engagement_rate FROM metrics ORDER BY collected_at DESC LIMIT ?",
            (limit,),
        ).fetchall()
        return [r[0] or 0.0 for r in rows]

    def get_metrics_since(self, since_iso: str) -> List[Dict[str, Any]]:
        conn = self._connect()
        c = conn.cursor()
        rows = c.execute(
            "SELECT * FROM metrics WHERE collected_at >= ? ORDER BY collected_at",
            (since_iso,),
        ).fetchall()
        return [dict(r) for r in rows]

    def log_human_feedback(self, draft_id: str, action: str, score: float, notes: str = "") -> None:
        conn = self._connect()
        c = conn.cursor()
        c.execute(
            "INSERT INTO human_feedback (draft_id, action, score, notes, created_at) VALUES (?, ?, ?, ?, ?)",
            (draft_id, action, score, notes, datetime.utcnow().isoformat()),
        )
        conn.commit()

    def close(self):
        if self.conn:
            self.conn.close()
            self.conn = None
