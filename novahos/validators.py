"""Deterministic pre-action validators. NO LLM. Hard guardrails WARDEN enforces. (Foundation; stdlib.)

Absolute caps a low risk score cannot buy off — platform publishing limits, the DM 24h window,
capability + opt-in checks. A validator returns violation strings; any non-empty result forces a
block regardless of score.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone

MAX_PUBLISH_PER_DAY = 25       # Meta Graph API hard limit (IG)
MAX_ENGAGE_PER_HOUR = 30
MAX_DM_PER_HOUR = 30


@dataclass
class ValidationContext:
    action_type: str
    compliance_mode: str = "official"
    capabilities: set[str] = field(default_factory=set)
    autonomous_optin: bool = False
    publishes_last_24h: int = 0
    engages_last_hour: int = 0
    dms_last_hour: int = 0
    dm_window_expires_at: datetime | None = None


def validate(ctx: ValidationContext) -> list[str]:
    v: list[str] = []

    if ctx.capabilities and ctx.action_type not in ctx.capabilities:
        v.append(f"action '{ctx.action_type}' not supported in {ctx.compliance_mode} mode")

    if ctx.compliance_mode == "autonomous" and not ctx.autonomous_optin:
        v.append("autonomous mode requires account.autonomous_optin=true")

    if ctx.action_type in {"publish_reel", "publish_post", "publish_story"}:
        if ctx.publishes_last_24h >= MAX_PUBLISH_PER_DAY:
            v.append(f"daily publish cap reached ({MAX_PUBLISH_PER_DAY}/24h)")

    if ctx.action_type == "engage" and ctx.engages_last_hour >= MAX_ENGAGE_PER_HOUR:
        v.append(f"engagement cap reached ({MAX_ENGAGE_PER_HOUR}/h)")

    if ctx.action_type == "send_dm":
        now = datetime.now(timezone.utc)
        if ctx.dm_window_expires_at is None or ctx.dm_window_expires_at < now:
            v.append("outside the 24h messaging window")
        if ctx.dms_last_hour >= MAX_DM_PER_HOUR:
            v.append(f"DM cap reached ({MAX_DM_PER_HOUR}/h)")
    if ctx.action_type == "cold_dm" and ctx.dms_last_hour >= MAX_DM_PER_HOUR:
        v.append(f"DM cap reached ({MAX_DM_PER_HOUR}/h)")

    return v
