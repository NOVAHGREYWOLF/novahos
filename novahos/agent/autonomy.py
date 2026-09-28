"""The autonomy advisor — optimize the human's approval bandwidth WITHOUT weakening WARDEN.

WARDEN (novahos/warden_runtime/) is the deterministic safety floor: for one request it returns
`decision = max(validator severities)` over the strict ordering APPROVE < ESCALATE < BLOCK.
That guarantee is content-blind and non-negotiable. Nothing in this module may ever LOWER it.

Everything here is **tighten-only**. Given WARDEN's verdict the advisor may only:
  - add scrutiny (hard-escalate to the human), or
  - schedule (timed auto-execute: "run in N minutes unless the human stops it"), or
  - abstain ("I don't have enough to do this well" — return 'need more', not a fluent draft).
The *effective* decision it yields is always **>= WARDEN's decision**. When WARDEN escalates or
blocks, the advisor can only match or exceed that strictness; it can never hand back an
auto-execute. The scarce resource is the human's attention, so the advisor spends it only where
confidence is low or stakes are high, and lets confident, low-stakes work flow with a stop-window.

Pure stdlib, deterministic (same inputs -> same advice), no I/O, no LLM. Confidence is passed
in as a float rather than computed here: a host's own learning signal is the natural source, but
this module deliberately does not reach for one. That keeps it inside the kernel's zero-core-
dependency promise (`novahos.learning` lives in the substrate extra and is not importable on a
plain install), keeps the import graph one-directional, and keeps the advisor trivially testable.

PORTED VERBATIM from NovahPrime `foundation/agent/autonomy.py`, which is where it was written
and tested. Only the import path changed: `foundation.warden.types` -> `novahos.warden_runtime
.types`. The two `Decision` enums were compared before porting and are identical — `IntEnum`
with APPROVE=0, ESCALATE=1, BLOCK=2 — which is the whole basis of the tighten-only proof below,
since it rests on `max()` over that ordering. Had the kernel's enum been unordered or renumbered,
this module would have silently stopped being a clamp while still reading like one.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import IntEnum

from novahos.warden_runtime.types import Decision


class Stakes(IntEnum):
    """How costly getting this action wrong would be. Higher = more scrutiny warranted."""

    LOW = 0
    MEDIUM = 1
    HIGH = 2


class Autonomy(IntEnum):
    """How much autonomy the advisor grants, ordered by strictness (higher = stricter).

    Each level maps to a WARDEN `Decision` *floor* via `.floor`. That mapping is monotone
    non-decreasing along this ordering, which is what makes the tighten-only clamp provable:
    taking the stricter (max) of the natural recommendation and WARDEN's floor can only raise
    the effective decision, never lower it.
    """

    AUTO_EXECUTE = 0   # run now — nothing added beyond WARDEN's APPROVE
    TIMED_EXECUTE = 1  # run after a delay unless the human stops it (a scrutiny window)
    ESCALATE = 2       # hold for explicit human approval now
    ABSTAIN = 3        # decline to act; surface a structured 'need more' to the human
    BLOCK = 4          # do not execute

    @property
    def floor(self) -> Decision:
        """The WARDEN decision this autonomy level corresponds to (its severity floor)."""
        return _AUTONOMY_FLOOR[self]


# Autonomy level -> the WARDEN Decision it is consistent with. NON-DECREASING in Autonomy order
# (APPROVE, APPROVE, ESCALATE, ESCALATE, BLOCK) — see the class docstring.
_AUTONOMY_FLOOR: dict[Autonomy, Decision] = {
    Autonomy.AUTO_EXECUTE: Decision.APPROVE,
    Autonomy.TIMED_EXECUTE: Decision.APPROVE,
    Autonomy.ESCALATE: Decision.ESCALATE,
    Autonomy.ABSTAIN: Decision.ESCALATE,
    Autonomy.BLOCK: Decision.BLOCK,
}

# WARDEN Decision -> the LOOSEST autonomy still consistent with it. This is the clamp floor:
# nothing the advisor returns may be looser than this for a given WARDEN decision.
_DECISION_FLOOR_AUTONOMY: dict[Decision, Autonomy] = {
    Decision.APPROVE: Autonomy.AUTO_EXECUTE,
    Decision.ESCALATE: Autonomy.ESCALATE,
    Decision.BLOCK: Autonomy.BLOCK,
}


@dataclass(frozen=True)
class AutonomyThresholds:
    """Tunable, inspectable decision boundaries for the advisor. All in [0, 1] for confidence."""

    auto_confidence: float = 0.90   # >= this AND low stakes -> execute now
    confident: float = 0.65         # >= this -> confident enough to schedule (timed)
    abstain_below: float = 0.35     # < this -> too little to act well; hand to the human
    timed_delay_minutes: int = 10   # stop-window length for a timed auto-execute


@dataclass(frozen=True)
class AutonomyAdvice:
    """A tighten-only recommendation. `floor` is guaranteed to be >= `warden_decision`."""

    autonomy: Autonomy
    warden_decision: Decision
    reasons: tuple[str, ...] = ()
    delay_minutes: int = 0

    @property
    def floor(self) -> Decision:
        """The effective decision severity — never below WARDEN's."""
        return self.autonomy.floor

    @property
    def executes_now(self) -> bool:
        """True only for an immediate auto-execute (WARDEN-approved + safe + confident)."""
        return self.autonomy is Autonomy.AUTO_EXECUTE

    @property
    def schedules(self) -> bool:
        """True for a timed auto-execute — caller runs it after `delay_minutes` unless stopped."""
        return self.autonomy is Autonomy.TIMED_EXECUTE

    @property
    def tightened(self) -> bool:
        """True when the advisor added scrutiny *beyond* WARDEN's floor (spent human attention)."""
        return self.floor > self.warden_decision


