"""The autonomy advisor may only ever ADD scrutiny — proved over the grid, not by inspection.

This module exists to spend the human's attention well: let confident, low-stakes work run with
a stop-window, and hard-escalate when confidence is low or stakes are high. The safety property
is that it can do that WITHOUT ever weakening WARDEN. Every recommendation's effective decision
must be >= WARDEN's own.

That claim rests on one thing: `Decision` is an `IntEnum` ordered APPROVE < ESCALATE < BLOCK, so
`max()` over it is a clamp that can only raise. `test_the_ordering_the_whole_proof_rests_on` pins
that premise directly. It is the test to keep if any are dropped: renumber or reorder the enum and
this module silently stops being a clamp while still reading exactly like one — the advisor would
go on citing "clamped up to WARDEN floor" in its reasons while handing back something looser.

The rest is exhaustive rather than illustrative. The grid is small enough to enumerate fully, so
these assert the property for EVERY combination instead of for the cases someone thought of.
"""
from __future__ import annotations

from enum import IntEnum
from itertools import product

import pytest

from novahos.agent.autonomy import (
    _AUTONOMY_FLOOR,
    Autonomy,
    AutonomyAdvisor,
    AutonomyThresholds,
    Stakes,
    abstain_or_proceed,
    confidence_valve,
    queue_score,
    should_abstain,
)
from novahos.warden_runtime.types import Decision

CONFIDENCES = (0.0, 0.2, 0.34, 0.35, 0.5, 0.64, 0.65, 0.8, 0.89, 0.90, 1.0)
GRID = tuple(product(tuple(Decision), tuple(Stakes), CONFIDENCES))


# -- the premise ---------------------------------------------------------------------------

def test_the_ordering_the_whole_proof_rests_on():
    """`max()` is only a clamp if Decision is ordered by severity. Pin it explicitly."""
    assert issubclass(Decision, IntEnum)
    assert Decision.APPROVE < Decision.ESCALATE < Decision.BLOCK


def test_the_autonomy_floor_map_is_non_decreasing():
    """Clamping with `max(natural, floor)` can only RAISE the effective decision if the
    Autonomy -> Decision map is monotone along Autonomy's own ordering. Insert a new level in
    the wrong place and the clamp inverts for that level while every other test still passes."""
    levels = sorted(Autonomy)
    floors = [_AUTONOMY_FLOOR[a] for a in levels]
    assert floors == sorted(floors), dict(zip([a.name for a in levels], [f.name for f in floors]))
    assert set(_AUTONOMY_FLOOR) == set(Autonomy), "every level needs a floor"


# -- the central property, over the whole grid ---------------------------------------------

@pytest.mark.parametrize("decision,stakes,confidence", GRID)
def test_advice_is_never_looser_than_warden(decision, stakes, confidence):
    """THE property. Every combination, no exceptions permitted."""
    advice = AutonomyAdvisor().advise(decision, stakes=stakes, confidence=confidence)
    assert advice.floor >= decision, (
        f"advisor LOWERED WARDEN: {decision.name} -> {advice.autonomy.name} "
        f"(floor {advice.floor.name}) at stakes={stakes.name} confidence={confidence}"
    )


@pytest.mark.parametrize("stakes,confidence", tuple(product(tuple(Stakes), CONFIDENCES)))
def test_a_block_never_comes_back_executable(stakes, confidence):
    """No confidence and no stakes reading may turn a BLOCK into anything that runs."""
    advice = AutonomyAdvisor().advise(Decision.BLOCK, stakes=stakes, confidence=confidence)
    assert advice.autonomy is Autonomy.BLOCK
    assert not advice.executes_now and not advice.schedules
    assert advice.delay_minutes == 0


@pytest.mark.parametrize("stakes,confidence", tuple(product(tuple(Stakes), CONFIDENCES)))
def test_an_escalate_never_comes_back_as_auto_execute(stakes, confidence):
    """A WARDEN escalation may be matched or exceeded, never spent down to an auto-run."""
    advice = AutonomyAdvisor().advise(Decision.ESCALATE, stakes=stakes, confidence=confidence)
    assert not advice.executes_now
    assert advice.floor >= Decision.ESCALATE


# -- what it is FOR: spending attention only where it buys something -----------------------

def test_confident_low_stakes_work_runs_now():
    advice = AutonomyAdvisor().advise(Decision.APPROVE, stakes=Stakes.LOW, confidence=0.95)
    assert advice.executes_now and advice.delay_minutes == 0 and not advice.tightened


def test_confident_medium_stakes_work_gets_a_stop_window():
    """The point of the module: not every approved action needs a human, but it can have a
    window in which one could intervene."""
    advice = AutonomyAdvisor().advise(Decision.APPROVE, stakes=Stakes.MEDIUM, confidence=0.80)
    assert advice.schedules
    assert advice.delay_minutes == AutonomyThresholds().timed_delay_minutes > 0


