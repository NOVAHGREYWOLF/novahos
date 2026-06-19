"""Runtime WARDEN gate — approve/escalate/block paths, audit chain, novahos-primitive bridge."""
from novahos.audit_trail import AuditTrail
from novahos.warden_runtime import (
    ActionRequest,
    AuthTier,
    ConsentTier,
    Decision,
    PrivacyTier,
    Warden,
    build_warden,
)
from novahos.warden_runtime.adapters import NovahosConsentResolver
from novahos.warden_runtime.providers import (
    AllowlistSafetyClassifier,
    DestinationPrivacyResolver,
    InMemoryConflictRegistry,
    InMemoryResourceTracker,
    RateLimit,
    StaticAuthStateProvider,
)


def _req(agent="CROESUS", action="read", action_class="read", **kw):
    return ActionRequest(agent=agent, action=action, action_class=action_class, **kw)


def test_verdict_interop_with_lean_warden():
    assert Decision.APPROVE.verdict == "approve"
    assert Decision.ESCALATE.verdict == "escalate"
    assert Decision.BLOCK.verdict == "block"


def test_green_read_approves():
    w = build_warden()
    d = w.evaluate(_req(action_class="read", payload={"q": "x"}))
    assert d.approved and d.verdict == "approve"
    assert d.audit_entry.decision == "APPROVE"


def test_red_action_escalates_with_reauth():
    w = build_warden()
    d = w.evaluate(_req(action="send", action_class="send_message"))
    assert d.escalated
    assert d.required_auth_tier is AuthTier.HIGH_VALUE  # RED consent demands re-auth


def test_unknown_action_class_escalates():
    # Not in novahos.consent DEFAULTS → is_authorized False → constitutional escalate.
    w = build_warden()
    assert w.evaluate(_req(action_class="frobnicate")).escalated


def test_consent_resolver_maps_novahos_tiers():
    r = NovahosConsentResolver()
    assert r.consent_tier("read") is ConsentTier.GREEN
    assert r.consent_tier("create_draft") is ConsentTier.YELLOW
    assert r.consent_tier("send_email") is ConsentTier.RED
    assert r.is_authorized("read") and not r.is_authorized("frobnicate")


def test_tier1_to_cloud_blocks():
    w = build_warden()
    d = w.evaluate(_req(action_class="read", source_tier=PrivacyTier.TIER_1,
                        destination="api.openai.com"))
    assert d.blocked  # PRIVATE data never leaves to a cloud destination


def test_most_severe_wins():
    # RED consent (escalate) + Tier-1→cloud (block) → BLOCK overall.
    w = build_warden()
    d = w.evaluate(_req(action="send", action_class="send_message",
                        source_tier=PrivacyTier.TIER_1, destination="api.openai.com"))
    assert d.decision is Decision.BLOCK


def _custom_warden(**over):
    base = dict(
        audit_trail=AuditTrail(), consent=NovahosConsentResolver(),
        auth=StaticAuthStateProvider(default_required=AuthTier.READ_ONLY, session_tier=AuthTier.READ_ONLY),
        safety=AllowlistSafetyClassifier(), resources=InMemoryResourceTracker(),
        conflicts=InMemoryConflictRegistry(), privacy=DestinationPrivacyResolver())
    base.update(over)
    return Warden(**base)


def test_resource_limit_blocks():
    w = _custom_warden(resources=InMemoryResourceTracker(rate_limit=RateLimit(actions_per_hour=1)))
    assert w.evaluate(_req()).approved        # 1st commits
    assert w.evaluate(_req()).blocked         # 2nd over cap → block


def test_cross_agent_conflict_escalates():
    w = _custom_warden()
    a = w.evaluate(_req(agent="A", metadata={"resource": "doc1", "writes": True}))
    assert a.approved                          # A claims doc1
    b = w.evaluate(_req(agent="B", metadata={"resource": "doc1", "writes": True}))
    assert b.escalated                         # B conflicts with A


def test_suspension_blocks():
    w = build_warden()
    w.suspend_agent("ROGUE")
    assert w.evaluate(_req(agent="ROGUE")).blocked
    w.reinstate_agent("ROGUE")
    assert w.evaluate(_req(agent="ROGUE")).approved


def test_every_decision_audited_and_chain_intact():
    w = build_warden()
    for _ in range(4):
        w.evaluate(_req())
    w.evaluate(_req(action="send", action_class="send_message"))
    assert len(w.audit_trail) == 5
    assert w.audit_trail.verify_integrity()
