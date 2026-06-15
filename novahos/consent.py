"""Three-tier consent — how much autonomy the user grants an action kind. (Foundation; stdlib.)

  GREEN 🟢 pre-authorized: act immediately, log after.
  YELLOW 🟡 propose → user approves before execution.
  RED 🔴 always escalate: never act without explicit, real-time approval.

Conservative defaults (anything that sends/spends/deletes/posts is RED). Users configure per
kind; pattern-learning may *suggest* a change but never auto-promotes (Autonomy). Deterministic.
"""
from __future__ import annotations

GREEN = "green"
YELLOW = "yellow"
RED = "red"

# Conservative defaults by action kind. Apps extend this map; user overrides win.
DEFAULTS: dict[str, str] = {
    # read-only / low-risk → auto
    "read": GREEN,
    "search": GREEN,
    "label": GREEN,
    "ingest": GREEN,
    "summarize": GREEN,
    "suggest": GREEN,
    "read_insights": GREEN,
    "generate_caption": GREEN,
    # novel / cross-app → propose-approve
    "create_draft": YELLOW,
    "schedule": YELLOW,
    "schedule_post": YELLOW,
    "create_task": YELLOW,
    "sequence_stage": YELLOW,
    "reply_comment": YELLOW,
    # irreversible / outward / money → always ask
    "send_email": RED,
    "send_message": RED,
    "send_dm": RED,
    "post_social": RED,
    "publish_reel": RED,
    "publish_post": RED,
    "publish_story": RED,
    "engage": RED,
    "cold_dm": RED,
    "spend": RED,
    "transfer": RED,
    "delete_external": RED,
    "apply_job": RED,
    "campaign_approve": RED,
}

_ORDER = {GREEN: 0, YELLOW: 1, RED: 2}


def tier_for(action_kind: str, overrides: dict[str, str] | None = None, default: str = RED) -> str:
    """Resolve the consent tier for an action kind. Unknown kinds default to RED (safe).

    An explicit user override wins (a user choosing a tier IS Autonomy). The "never
    auto-promote" rule constrains *system*-suggested changes, not explicit user settings."""
    if overrides and action_kind in overrides:
        return overrides[action_kind]
    return DEFAULTS.get(action_kind, default)


def requires_approval(tier: str) -> bool:
    return tier in (YELLOW, RED)


def stricter(a: str, b: str) -> str:
    return a if _ORDER.get(a, 2) >= _ORDER.get(b, 2) else b