class AutonomyAdvisor:
    """Recommends how much autonomy to grant a WARDEN-evaluated action — tighten-only.

    The advisor NEVER lowers a WARDEN decision. Its recommendation is computed from stakes and
    confidence, then clamped up to WARDEN's floor so the result is always at least as strict as
    WARDEN said. It optimizes *how* the human is asked (auto / timed-with-stop-window / escalate),
    never *whether* WARDEN's gate applies.
    """

    def __init__(self, thresholds: AutonomyThresholds | None = None) -> None:
        self.thresholds = thresholds or AutonomyThresholds()

    def advise(
        self,
        warden_decision: Decision,
        *,
        stakes: Stakes | int = Stakes.MEDIUM,
        confidence: float,
        action_class: str | None = None,
    ) -> AutonomyAdvice:
        """Return a tighten-only recommendation for a WARDEN-evaluated action.

        High-confidence + low-stakes -> timed (or immediate) auto-execute; high-stakes or
        low-confidence -> hard escalate. The result's `floor` is always >= `warden_decision`.
        """
        t = self.thresholds
        stakes = Stakes(stakes)
        warden_decision = Decision(warden_decision)
        reasons: list[str] = []

        # 1) Natural recommendation from stakes + confidence — computed independently of WARDEN,
        #    always defaulting toward MORE scrutiny when signals are weak or stakes are high.
        if confidence < t.abstain_below:
            natural = Autonomy.ESCALATE
            reasons.append(
                f"confidence {confidence:.2f} < abstain floor {t.abstain_below:.2f}: hand to the human"
            )
        elif stakes >= Stakes.HIGH:
            natural = Autonomy.ESCALATE
            reasons.append("high stakes: hard escalate for explicit approval")
        elif confidence < t.confident:
            natural = Autonomy.ESCALATE
            reasons.append(
                f"confidence {confidence:.2f} < confident {t.confident:.2f}: escalate"
            )
        elif stakes <= Stakes.LOW and confidence >= t.auto_confidence:
            natural = Autonomy.AUTO_EXECUTE
            reasons.append(
                f"low stakes + confidence {confidence:.2f} >= {t.auto_confidence:.2f}: auto-execute"
            )
        else:
            natural = Autonomy.TIMED_EXECUTE
            reasons.append(
                f"confident (>= {t.confident:.2f}), bounded stakes: timed auto-execute "
                f"(stop-window {t.timed_delay_minutes}m)"
            )

        # 2) Tighten-only clamp: never looser than WARDEN's floor. Because _AUTONOMY_FLOOR is
        #    monotone in Autonomy order, max() here can only raise the effective decision.
        floor = _DECISION_FLOOR_AUTONOMY[warden_decision]
        autonomy = max(natural, floor)
        if autonomy is not natural:
            reasons.append(f"clamped up to WARDEN floor ({warden_decision.name})")

        delay = t.timed_delay_minutes if autonomy is Autonomy.TIMED_EXECUTE else 0
        return AutonomyAdvice(
            autonomy=autonomy,
            warden_decision=warden_decision,
            reasons=tuple(reasons),
            delay_minutes=delay,
        )


