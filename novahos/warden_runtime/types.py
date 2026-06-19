"""Shared types for the runtime WARDEN gate + its validators. (Foundation; stdlib.)

The richer, agent-runtime surface of WARDEN (ported from the NovahPrime foundation during the
NovahOS consolidation). The lean back-compat surface stays in `novahos.warden`
(`evaluate`/`score_action`); this is the stateful, multi-agent gate built on the same verdicts.

Verdict interop: `Decision.name.lower()` equals the `novahos.warden` string verdicts
(`approve`/`escalate`/`block`) — the two surfaces speak the same vocabulary.

Nothing here performs I/O or calls an LLM — WARDEN is deterministic.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum, IntEnum
from typing import Any, Protocol, runtime_checkable


class Decision(IntEnum):
    """A WARDEN verdict, ordered by severity so the engine can take the strictest."""

    APPROVE = 0
    ESCALATE = 1
    BLOCK = 2

    def __str__(self) -> str:  # pragma: no cover - cosmetic
        return self.name

    @property
    def verdict(self) -> str:
        """The lowercase string verdict, identical to novahos.warden's APPROVE/ESCALATE/BLOCK."""
        return self.name.lower()


class ConsentTier(Enum):
    """The three-tier consent model. Values match novahos.consent strings."""

    GREEN = "green"    # pre-authorized; act now, inform after
    YELLOW = "yellow"  # propose, wait for approval
    RED = "red"        # always escalate; real-time approval + re-auth


class AuthTier(IntEnum):
    """Authentication tiers by action sensitivity. Higher = stronger."""

    NONE = 0
    READ_ONLY = 1
    STANDARD = 2
    HIGH_VALUE = 3
    CATASTROPHIC = 4


class PrivacyTier(IntEnum):
    """Data classification. LOWER number = MORE private. TIER_1 must never reach cloud.

    Maps to novahos.privacy strings: TIER_1=private, TIER_2=semi, TIER_3=public.
    """

    TIER_1 = 1
    TIER_2 = 2
    TIER_3 = 3


class Principle(IntEnum):
    """The three ranked constitutional principles (lower number wins). Mirrors novahos.constitution."""

    USER_AUTONOMY = 1
    USER_SAFETY = 2
    USER_GOALS = 3

    @property
    def title(self) -> str:
        return {1: "User Autonomy", 2: "User Safety", 3: "User Goals"}[int(self)]


@dataclass(frozen=True)
class ConstitutionalCheck:
    """Per-action verdict against the principles. Passes when autonomy AND safety hold;
    goals alone never block. Agrees with novahos.constitution's ranking (autonomy>safety>goals)."""

    autonomy_ok: bool
    safety_ok: bool
    goals_ok: bool = True
    detail: str = ""

    @property
    def violated_principle(self) -> Principle | None:
        if not self.autonomy_ok:
            return Principle.USER_AUTONOMY
        if not self.safety_ok:
            return Principle.USER_SAFETY
        return None

    @property
    def passed(self) -> bool:
        return self.violated_principle is None


def _utc_now() -> datetime:
    return datetime.now(UTC)


@dataclass
class ActionRequest:
    """A request by an agent to take one action. Agents propose; WARDEN disposes."""

    agent: str
    action: str
    action_class: str
    payload: Any = None
    trace_id: str = field(default_factory=lambda: uuid.uuid4().hex)
    source_tier: PrivacyTier | None = None
    destination_tier: PrivacyTier | None = None
    destination: str | None = None
    amount: float | None = None
    timestamp: datetime = field(default_factory=_utc_now)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ValidatorResult:
    """The outcome of one validator (one of WARDEN's check steps)."""

    name: str
    decision: Decision
    reasons: tuple[str, ...] = ()
    required_auth_tier: AuthTier | None = None


# --- Provider protocols (the app-specific rules plug in behind these interfaces) ---


@runtime_checkable
class ConsentResolver(Protocol):
    def consent_tier(self, action_class: str) -> ConsentTier | None: ...
    def is_authorized(self, action_class: str) -> bool: ...


@runtime_checkable
class AuthStateProvider(Protocol):
    def required_tier(self, action_class: str) -> AuthTier: ...
    def current_tier(self) -> AuthTier: ...
    def cooling_satisfied(self, request: ActionRequest) -> bool: ...


@runtime_checkable
class SafetyClassifier(Protocol):
    def assess(self, request: ActionRequest) -> tuple[bool, str]: ...


@runtime_checkable
class ResourceTracker(Protocol):
    def check(self, request: ActionRequest) -> tuple[bool, list[str]]: ...
    def commit(self, request: ActionRequest) -> None: ...


@runtime_checkable
class ConflictRegistry(Protocol):
    def conflicts(self, request: ActionRequest) -> list[str]: ...
    def register(self, request: ActionRequest) -> None: ...


@runtime_checkable
class PrivacyResolver(Protocol):
    def is_cloud_destination(self, request: ActionRequest) -> bool: ...


@runtime_checkable
class Classifier(Protocol):
    def classify(self, data_type: str) -> PrivacyTier: ...


@dataclass
class WardenContext:
    """Everything a validator may consult for one request. Built by the engine per request."""

    request: ActionRequest
    consent: ConsentResolver
    auth: AuthStateProvider
    safety: SafetyClassifier
    resources: ResourceTracker
    conflicts_registry: ConflictRegistry
    privacy: PrivacyResolver
    classifier: Classifier | None = None


@runtime_checkable
class Validator(Protocol):
    """One WARDEN check step. Pure: inspects context, returns a result, no side effects."""

    name: str

    def check(self, ctx: WardenContext) -> ValidatorResult: ...
