"""DI bridge — back the runtime gate with novahos's own primitives. (Foundation; stdlib.)

The gate depends only on protocols; these adapters wrap `novahos.consent` and `novahos.privacy`
so the runtime gate and the lean `novahos.warden` surface enforce ONE set of rules. `build_warden`
wires a ready gate with novahos-backed consent + reference providers + a fresh audit trail.
"""
from __future__ import annotations

from .. import consent as _consent
from .. import privacy as _privacy
from ..audit_trail import AuditTrail
from .gate import Warden
from .providers import (
    AllowlistSafetyClassifier,
    DestinationPrivacyResolver,
    InMemoryConflictRegistry,
    InMemoryResourceTracker,
    StaticAuthStateProvider,
)
from .types import ActionRequest, AuthTier, ConsentTier, PrivacyTier

_TIER_ENUM = {_consent.GREEN: ConsentTier.GREEN, _consent.YELLOW: ConsentTier.YELLOW,
              _consent.RED: ConsentTier.RED}
_PRIVACY_ENUM = {_privacy.PRIVATE: PrivacyTier.TIER_1, _privacy.SEMI: PrivacyTier.TIER_2,
                 _privacy.PUBLIC: PrivacyTier.TIER_3}


class NovahosConsentResolver:
    """ConsentResolver backed by `novahos.consent` (the same tiers the lean WARDEN uses).

    `consent_tier` maps the kernel's string tier to the enum. `is_authorized` is true for a
    *known* action kind (one with a default tier or a user override) — an unknown kind is
    unauthorized, so the constitutional step escalates it (caution).
    """

    def __init__(self, overrides: dict[str, str] | None = None) -> None:
        self.overrides = overrides or {}

    def consent_tier(self, action_class: str) -> ConsentTier:
        return _TIER_ENUM.get(_consent.tier_for(action_class, self.overrides), ConsentTier.RED)

    def is_authorized(self, action_class: str) -> bool:
        return action_class in self.overrides or action_class in _consent.DEFAULTS


class NovahosPrivacyClassifier:
    """Classifier that derives a PrivacyTier from a data_type via `novahos.privacy.classify`."""

    def classify(self, data_type: str) -> PrivacyTier:
        return _PRIVACY_ENUM.get(_privacy.classify("", data_type), PrivacyTier.TIER_1)


def build_warden(
    *,
    consent_overrides: dict[str, str] | None = None,
    unsafe_classes: set[str] | None = None,
    audit_path=None,
) -> Warden:
    """A ready runtime gate wired to novahos primitives + in-memory reference providers.

    Defaults are conservative (safe): novahos consent tiers, fail-closed privacy, a fresh
    hash-chained audit trail. Pass `audit_path` for a durable JSONL trail.
    """
    return Warden(
        audit_trail=AuditTrail(audit_path),
        consent=NovahosConsentResolver(consent_overrides),
        # A normal authenticated session reads freely; sensitive kinds escalate via consent
        # (RED → required HIGH_VALUE). Apps can inject a stricter required-tier map.
        auth=StaticAuthStateProvider(default_required=AuthTier.READ_ONLY,
                                     session_tier=AuthTier.READ_ONLY),
        safety=AllowlistSafetyClassifier(unsafe_classes or set()),
        resources=InMemoryResourceTracker(),
        conflicts=InMemoryConflictRegistry(),
        privacy=DestinationPrivacyResolver(),
        classifier=NovahosPrivacyClassifier(),
    )


__all__ = ["NovahosConsentResolver", "NovahosPrivacyClassifier", "build_warden", "ActionRequest"]
