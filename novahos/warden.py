"""WARDEN — the deterministic enforcement gate. NO LLM, ever. (Foundation; stdlib.)

Two APIs, one deterministic module, sharing the consent/constitution/privacy primitives:

  • SIMPLE (back-compat — the live Flask apps use this):
      evaluate(Action) -> Decision(verdict = approve | escalate | block)
    Checks auth → privacy transition → consent tier → resource limits.

  • NUMERIC (richer — content/social apps use this):
      score_action(RiskContext) -> RiskBreakdown   (deterministic 0..100)
      decide(risk, tier, threshold, hard_violations) -> GateDecision
          (auto_post | hold_yellow | block_red)
    A single per-account `threshold` unifies autonomous (high) vs approve-before (0).

The two verdict spaces map cleanly:  approve↔auto_post · escalate↔hold_yellow · block↔block_red
(see verdict_to_gate / gate_to_verdict). DB persistence of the audit trail is optional and lives
in novahos.warden_audit (substrate); the decision functions here stay pure stdlib.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from . import consent as _consent
from . import constitution as _con
from . import privacy as _privacy

# ── SIMPLE verdicts (back-compat) ─────────────────────────────────────────────
APPROVE = "approve"
ESCALATE = "escalate"
BLOCK = "block"

# ── NUMERIC verdicts ──────────────────────────────────────────────────────────
AUTO_POST = "auto_post"
HOLD_YELLOW = "hold_yellow"
BLOCK_RED = "block_red"

BLOCK_THRESHOLD = 70   # Safety hard line: at/above this, block regardless of goal value


# ── SIMPLE API (verbatim semantics from the original kernel) ──────────────────
@dataclass
class Action:
    kind: str
    authed: bool = True
    approved: bool = False
    consent_overrides: dict | None = None
    privacy_tier: str | None = None
    destination: str = "internal"          # internal | trusted | third_party
    resource_ok: bool = True
    meta: dict = field(default_factory=dict)


@dataclass
class Decision:
    verdict: str                  # approve | escalate | block
    reason: str
    principle: str | None = None
    consent_tier: str | None = None
    audit: dict = field(default_factory=dict)


def evaluate(action: Action) -> Decision:
    tier = _consent.tier_for(action.kind, action.consent_overrides)

    def _audit(verdict: str, reason: str, principle: str | None) -> dict:
        return {"kind": action.kind, "verdict": verdict, "reason": reason,
                "principle": principle, "consent_tier": tier,
                "privacy_tier": action.privacy_tier, "destination": action.destination}

    if not action.authed:
        return Decision(BLOCK, "no authenticated identity", _con.AUTONOMY, tier,
                        _audit(BLOCK, "unauthenticated", _con.AUTONOMY))
    if action.privacy_tier == _privacy.PRIVATE and action.destination == "third_party":
        return Decision(BLOCK, "PRIVATE data cannot go to a third party", _con.SAFETY, tier,
                        _audit(BLOCK, "private->third_party", _con.SAFETY))
    if _consent.requires_approval(tier) and not action.approved:
        return Decision(ESCALATE, f"consent tier {tier} requires approval", _con.AUTONOMY, tier,
                        _audit(ESCALATE, "needs_approval", _con.AUTONOMY))
    if not action.resource_ok:
        return Decision(BLOCK, "resource/quota limit exceeded", _con.SAFETY, tier,
                        _audit(BLOCK, "resource_limit", _con.SAFETY))
    return Decision(APPROVE, "ok", None, tier, _audit(APPROVE, "ok", None))


# ── NUMERIC API (deterministic risk scoring) ──────────────────────────────────
BACKEND_FLOOR = {"official": 0, "assisted": 30, "autonomous": 70}

ACTION_POINTS = {
    "read_insights": 0, "generate_caption": 0, "schedule_post": 5,
    "publish_reel": 10, "publish_post": 10, "publish_story": 10, "reply_comment": 10,
    "send_dm": 20, "engage": 15, "cold_dm": 30,
}

_PROFANITY = {"fuck", "shit", "bitch", "asshole", "cunt", "bastard"}
_MEDICAL = {"cure", "diagnosis", "treatment", "covid", "cancer", "vaccine", "disease", "fda"}
_FINANCIAL_CLAIM = {"guaranteed", "guarantee", "risk-free", "double your", "10x your", "get rich",
                    "passive income", "financial freedom", "roi", "returns"}
_POLITICAL = {"election", "democrat", "republican", "abortion", "immigration", "biden", "trump"}
_URL_RE = re.compile(r"https?://|www\.|\b\w+\.(com|net|org|io|co|ai|link)\b", re.I)
_MENTION_RE = re.compile(r"(?<!\w)@\w+")


@dataclass
class RiskContext:
    action_type: str
    compliance_mode: str = "official"
    text: str = ""
    playbook_key: str | None = None
    playbook_stakes: str = "low"
    requires_ai_disclosure: bool = False
    has_ai_disclosure: bool = False
    account_post_count: int = 0
    prior_rejections: int = 0
    prior_violations: int = 0
    is_novel_action: bool = False


@dataclass
class RiskBreakdown:
    score: int
    parts: dict[str, int] = field(default_factory=dict)
    flags: list[str] = field(default_factory=list)


@dataclass
class GateDecision:
    decision: str                  # auto_post | hold_yellow | block_red
    score: int
    tier: str
    threshold: int
    constitution_result: str
    violations: list[str] = field(default_factory=list)
    breakdown: dict = field(default_factory=dict)
    flags: list[str] = field(default_factory=list)

    @property
    def may_execute(self) -> bool:
        return self.decision == AUTO_POST


def _hits(text: str, words: set[str]) -> int:
    t = text.lower()
    return sum(1 for w in words if w in t)


def sensitivity_points(ctx: RiskContext) -> tuple[int, list[str]]:
    pts, flags = 0, []
    t = ctx.text or ""
    if _hits(t, _PROFANITY): pts += 8; flags.append("profanity")
    if _hits(t, _MEDICAL): pts += 10; flags.append("medical_claim")
    if _hits(t, _FINANCIAL_CLAIM): pts += 10; flags.append("financial_claim")
    if _hits(t, _POLITICAL): pts += 8; flags.append("political")
    if _URL_RE.search(t): pts += 4; flags.append("external_link")
    if _MENTION_RE.search(t): pts += 4; flags.append("mentions_others")
    pts = min(pts, 40)
    # Missing mandatory AI disclosure is added AFTER the cap so it can force a hold.
    if ctx.requires_ai_disclosure and not ctx.has_ai_disclosure:
        pts += 40
        flags.append("missing_ai_disclosure")
    return pts, flags


def score_action(ctx: RiskContext) -> RiskBreakdown:
    parts = {
        "backend_floor": BACKEND_FLOOR.get(ctx.compliance_mode, 0),
        "sensitivity": (sens := sensitivity_points(ctx))[0],
        "novelty": min((10 if ctx.account_post_count == 0 else 5 if ctx.account_post_count < 5 else 0)
                       + (5 if ctx.is_novel_action else 0), 15),
        "history": min(min(ctx.prior_rejections * 3, 10) + min(ctx.prior_violations * 15, 25), 25),
        "goal_stakes": {"low": 0, "medium": 7, "high": 15}.get(ctx.playbook_stakes, 0),
        "action_class": ACTION_POINTS.get(ctx.action_type, 15),
    }
    return RiskBreakdown(score=min(sum(parts.values()), 100), parts=parts, flags=sens[1])


def decide(*, risk: RiskBreakdown, tier: str, threshold: int, hard_violations: list[str]) -> GateDecision:
    """Pure decision — deterministic, no I/O. The testable core."""
    base = dict(score=risk.score, tier=tier, threshold=threshold, breakdown=risk.parts, flags=risk.flags)
    if hard_violations:
        return GateDecision(decision=BLOCK_RED, constitution_result="safety:hard_violation",
                            violations=hard_violations, **base)
    if tier == _consent.RED:
        return GateDecision(decision=BLOCK_RED, constitution_result="autonomy:red_consent", **base)
    if risk.score >= BLOCK_THRESHOLD:
        return GateDecision(decision=BLOCK_RED, constitution_result="safety:over_threshold", **base)
    if risk.score >= threshold:
        return GateDecision(decision=HOLD_YELLOW, constitution_result="goals:held_for_review", **base)
    return GateDecision(decision=AUTO_POST, constitution_result="goals:advanced", **base)


# ── verdict mapping between the two APIs ──────────────────────────────────────
_GATE_OF = {APPROVE: AUTO_POST, ESCALATE: HOLD_YELLOW, BLOCK: BLOCK_RED}
_VERDICT_OF = {AUTO_POST: APPROVE, HOLD_YELLOW: ESCALATE, BLOCK_RED: BLOCK}


def verdict_to_gate(verdict: str) -> str:
    return _GATE_OF.get(verdict, BLOCK_RED)


def gate_to_verdict(decision: str) -> str:
    return _VERDICT_OF.get(decision, BLOCK)
