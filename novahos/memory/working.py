"""Working memory — the agent's volatile short-term scratchpad (Blueprint §6).

A Redis-like in-process key/value store with optional per-key TTL and per-session
scoping. It holds the transient state of an in-flight task: nothing here is durable, and
expired entries are indistinguishable from absent ones (``get`` returns the default).

Time is injectable. Pass ``now`` (a UNIX timestamp, float seconds) to any time-sensitive
method, or construct with a ``clock`` callable, so TTL behaviour is fully deterministic in
tests. All operations are guarded by a re-entrant lock for thread safety.
"""

from __future__ import annotations

import threading
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any


@dataclass
class _Entry:
    """One stored value plus its absolute expiry (UNIX seconds), or None for no TTL."""

    value: Any
    expires_at: float | None


class WorkingMemory:
    """In-process key/value store with optional TTL and session scoping.

    Keys are namespaced by an optional ``session`` so that concurrent sessions never see
    one another's working state. The default (``session=None``) is its own namespace.
    """

    def __init__(self, *, clock: Callable[[], float] | None = None) -> None:
        self._clock: Callable[[], float] = clock if clock is not None else time.time
        self._store: dict[tuple[str | None, str], _Entry] = {}
        self._lock = threading.RLock()

    # --- time ---

    def _resolve_now(self, now: float | None) -> float:
        return self._clock() if now is None else now

    @staticmethod
    def _is_expired(entry: _Entry, now: float) -> bool:
        return entry.expires_at is not None and now >= entry.expires_at

    # --- core operations ---

    def set(
        self,
        key: str,
        value: Any,
        ttl_seconds: float | None = None,
        *,
        session: str | None = None,
        now: float | None = None,
    ) -> None:
        """Store ``value`` under ``key``. If ``ttl_seconds`` is given the entry expires
        ``ttl_seconds`` after ``now`` (the injected/current time)."""
        current = self._resolve_now(now)
        expires_at = None if ttl_seconds is None else current + ttl_seconds
        with self._lock:
            self._store[(session, key)] = _Entry(value, expires_at)

    def get(
        self,
        key: str,
        default: Any = None,
        *,
        session: str | None = None,
        now: float | None = None,
    ) -> Any:
        """Return the value for ``key``, or ``default`` if absent or expired.

        Expired entries are evicted on access so the store does not grow unbounded.
        """
        current = self._resolve_now(now)
        with self._lock:
            entry = self._store.get((session, key))
            if entry is None:
                return default
            if self._is_expired(entry, current):
                del self._store[(session, key)]
                return default
            return entry.value

    def exists(
        self, key: str, *, session: str | None = None, now: float | None = None
    ) -> bool:
        """True iff ``key`` holds a live (non-expired) value."""
        sentinel = object()
        return self.get(key, sentinel, session=session, now=now) is not sentinel

    def delete(self, key: str, *, session: str | None = None) -> bool:
        """Delete ``key``. Returns True if a value was removed, False if absent."""
        with self._lock:
            return self._store.pop((session, key), None) is not None

    def clear(self, *, session: str | None = None) -> None:
        """Remove all keys. With ``session`` given, clears only that session's namespace."""
        with self._lock:
            if session is None and not any(s is not None for s, _ in self._store):
                self._store.clear()
                return
            to_drop = [k for k in self._store if k[0] == session]
            for k in to_drop:
                del self._store[k]

    def keys(
        self, *, session: str | None = None, now: float | None = None
    ) -> list[str]:
        """Live keys in a session's namespace (expired keys excluded and evicted)."""
        current = self._resolve_now(now)
        with self._lock:
            out: list[str] = []
            expired: list[tuple[str | None, str]] = []
            for (sess, key), entry in self._store.items():
                if sess != session:
                    continue
                if self._is_expired(entry, current):
                    expired.append((sess, key))
                else:
                    out.append(key)
            for k in expired:
                del self._store[k]
            return out

    def __len__(self) -> int:
        with self._lock:
            return len(self._store)

    # --- session scoping ---

    def scope(self, session_id: str) -> ScopedWorkingMemory:
        """Return a namespaced view bound to ``session_id``.

        The view shares the same backing store and lock; it simply pins every operation to
        the given session, so callers need not pass ``session=`` repeatedly.
        """
        return ScopedWorkingMemory(self, session_id)


class ScopedWorkingMemory:
    """A view of :class:`WorkingMemory` pinned to a single session id."""

    def __init__(self, parent: WorkingMemory, session_id: str) -> None:
        self._parent = parent
        self._session = session_id

    @property
    def session_id(self) -> str:
        return self._session

    def set(
        self,
        key: str,
        value: Any,
        ttl_seconds: float | None = None,
        *,
        now: float | None = None,
    ) -> None:
        self._parent.set(key, value, ttl_seconds, session=self._session, now=now)

    def get(self, key: str, default: Any = None, *, now: float | None = None) -> Any:
        return self._parent.get(key, default, session=self._session, now=now)

    def exists(self, key: str, *, now: float | None = None) -> bool:
        return self._parent.exists(key, session=self._session, now=now)

    def delete(self, key: str) -> bool:
        return self._parent.delete(key, session=self._session)

    def clear(self) -> None:
        self._parent.clear(session=self._session)

    def keys(self, *, now: float | None = None) -> list[str]:
        return self._parent.keys(session=self._session, now=now)
