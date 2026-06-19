"""The Agent Manifest Standard (Doc #26 §6) — the universal contract.

Every agent declares a manifest before it can be activated. This module parses, validates,
and represents that manifest. Validation enforces the non-negotiable invariants:
  - override_capability is always False ("The Override Switch" anti-pattern),
  - the three principles are acknowledged,
  - consent is user-configurable,
  - the audit trail is the warden audit trail and irreversible actions require red consent.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from ..warden_runtime.types import AuthTier, ConsentTier

VALID_TIERS = {"ORCHESTRATOR", "DOMAIN", "SPECIALIST"}
REQUIRED_SECTIONS = (
    "agent",
    "constitution",
    "consent",
    "auth",
    "data",
    "warden",
    "audit",
    "failure_modes",
)
PRINCIPLES = ["autonomy", "safety", "goals"]


class ManifestError(Exception):
    """Raised when an agent manifest is missing, malformed, or non-compliant."""


@dataclass
class AgentManifest:
    name: str
    version: str
    purpose: str
    tier: str
    default_consent: ConsentTier
    red_actions: list[str]
    action_tier_map: dict[str, AuthTier]
    reads_from: list[str]
    writes_to: list[str]
    privacy_tier: str
    inference_categories: list[str]
    rate_limits: dict[str, int]
    spending_limits: dict[str, float]
    reversible_actions: list[str]
    irreversible_actions: list[str]
    raw: dict[str, Any] = field(default_factory=dict, repr=False)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> AgentManifest:
        validate_manifest(data)
        agent = data["agent"]
        consent = data["consent"]
        auth = data.get("auth", {})
        dat = data["data"]
        warden = data.get("warden", {})
        audit = data["audit"]
        action_tier_map = {
            k: AuthTier[v] for k, v in (auth.get("action_tier_map") or {}).items()
        }
        return cls(
            name=agent["name"],
            version=str(agent.get("version", "0.1.0")),
            purpose=agent["purpose"],
            tier=agent["tier"],
            default_consent=ConsentTier(consent["default_tier"].lower()),
            red_actions=list(consent.get("red_actions") or []),
            action_tier_map=action_tier_map,
            reads_from=list(dat.get("reads_from") or []),
            writes_to=list(dat.get("writes_to") or []),
            privacy_tier=str(dat.get("privacy_tier", "TIER_2")),
            inference_categories=list(dat.get("inference_categories") or []),
            rate_limits=dict(warden.get("rate_limits") or {}),
            spending_limits=dict(warden.get("spending_limits") or {}),
            reversible_actions=list(audit.get("reversible_actions") or []),
            irreversible_actions=list(audit.get("irreversible_actions") or []),
            raw=data,
        )

    @classmethod
    def from_file(cls, path: str | Path) -> AgentManifest:
        import yaml  # lazy: only manifests loaded from disk need PyYAML; from_dict stays stdlib

        p = Path(path)
        if not p.is_file():
            raise ManifestError(f"Manifest not found: {p}")
        return cls.from_dict(yaml.safe_load(p.read_text(encoding="utf-8")) or {})


def validate_manifest(data: dict[str, Any]) -> None:
    """Validate a manifest dict against the universal contract. Raises ManifestError."""
    if not isinstance(data, dict):
        raise ManifestError("Manifest must be a mapping.")

    for section in REQUIRED_SECTIONS:
        if section not in data:
            raise ManifestError(f"Manifest missing required section '{section}'.")

    agent = data["agent"]
    for key in ("name", "purpose", "tier"):
        if not agent.get(key):
            raise ManifestError(f"agent.{key} is required.")
    if agent["tier"] not in VALID_TIERS:
        raise ManifestError(f"agent.tier must be one of {sorted(VALID_TIERS)}.")

    con = data["constitution"]
    if con.get("override_capability") is not False:
        raise ManifestError("constitution.override_capability must be false — always.")
    if con.get("principles_acknowledged") != PRINCIPLES:
        raise ManifestError(f"constitution.principles_acknowledged must equal {PRINCIPLES}.")

    consent = data["consent"]
    if consent.get("user_configurable") is not True:
        raise ManifestError("consent.user_configurable must be true.")
    if str(consent.get("default_tier", "")).upper() not in {"GREEN", "YELLOW", "RED"}:
        raise ManifestError("consent.default_tier must be GREEN, YELLOW, or RED.")

    audit = data["audit"]
    if audit.get("logs_to") != "warden_audit_trail":
        raise ManifestError("audit.logs_to must be 'warden_audit_trail'.")
    if audit.get("irreversible_actions_require_red") is not True:
        raise ManifestError("audit.irreversible_actions_require_red must be true.")

    auth = data.get("auth", {})
    for action, tier in (auth.get("action_tier_map") or {}).items():
        if tier not in AuthTier.__members__:
            raise ManifestError(
                f"auth.action_tier_map['{action}'] = '{tier}' is not a valid AuthTier."
            )
