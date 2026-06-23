"""Three-factor authentication, tiered by action sensitivity (Doc #26 §2.2).

The three factor *types*:
  - BIOMETRIC      — something you are (face/fingerprint; plus continuous behavioral, see continuous.py)
  - KNOWLEDGE      — something you know (passphrase of 5+ words, plus a 12-word recovery seed)
  - HARDWARE_KEY   — something you have (WebAuthn/FIDO2 key or authenticator on a separate device)

The action tiers and what each requires:
  - READ_ONLY     — 1 factor
  - STANDARD      — 2 factors (any combination)
  - HIGH_VALUE    — 3 factors (all)
  - CATASTROPHIC  — 3 factors + a cooling delay

This module verifies presented factors deterministically and tracks session capability. The
biometric and hardware-key checks are deliberately injectable interfaces (a real deployment
wires in platform biometrics and a FIDO2 verifier); passphrase and recovery-seed checks use
stdlib PBKDF2 so secrets are only ever stored as salted hashes.

Ported into the shared kernel from NovahPrime/foundation/auth (Batch 1). The only change vs
the reference is the import path (kernel ``novahos.warden_runtime.types``). ``AuthState`` at
the bottom IS the ``AuthStateProvider`` the runtime WARDEN consumes — a real, session-backed
replacement for ``StaticAuthStateProvider``.
"""

from __future__ import annotations

import hashlib
import hmac
import os
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from enum import Enum

from novahos.warden_runtime.types import ActionRequest, AuthTier

_PBKDF2_ITERATIONS = 200_000


class FactorType(Enum):
    BIOMETRIC = "biometric"        # something you are
    KNOWLEDGE = "knowledge"        # something you know
    HARDWARE_KEY = "hardware_key"  # something you have


# What each action tier requires (Doc #26 §2.2).
TIER_FACTOR_COUNT: dict[AuthTier, int] = {
    AuthTier.READ_ONLY: 1,
    AuthTier.STANDARD: 2,
    AuthTier.HIGH_VALUE: 3,
    AuthTier.CATASTROPHIC: 3,  # 3 factors + cooling delay (cooling enforced separately)
}


# --- secret hashing (stdlib PBKDF2; no raw secrets ever stored) ---


def hash_secret(secret: str) -> str:
    """Return a salted PBKDF2-SHA256 hash string for a secret."""
    salt = os.urandom(16)
    dk = hashlib.pbkdf2_hmac("sha256", secret.encode("utf-8"), salt, _PBKDF2_ITERATIONS)
    return f"pbkdf2_sha256${_PBKDF2_ITERATIONS}${salt.hex()}${dk.hex()}"


def verify_secret(secret: str, stored: str) -> bool:
    """Constant-time verification of a secret against a stored PBKDF2 hash string."""
    try:
        algo, iters, salt_hex, hash_hex = stored.split("$")
        if algo != "pbkdf2_sha256":
            return False
        dk = hashlib.pbkdf2_hmac(
            "sha256", secret.encode("utf-8"), bytes.fromhex(salt_hex), int(iters)
        )
        return hmac.compare_digest(dk.hex(), hash_hex)
    except (ValueError, AttributeError):
        return False


def normalize_seed(seed: str) -> str:
    """Normalize a recovery seed phrase (lowercase, collapse whitespace) for hashing."""
    return " ".join(seed.lower().split())


# --- presented credentials ---


@dataclass
class AuthAttempt:
    """The credentials a caller presents in one authentication attempt.

    Each field is optional; whichever are present and verify successfully count toward the
    satisfied factor set. `biometric_sample` / `hardware_assertion` are opaque tokens handed
    to the injected verifiers.
    """

    passphrase: str | None = None
    biometric_sample: object | None = None
    hardware_assertion: object | None = None


# --- the engine ---


class ThreeFactorAuth:
    """Registers the user's factors and verifies attempts into a set of satisfied types."""

    def __init__(
        self,
        *,
        biometric_verifier: Callable[[object], bool] | None = None,
        hardware_verifier: Callable[[object], bool] | None = None,
    ) -> None:
        self._passphrase_hash: str | None = None
        self._recovery_seed_hash: str | None = None
        self._biometric_verifier = biometric_verifier
        self._hardware_verifier = hardware_verifier

    # registration

    def register_passphrase(self, passphrase: str) -> None:
        if len(passphrase.split()) < 5:
            raise ValueError("Passphrase must be at least 5 words.")
        self._passphrase_hash = hash_secret(passphrase)

    def register_recovery_seed(self, seed: str) -> None:
        if len(normalize_seed(seed).split()) < 12:
            raise ValueError("Recovery seed must be a 12-word BIP-39 phrase.")
        self._recovery_seed_hash = hash_secret(normalize_seed(seed))

    # verification

    def verify_passphrase(self, passphrase: str) -> bool:
        return self._passphrase_hash is not None and verify_secret(passphrase, self._passphrase_hash)

    def verify_recovery_seed(self, seed: str) -> bool:
        return self._recovery_seed_hash is not None and verify_secret(
            normalize_seed(seed), self._recovery_seed_hash
        )

    def verify(self, attempt: AuthAttempt) -> set[FactorType]:
        """Return the set of factor *types* satisfied by this attempt."""
        satisfied: set[FactorType] = set()
        if attempt.passphrase is not None and self.verify_passphrase(attempt.passphrase):
            satisfied.add(FactorType.KNOWLEDGE)
        if attempt.biometric_sample is not None and self._biometric_verifier is not None:
            if self._biometric_verifier(attempt.biometric_sample):
                satisfied.add(FactorType.BIOMETRIC)
        if attempt.hardware_assertion is not None and self._hardware_verifier is not None:
            if self._hardware_verifier(attempt.hardware_assertion):
                satisfied.add(FactorType.HARDWARE_KEY)
        return satisfied


