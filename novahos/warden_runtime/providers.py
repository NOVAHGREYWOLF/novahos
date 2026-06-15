"""Reference provider implementations for the runtime gate's protocols. (Foundation; stdlib.)

These make the gate runnable on its own and are what tests inject. Real deployments swap in
their own providers (e.g. a Redis-backed ResourceTracker) — the gate depends only on the
protocols, never on a concrete class. Ported from the NovahPrime foundation.
"""
from __future__ import annotations

import threading
from collections import deque
from dataclasses import dataclass, field
from datetime import timedelta

from .types import ActionRequest, AuthTier, ConsentTier


@dataclass
class DictConsentResolver:
    """ConsentResolver backed by a plain dict (action_class -> ConsentTier)."""

    consent_map: dict[str, ConsentTier] = field(default_factory=dict)
    unauthorized: set[str] = field(default_factory=set)

    def consent_tier(self, action_class: str) -> ConsentTier | None:
        return self.consent_map.get(action_class)

    def is_authorized(self, action_class: str) -> bool:
        if action_class in self.unauthorized:
            return False
        return action_class in self.consent_map


@dataclass
class StaticAuthStateProvider:
    """AuthStateProvider with a fixed required-tier map and a settable current session tier."""

    required_map: dict[str, AuthTier] = field(default_factory=dict)
    session_tier: AuthTier = AuthTier.READ_ONLY
    cooling_ok: bool = False
    default_required: AuthTier = AuthTier.STANDARD

    def required_tier(self, action_class: str) -> AuthTier:
        return self.required_map.get(action_class, self.default_required)

    def current_tier(self) -> AuthTier:
        return self.session_tier

    def cooling_satisfied(self, request: ActionRequest) -> bool:
        return self.cooling_ok


@dataclass
class AllowlistSafetyClassifier:
    """Deterministic safety check: unsafe if class in `unsafe_classes` or metadata['unsafe']."""

    unsafe_classes: set[str] = field(default_factory=set)

    def assess(self, request: ActionRequest) -> tuple[bool, str]:
        if request.metadata.get("unsafe"):
            return (False, str(request.metadata.get("unsafe_detail", "flagged unsafe by caller")))
        if request.action_class in self.unsafe_classes:
            return (False, f"action class '{request.action_class}' is classified unsafe")
        return (True, "")


@dataclass
class DestinationPrivacyResolver:
    """Fail-CLOSED PrivacyResolver: a named destination is cloud unless explicitly known-local.

    `metadata['local']=True` forces local; `metadata['cloud']=True` forces cloud; None = no transfer.
    """

    local_destinations: set[str] = field(default_factory=lambda: {
        "local", "localhost", "127.0.0.1", "::1", "on-device", "device",
        "file", "filesystem", "disk", "memory", ":memory:", "ollama",
    })

    def is_cloud_destination(self, request: ActionRequest) -> bool:
        if request.metadata.get("local"):
            return False
        if request.metadata.get("cloud"):
            return True
        dest = request.destination
        if not dest:
            return False
        return dest.strip().lower() not in self.local_destinations


@dataclass
class RateLimit:
    actions_per_hour: int = 120
    actions_per_day: int = 1000


@dataclass
class SpendingLimit:
    per_action: float = 500.0
    per_day: float = 2000.0


@dataclass
class InMemoryResourceTracker:
    """Sliding-window rate limits + daily spend, per agent. Thread-safe; check is read-only."""

    rate_limit: RateLimit = field(default_factory=RateLimit)
    spending_limit: SpendingLimit = field(default_factory=SpendingLimit)
    _events: dict[str, deque] = field(default_factory=dict)
    _spend: dict[str, deque] = field(default_factory=dict)
    _lock: threading.Lock = field(default_factory=threading.Lock)

    def _prune(self, agent: str, now) -> None:
        day_ago = now - timedelta(days=1)
        ev = self._events.setdefault(agent, deque())
        while ev and ev[0] < day_ago:
            ev.popleft()
        sp = self._spend.setdefault(agent, deque())
        while sp and sp[0][0] < day_ago:
            sp.popleft()

    def check(self, request: ActionRequest) -> tuple[bool, list[str]]:
        with self._lock:
            now = request.timestamp
            self._prune(request.agent, now)
            reasons: list[str] = []
            ev = self._events[request.agent]
            hour_ago = now - timedelta(hours=1)
            in_hour = sum(1 for t in ev if t >= hour_ago)
            if in_hour >= self.rate_limit.actions_per_hour:
                reasons.append(f"Rate limit: {in_hour}/{self.rate_limit.actions_per_hour} actions in the last hour.")
            if len(ev) >= self.rate_limit.actions_per_day:
                reasons.append(f"Rate limit: {len(ev)}/{self.rate_limit.actions_per_day} actions in the last day.")
            if request.amount is not None:
                if request.amount > self.spending_limit.per_action:
                    reasons.append(f"Spending: ${request.amount:.2f} exceeds per-action cap ${self.spending_limit.per_action:.2f}.")
                spent_today = sum(amt for _, amt in self._spend[request.agent])
                if spent_today + request.amount > self.spending_limit.per_day:
                    reasons.append(f"Spending: ${spent_today + request.amount:.2f} would exceed daily cap ${self.spending_limit.per_day:.2f}.")
            return (len(reasons) == 0, reasons)

    def commit(self, request: ActionRequest) -> None:
        with self._lock:
            now = request.timestamp
            self._events.setdefault(request.agent, deque()).append(now)
            if request.amount is not None:
                self._spend.setdefault(request.agent, deque()).append((now, request.amount))


@dataclass
class InMemoryConflictRegistry:
    """Tracks which agent currently holds a write claim on each named resource."""

    _holders: dict[str, str] = field(default_factory=dict)
    _lock: threading.Lock = field(default_factory=threading.Lock)

    def conflicts(self, request: ActionRequest) -> list[str]:
        resource = request.metadata.get("resource")
        if not resource or not request.metadata.get("writes", False):
            return []
        with self._lock:
            holder = self._holders.get(resource)
            if holder and holder != request.agent:
                return [holder]
            return []

    def register(self, request: ActionRequest) -> None:
        resource = request.metadata.get("resource")
        if resource and request.metadata.get("writes", False):
            with self._lock:
                self._holders[resource] = request.agent

    def release(self, resource: str) -> None:
        with self._lock:
            self._holders.pop(resource, None)
