"""WARDEN — the safety-critical core. Deterministic: no DB, no LLM, no network.

Covers BOTH the back-compat simple API (evaluate) and the numeric API (score_action/decide),
plus that the two verdict spaces map consistently."""
from novahos import consent, warden
from novahos.validators import ValidationContext, validate
from novahos.warden import Action, RiskContext, decide, evaluate, score_action


def _ctx(**kw) -> RiskContext:
    base = dict(action_type="publish_reel", compliance_mode="official", text="a normal caption")
    base.update(kw)
    return RiskContext(**base)


# ── numeric API: determinism + scoring ────────────────────────────────────────
def test_score_is_deterministic():
    c = _ctx(text="grow your reach today", playbook_stakes="high", account_post_count=3)
    assert score_action(c).score == score_action(c).score
    assert score_action(c).parts == score_action(c).parts


def test_official_clean_post_is_low_risk():
    assert score_action(_ctx(text="here is a tip", account_post_count=50)).score < 30


def test_backend_floor_orders_modes():
    clean = "a calm caption"
    off = score_action(_ctx(text=clean, account_post_count=50)).score
    asst = score_action(_ctx(text=clean, compliance_mode="assisted", account_post_count=50)).score
    auto = score_action(_ctx(text=clean, compliance_mode="autonomous", account_post_count=50)).score
    assert off < asst < auto and auto >= 70


def test_missing_ai_disclosure_forces_hold():
    r = score_action(_ctx(playbook_key="adapt_creator", playbook_stakes="high",
                          requires_ai_disclosure=True, has_ai_disclosure=False, account_post_count=50))
    assert "missing_ai_disclosure" in r.flags and r.score >= 60
    d = decide(risk=r, tier=consent.YELLOW, threshold=30, hard_violations=[])
    assert d.decision == warden.HOLD_YELLOW and not d.may_execute


# ── numeric API: decision logic ───────────────────────────────────────────────
def test_threshold_zero_holds_everything():
    r = score_action(_ctx(text="clean", account_post_count=50))
    assert decide(risk=r, tier=consent.YELLOW, threshold=0, hard_violations=[]).decision == warden.HOLD_YELLOW


def test_high_threshold_auto_posts_low_risk():
    r = score_action(_ctx(text="clean", account_post_count=50))
    d = decide(risk=r, tier=consent.YELLOW, threshold=70, hard_violations=[])
    assert d.decision == warden.AUTO_POST and d.may_execute


def test_red_tier_always_blocks():
    r = score_action(_ctx(text="clean", account_post_count=50))
    d = decide(risk=r, tier=consent.RED, threshold=100, hard_violations=[])
    assert d.decision == warden.BLOCK_RED and d.constitution_result == "autonomy:red_consent"


def test_safety_outranks_goals_over_threshold():
    r = score_action(_ctx(compliance_mode="autonomous", text="clean", account_post_count=50))
    d = decide(risk=r, tier=consent.YELLOW, threshold=100, hard_violations=[])
    assert d.decision == warden.BLOCK_RED and d.constitution_result == "safety:over_threshold"


def test_hard_violation_blocks_regardless():
    r = score_action(_ctx(text="clean", account_post_count=50))
    d = decide(risk=r, tier=consent.GREEN, threshold=100, hard_violations=["cap reached"])
    assert d.decision == warden.BLOCK_RED and "cap reached" in d.violations


# ── validators ────────────────────────────────────────────────────────────────
def test_daily_publish_cap_violation():
    v = validate(ValidationContext(action_type="publish_reel", publishes_last_24h=25,
                                   capabilities={"publish_reel"}))
    assert any("daily publish cap" in x for x in v)


def test_dm_outside_window_blocked():
    v = validate(ValidationContext(action_type="send_dm", capabilities={"send_dm"}, dm_window_expires_at=None))
    assert any("24h" in x for x in v)


# ── consent ───────────────────────────────────────────────────────────────────
def test_consent_defaults_and_overrides():
    assert consent.tier_for("publish_reel") == consent.RED
    assert consent.tier_for("read_insights") == consent.GREEN
    assert consent.tier_for("send_email") == consent.RED          # original kernel kind preserved
    assert consent.tier_for("publish_reel", {"publish_reel": "green"}) == consent.GREEN  # explicit override wins


# ── back-compat: the SIMPLE API the live apps use ─────────────────────────────
def test_evaluate_approves_green_authed():
    d = evaluate(Action(kind="read", authed=True))
    assert d.verdict == warden.APPROVE


def test_evaluate_escalates_unapproved_yellow():
    d = evaluate(Action(kind="create_draft", authed=True, approved=False))
    assert d.verdict == warden.ESCALATE


def test_evaluate_blocks_unauthed():
    d = evaluate(Action(kind="read", authed=False))
    assert d.verdict == warden.BLOCK


def test_evaluate_blocks_private_to_third_party():
    d = evaluate(Action(kind="read", authed=True, privacy_tier="private", destination="third_party"))
    assert d.verdict == warden.BLOCK


# ── verdict mapping between the two APIs ──────────────────────────────────────
def test_verdict_gate_mapping_is_consistent():
    assert warden.verdict_to_gate(warden.APPROVE) == warden.AUTO_POST
    assert warden.verdict_to_gate(warden.ESCALATE) == warden.HOLD_YELLOW
    assert warden.verdict_to_gate(warden.BLOCK) == warden.BLOCK_RED
    for v in (warden.APPROVE, warden.ESCALATE, warden.BLOCK):
        assert warden.gate_to_verdict(warden.verdict_to_gate(v)) == v
