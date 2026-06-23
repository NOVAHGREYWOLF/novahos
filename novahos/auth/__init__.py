"""novahos.auth — tiered three-factor + continuous behavioral authentication (Doc #26 §2.2).

The kernel's authentication module: factor verification, tiered capability (READ_ONLY →
CATASTROPHIC), expiring sessions, the catastrophic-action cooling delay, recovery friction,
and continuous behavioral monitoring. ``AuthState`` is a drop-in ``AuthStateProvider`` for the
runtime WARDEN gate — a real, session-backed replacement for ``StaticAuthStateProvider``.

stdlib-only (PBKDF2 + cosine similarity); biometric/hardware verifiers are injectable.
"""
from __future__ import annotations

from .continuous import ContinuousAuth, ContinuousResult
from .three_factor import (
    TIER_FACTOR_COUNT,
    AuthAttempt,
    AuthSession,
    AuthState,
    CoolingDelay,
    FactorType,
    RecoveryProcess,
    ThreeFactorAuth,
    capability_tier,
    hash_secret,
    normalize_seed,
    verify_secret,
)

__all__ = [
    "ThreeFactorAuth",
    "AuthAttempt",
    "FactorType",
    "AuthSession",
    "AuthState",
    "CoolingDelay",
    "RecoveryProcess",
    "ContinuousAuth",
    "ContinuousResult",
    "capability_tier",
    "hash_secret",
    "verify_secret",
    "normalize_seed",
    "TIER_FACTOR_COUNT",
]