def test_high_stakes_escalates_however_confident():
    advice = AutonomyAdvisor().advise(Decision.APPROVE, stakes=Stakes.HIGH, confidence=1.0)
    assert advice.autonomy is Autonomy.ESCALATE and advice.tightened


def test_low_confidence_escalates_however_safe():
    advice = AutonomyAdvisor().advise(Decision.APPROVE, stakes=Stakes.LOW, confidence=0.1)
    assert advice.autonomy is Autonomy.ESCALATE and advice.tightened


def test_tightened_is_only_true_when_attention_was_actually_spent():
    """`tightened` is the module's own accounting of when it cost the human something."""
    adv = AutonomyAdvisor()
    assert not adv.advise(Decision.APPROVE, stakes=Stakes.LOW, confidence=0.95).tightened
    assert adv.advise(Decision.APPROVE, stakes=Stakes.HIGH, confidence=0.95).tightened
    # Matching WARDEN is not tightening — it added nothing of its own.
    assert not adv.advise(Decision.BLOCK, stakes=Stakes.HIGH, confidence=0.1).tightened


def test_reasons_are_always_given():
    """An escalation whose cause the human cannot see is one they cannot learn from."""
    for decision, stakes, confidence in GRID:
        advice = AutonomyAdvisor().advise(decision, stakes=stakes, confidence=confidence)
        assert advice.reasons, (decision, stakes, confidence)


def test_it_is_deterministic():
    adv = AutonomyAdvisor()
    for decision, stakes, confidence in GRID:
        first = adv.advise(decision, stakes=stakes, confidence=confidence)
        again = adv.advise(decision, stakes=stakes, confidence=confidence)
        assert first == again


# -- the valve -----------------------------------------------------------------------------

@pytest.mark.parametrize("decision,confidence", tuple(product(tuple(Decision), CONFIDENCES)))
def test_the_valve_is_one_way(decision, confidence):
    """It may raise a decision and must never lower one, at any confidence."""
    assert confidence_valve(decision, confidence) >= decision


def test_high_confidence_cannot_loosen_a_block():
    assert confidence_valve(Decision.BLOCK, 1.0) is Decision.BLOCK


def test_low_confidence_can_raise_an_approval():
    assert confidence_valve(Decision.APPROVE, 0.1) is Decision.ESCALATE


def test_the_block_threshold_is_opt_in():
    assert confidence_valve(Decision.APPROVE, 0.01) is Decision.ESCALATE
    assert confidence_valve(Decision.APPROVE, 0.01, block_below=0.1) is Decision.BLOCK


# -- abstention ----------------------------------------------------------------------------

def test_abstaining_says_what_would_help():
    """A refusal that names nothing is a dead end; the point is to return 'need more', with the
    what, rather than a fluent draft built on too little."""
    out = abstain_or_proceed(0.1, needs=("the customer's last reply",))
    assert out and out.abstained
    assert out.needs == ("the customer's last reply",)
    assert "not enough" in out.reason


def test_abstaining_always_names_something_even_unprompted():
    assert abstain_or_proceed(0.1).needs, "an empty needs tuple gives the human nothing to act on"


def test_proceeding_is_falsy_so_it_reads_as_a_guard():
    out = abstain_or_proceed(0.9)
    assert not out and not out.abstained and out.needs == ()


def test_the_threshold_is_exclusive():
    assert should_abstain(0.34) and not should_abstain(0.35) and not should_abstain(0.36)


# -- queue score ---------------------------------------------------------------------------

def test_score_rises_with_each_input_independently():
    base = dict(urgency=0.5, stakes=0.5, age_seconds=60.0)
    ref = queue_score(**base)
    assert queue_score(**{**base, "urgency": 0.9}) > ref
    assert queue_score(**{**base, "stakes": 0.9}) > ref
    assert queue_score(**{**base, "age_seconds": 600.0}) > ref


def test_age_saturates_so_an_old_trifle_cannot_outrank_a_fresh_emergency():
    """The reason age is `age/(age+halflife)` and not linear."""
    stale_trifle = queue_score(urgency=0.0, stakes=0.0, age_seconds=10**9)
    fresh_crisis = queue_score(urgency=1.0, stakes=1.0, age_seconds=0.0)
    assert stale_trifle < 1.0, "the age term must stay bounded below 1"
    assert fresh_crisis > stale_trifle


def test_negative_age_is_clamped_not_subtracted():
    """A clock skew must not produce a negative contribution that hides a real item."""
    assert queue_score(urgency=0.0, stakes=0.0, age_seconds=-5.0) == 0.0
