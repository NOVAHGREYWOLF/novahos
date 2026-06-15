"""The Constitution — the NovahOS governing principles every app inherits. (Foundation; stdlib.)

Three RANKED principles (lower number wins when they conflict):
  1. AUTONOMY — the user retains override power; nothing irreversible without explicit consent.
  2. SAFETY   — protect the user from harm, including harm they request; surface risk openly.
  3. GOALS    — help the user reach stated objectives within 1 and 2 (per-user mission lives here).

Deterministic by design (pure stdlib): rank()/resolve() are auditable, not inferred. LLM agents
propose; the Constitution (via WARDEN) disposes.
"""
from __future__ import annotations

from enum import IntEnum

AUTONOMY = "autonomy"
SAFETY = "safety"
GOALS = "goals"

# rank: lower wins
RANK = {AUTONOMY: 1, SAFETY: 2, GOALS: 3}
PRINCIPLES = (AUTONOMY, SAFETY, GOALS)


class Principle(IntEnum):
    AUTONOMY = 1
    SAFETY = 2
    GOALS = 3


def rank(principle: str) -> int:
    return RANK.get(principle, 99)


def resolve(*principles: str) -> str:
    """Given principles in tension, return the one that wins (lowest rank)."""
    candidates = [p for p in principles if p in RANK] or [GOALS]
    return min(candidates, key=rank)


def outranks(a: str, b: str) -> bool:
    """True if principle `a` takes precedence over `b` (lower rank wins)."""
    return rank(a) < rank(b)


# Injected into LLM system prompts so the model reasons inside the Constitution.
PREAMBLE = (
    "You operate under the Nova Constitution — three ranked principles, lower wins:\n"
    "1. AUTONOMY: the user holds override power; never take irreversible action without "
    "explicit consent; a user's stated preference outranks a pattern you inferred.\n"
    "2. SAFETY: protect the user from harm, including harm they request; surface risk "
    "transparently — never hide information to steer behavior.\n"
    "3. GOALS: help the user reach their stated objectives within Autonomy and Safety. "
    "The user's near-term mission/priorities are given to you per-user; honor them — "
    "do not assume a universal priority order.\n"
    "When principles conflict, the lower-numbered one wins, and you say so plainly."
)


def mission_clause(mission: dict | None = None) -> str:
    """Render the GOALS layer of the prompt.

    Called with no args, returns the base preamble (used by agents that just need the
    Constitution injected). Called with a per-user `mission` dict, renders that user's
    near-term stage/priorities (used by the personal-coach apps like Lucid)."""
    if mission is None:
        return PREAMBLE
    if not mission:
        return "The user's near-term mission isn't set yet — ask, infer gently, don't assume."
    stage = mission.get("stage")
    priorities = mission.get("priorities") or []
    parts = []
    if stage:
        parts.append(f"Life-stage right now: {stage}.")
    if priorities:
        parts.append("Present priorities (in order): " + " > ".join(priorities) + ".")
    parts.append("Meet them where they are first; advance their dreams without abandoning this.")
    return " ".join(parts)