# --- 2) Confidence one-way valve ------------------------------------------------------------


def confidence_valve(
    decision: Decision,
    confidence: float,
    *,
    escalate_below: float = 0.5,
    block_below: float | None = None,
) -> Decision:
    """A monotone, tighten-only valve: low confidence can RAISE a decision toward ESCALATE/BLOCK,
    but nothing here can ever lower it below WARDEN's floor.

    The valve only ever `max`es the incoming decision with a stricter one, so the return is
    guaranteed >= `decision` for every input. High confidence is a no-op (it cannot loosen).
    """
    decision = Decision(decision)
    adjusted = decision
    if block_below is not None and confidence < block_below:
        adjusted = max(adjusted, Decision.BLOCK)
    if confidence < escalate_below:
        adjusted = max(adjusted, Decision.ESCALATE)
    return adjusted


# --- 3) Abstention --------------------------------------------------------------------------


@dataclass(frozen=True)
class Abstention:
    """The outcome of an abstention check. Truthy when the agent is abstaining."""

    abstained: bool
    confidence: float
    threshold: float
    needs: tuple[str, ...] = ()
    reason: str = ""

    def __bool__(self) -> bool:
        return self.abstained


def should_abstain(confidence: float, *, threshold: float = 0.35) -> bool:
    """True when confidence is too low to do the task well (a plain predicate)."""
    return confidence < threshold


def abstain_or_proceed(
    confidence: float,
    *,
    threshold: float = 0.35,
    needs: tuple[str, ...] = (),
) -> Abstention:
    """Decide whether to abstain. Below threshold, return a structured 'need more' (what would
    raise confidence) instead of a fluent-but-underinformed draft; otherwise, clear to proceed.
    """
    if should_abstain(confidence, threshold=threshold):
        return Abstention(
            abstained=True,
            confidence=confidence,
            threshold=threshold,
            needs=tuple(needs) or ("more context or examples before drafting",),
            reason=(
                f"confidence {confidence:.2f} below {threshold:.2f}: not enough to do this well"
            ),
        )
    return Abstention(abstained=False, confidence=confidence, threshold=threshold)


# --- 4) Escalation queue score --------------------------------------------------------------


def queue_score(
    *,
    urgency: float,
    stakes: float,
    age_seconds: float,
    age_halflife_seconds: float = 3600.0,
    w_urgency: float = 1.0,
    w_stakes: float = 1.0,
    w_age: float = 1.0,
) -> float:
    """Rank the human's escalation queue. Higher score => review sooner.

    Pure and monotone increasing in each of urgency, stakes, and age (holding the others fixed),
    given non-negative weights. Age contributes a *saturating* term `age/(age+halflife)` in
    [0, 1) so a very old low-urgency item can never dominate a fresh high-urgency/high-stakes one.
    """
    age = max(0.0, age_seconds)
    age_factor = age / (age + age_halflife_seconds) if age_halflife_seconds > 0 else 1.0
    return w_urgency * urgency + w_stakes * stakes + w_age * age_factor