def capability_tier(verified: set[FactorType]) -> AuthTier:
    """Map a set of verified factor types to the highest auth tier it can satisfy.

    Three factors reach CATASTROPHIC capability (the cooling delay is a separate, action-time
    gate enforced by WARDEN, not an extra factor).
    """
    n = len(verified)
    if n >= 3:
        return AuthTier.CATASTROPHIC
    if n == 2:
        return AuthTier.STANDARD
    if n == 1:
        return AuthTier.READ_ONLY
    return AuthTier.NONE


@dataclass
class AuthSession:
    """A live authentication session: which factor types are verified and when.

    Sessions expire; an expired session drops to NONE until factors are re-presented. The
    continuous behavioral check (continuous.py) can call `revoke` to force step-up.
    """

    ttl: timedelta = timedelta(hours=12)
    _verified: set[FactorType] = field(default_factory=set)
    _authenticated_at: datetime | None = None

    def authenticate(self, satisfied: set[FactorType], *, now: datetime | None = None) -> AuthTier:
        now = now or datetime.now(UTC)
        self._verified = set(satisfied)
        self._authenticated_at = now if satisfied else None
        return self.current_tier(now=now)

    def step_up(self, satisfied: set[FactorType], *, now: datetime | None = None) -> AuthTier:
        """Add newly satisfied factors to the session (for re-auth at a higher tier)."""
        now = now or datetime.now(UTC)
        self._verified |= set(satisfied)
        if self._verified:
            self._authenticated_at = now
        return self.current_tier(now=now)

    def revoke(self) -> None:
        self._verified = set()
        self._authenticated_at = None

    def is_expired(self, *, now: datetime | None = None) -> bool:
        if self._authenticated_at is None:
            return True
        now = now or datetime.now(UTC)
        return now - self._authenticated_at > self.ttl

    def current_tier(self, *, now: datetime | None = None) -> AuthTier:
        if self.is_expired(now=now):
            return AuthTier.NONE
        return capability_tier(self._verified)


@dataclass
class CoolingDelay:
    """Enforces the cooling delay for CATASTROPHIC actions (Doc #26 §2.2).

    The first time a given catastrophic action is seen, the clock starts and the action is
    not yet permitted; it becomes permitted only once the delay has elapsed on a later
    attempt. The action's identity is `metadata["cooling_key"]`, falling back to
    agent + action_class.
    """

    delay: timedelta = timedelta(hours=24)
    _started: dict[str, datetime] = field(default_factory=dict)

    @staticmethod
    def _key(request: ActionRequest) -> str:
        return request.metadata.get("cooling_key") or f"{request.agent}:{request.action_class}"

    def satisfied(self, request: ActionRequest, *, now: datetime | None = None) -> bool:
        now = now or datetime.now(UTC)
        key = self._key(request)
        started = self._started.get(key)
        if started is None:
            self._started[key] = now  # start the clock on first request
            return False
        return now - started >= self.delay

    def reset(self, request: ActionRequest) -> None:
        self._started.pop(self._key(request), None)


class RecoveryProcess:
    """Account recovery with deliberate friction: identity verification + a waiting period.

    Recovery is never instant (Doc #26 §2.2: "recovery friction"). The seed alone is not
    enough — identity must be verified and the waiting period must elapse before a new
    passphrase can be set.
    """

    def __init__(self, *, waiting_period: timedelta = timedelta(hours=24)) -> None:
        self._waiting_period = waiting_period
        self._initiated_at: datetime | None = None
        self._identity_verified = False

    def initiate(self, *, now: datetime | None = None) -> None:
        self._initiated_at = now or datetime.now(UTC)
        self._identity_verified = False

    def verify_identity(self, verified: bool = True) -> None:
        self._identity_verified = verified

    def can_recover(self, *, now: datetime | None = None) -> bool:
        if self._initiated_at is None or not self._identity_verified:
            return False
        now = now or datetime.now(UTC)
        return now - self._initiated_at >= self._waiting_period


@dataclass
class AuthState:
    """The `AuthStateProvider` WARDEN consumes — wires session + cooling + required-tier map.

    `required_map` is the action_class -> AuthTier mapping loaded from config/auth_tiers.yaml.
    Drop-in for ``warden_runtime.providers.StaticAuthStateProvider`` but backed by a real,
    expiring ``AuthSession`` and ``CoolingDelay``.
    """

    session: AuthSession
    cooling: CoolingDelay = field(default_factory=CoolingDelay)
    required_map: dict[str, AuthTier] = field(default_factory=dict)
    default_required: AuthTier = AuthTier.STANDARD

    def required_tier(self, action_class: str) -> AuthTier:
        return self.required_map.get(action_class, self.default_required)

    def current_tier(self) -> AuthTier:
        return self.session.current_tier()

    def cooling_satisfied(self, request: ActionRequest) -> bool:
        return self.cooling.satisfied(request)
