"""Episodic memory — the durable event log (Blueprint §6).

Episodic memory records *what happened*: a chronological log of events, each tagged with
the originating agent, an event ``kind``, an optional ``trace_id`` linking it to a unit of
work, and an arbitrary JSON payload. It is the long-term, queryable record an agent can
replay to reconstruct how a situation unfolded.

Storage is stdlib ``sqlite3`` only — pass a filesystem path for durability (the schema is
created on first open and survives process restarts) or ``":memory:"`` for an ephemeral,
test-only log. Timestamps are stored as ISO-8601 UTC strings, so lexical ordering equals
chronological ordering.
"""

from __future__ import annotations

import json
import sqlite3
import threading
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

_SCHEMA = """
CREATE TABLE IF NOT EXISTS events (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    ts        TEXT    NOT NULL,
    agent     TEXT    NOT NULL,
    kind      TEXT    NOT NULL,
    trace_id  TEXT,
    data      TEXT    NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_events_agent    ON events(agent);
CREATE INDEX IF NOT EXISTS idx_events_kind     ON events(kind);
CREATE INDEX IF NOT EXISTS idx_events_trace_id ON events(trace_id);
CREATE INDEX IF NOT EXISTS idx_events_ts       ON events(ts);
"""


def _utc_now_iso() -> str:
    return datetime.now(UTC).isoformat()


@dataclass(frozen=True)
class Event:
    """One recorded episode. ``data`` is the decoded JSON payload."""

    id: int
    ts: str
    agent: str
    kind: str
    trace_id: str | None
    data: dict[str, Any]


class EpisodicMemory:
    """A durable, queryable event log backed by SQLite.

    Thread-safe: a single shared connection is guarded by a lock, and the connection is
    opened with ``check_same_thread=False`` so the store may be shared across threads.
    """

    def __init__(
        self,
        path: str | Path = ":memory:",
        *,
        clock: Callable[[], str] | None = None,
    ) -> None:
        self._path = str(path)
        self._clock: Callable[[], str] = clock if clock is not None else _utc_now_iso
        self._lock = threading.RLock()
        if self._path != ":memory:":
            Path(self._path).parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(self._path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        with self._lock:
            self._conn.executescript(_SCHEMA)
            self._conn.commit()

    # --- writing ---

    def record(
        self,
        agent: str,
        kind: str,
        data: dict[str, Any] | None = None,
        *,
        trace_id: str | None = None,
        ts: str | None = None,
    ) -> int:
        """Append one event and return its row id. ``ts`` defaults to the current UTC time."""
        timestamp = self._clock() if ts is None else ts
        payload = json.dumps(data or {}, sort_keys=True, default=str)
        with self._lock:
            cur = self._conn.execute(
                "INSERT INTO events (ts, agent, kind, trace_id, data) VALUES (?, ?, ?, ?, ?)",
                (timestamp, agent, kind, trace_id, payload),
            )
            self._conn.commit()
            return int(cur.lastrowid or 0)

    # --- reading / querying ---

    @staticmethod
    def _row_to_event(row: sqlite3.Row) -> Event:
        return Event(
            id=row["id"],
            ts=row["ts"],
            agent=row["agent"],
            kind=row["kind"],
            trace_id=row["trace_id"],
            data=json.loads(row["data"]),
        )

    def get(self, event_id: int) -> Event | None:
        """Return the event with ``event_id``, or None if it does not exist."""
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM events WHERE id = ?", (event_id,)
            ).fetchone()
        return self._row_to_event(row) if row is not None else None

    def query(
        self,
        *,
        agent: str | None = None,
        kind: str | None = None,
        trace_id: str | None = None,
        since: str | None = None,
        limit: int | None = None,
    ) -> list[Event]:
        """Return matching events in chronological order (oldest first).

        ``since`` is an inclusive ISO-8601 lower bound on ``ts``. All filters AND together.
        """
        clauses: list[str] = []
        params: list[Any] = []
        if agent is not None:
            clauses.append("agent = ?")
            params.append(agent)
        if kind is not None:
            clauses.append("kind = ?")
            params.append(kind)
        if trace_id is not None:
            clauses.append("trace_id = ?")
            params.append(trace_id)
        if since is not None:
            clauses.append("ts >= ?")
            params.append(since)
        where = f" WHERE {' AND '.join(clauses)}" if clauses else ""
        sql = f"SELECT * FROM events{where} ORDER BY ts ASC, id ASC"
        if limit is not None:
            sql += " LIMIT ?"
            params.append(limit)
        with self._lock:
            rows = self._conn.execute(sql, params).fetchall()
        return [self._row_to_event(r) for r in rows]

    def all(self) -> list[Event]:
        """Every event, chronologically ordered."""
        return self.query()

    def count(self) -> int:
        """Total number of recorded events."""
        with self._lock:
            return int(self._conn.execute("SELECT COUNT(*) FROM events").fetchone()[0])

    def __len__(self) -> int:
        return self.count()

    def close(self) -> None:
        """Close the underlying SQLite connection."""
        with self._lock:
            self._conn.close()
