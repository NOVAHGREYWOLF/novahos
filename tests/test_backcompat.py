"""The leadfuel_core shim must keep the live apps' imports working unchanged."""
import leadfuel_core
from leadfuel_core import consent, constitution, knowledge, service_auth, service_client, warden  # noqa: F401


def test_shim_exposes_rails_and_governance():
    for name in ("service_auth", "service_client", "knowledge",
                 "constitution", "consent", "privacy", "warden", "mcp"):
        assert hasattr(leadfuel_core, name)


def test_submodule_import_path_resolves():
    # `import leadfuel_core.warden` style must also work, not just `from leadfuel_core import warden`.
    import leadfuel_core.warden as w
    import leadfuel_core.service_auth as sa
    assert hasattr(w, "evaluate") and hasattr(sa, "header_authed")


def test_warden_evaluate_still_behaves():
    d = warden.evaluate(warden.Action(kind="read", authed=True))
    assert d.verdict == warden.APPROVE
    d2 = warden.evaluate(warden.Action(kind="send_email", authed=True, approved=False))
    assert d2.verdict == warden.ESCALATE


def test_constitution_and_consent_api_intact():
    assert constitution.resolve("safety", "goals") == "safety"
    assert consent.tier_for("post_social") == consent.RED
    # mission_clause callable both ways (no-arg → preamble; with mission → rendered)
    assert constitution.mission_clause() == constitution.PREAMBLE
    assert "priorities" in constitution.mission_clause({"priorities": ["cash"]}).lower()
