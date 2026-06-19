"""The agent contract (Doc #26 §6): manifest -> agent -> 8-step onboarding -> propose/act through WARDEN.

Proves the ported foundation contract works on the novahos primitives: the Constitutional
Preamble is bound, the manifest enforces its invariants, onboarding gates activation, and an
agent can only execute a handler once ACTIVE and only after WARDEN approves — with an audit
entry on every decision.
"""
from __future__ import annotations

from datetime import timedelta

import pytest

from novahos.agent import (
    Agent,
    AgentManifest,
    AgentRegistry,
    ManifestError,
    OnboardingProcess,
    OnboardingState,
)
from novahos.constitution import preamble_present
from novahos.warden_runtime import build_warden

MANIFEST = {
    "agent": {"name": "TESTER", "version": "0.1.0", "purpose": "verify the contract", "tier": "SPECIALIST"},
    "constitution": {"principles_acknowledged": ["autonomy", "safety", "goals"], "override_capability": False},
    "consent": {"default_tier": "GREEN", "user_configurable": True, "red_actions": []},
    "auth": {"action_tier_map": {"read_data": "READ_ONLY"}},
    "data": {"reads_from": [], "writes_to": [], "privacy_tier": "TIER_2", "inference_categories": []},
    "warden": {"rate_limits": {"actions_per_hour": 100, "actions_per_day": 1000}},
    "audit": {
        "logs_to": "warden_audit_trail",
        "irreversible_actions_require_red": True,
        "reversible_actions": ["read_data"],
        "irreversible_actions": [],
    },
    "failure_modes": {"on_warden_block": "ESCALATE_TO_USER"},
}


def _make_agent() -> Agent:
    manifest = AgentManifest.from_dict(MANIFEST)
    return Agent(manifest, build_warden(), role_prompt="You are TESTER, a contract probe.")


def test_constitutional_preamble_is_bound():
    a = _make_agent()
    assert preamble_present(a.system_prompt)
    assert a.role_prompt in a.system_prompt


def test_manifest_rejects_override_capability():
    bad = {**MANIFEST, "constitution": {"principles_acknowledged": ["autonomy", "safety", "goals"],
                                         "override_capability": True}}
    with pytest.raises(ManifestError):
        AgentManifest.from_dict(bad)


def test_onboarding_gates_activation_and_warden_gates_action():
    a = _make_agent()
    reg = AgentRegistry()
    proc = OnboardingProcess(a, registry=reg, shadow_period=timedelta(0))

    # steps 1-5 + enter shadow, automatically
    assert proc.run_automated() is OnboardingState.SHADOW
    assert a.name in reg  # registered during onboarding (step 3); registry is keyed by name

    # SHADOW: an approved action is proposed + audited, but never executed
    a.register_action("ping", lambda payload, decision: "pong")
    shadow_res = a.act(action="ping", action_class="read", payload={})
    assert shadow_res.decision.approved
    assert shadow_res.shadow and not shadow_res.executed
    assert shadow_res.decision.audit_entry is not None

    # steps 7-8: user approves, then rollout -> ACTIVE
    proc.approve()
    proc.rollout()
    assert a.state is OnboardingState.ACTIVE

    # ACTIVE + approved: the handler executes
    active_res = a.act(action="ping", action_class="read", payload={})
    assert active_res.executed and active_res.output == "pong"
    assert active_res.decision.audit_entry is not None


def test_reasoning_seam_defaults_to_deterministic_local():
    a = _make_agent()
    out = a.reason("This is a test. It should summarize deterministically.")
    assert "Summary:" in out
    assert a.reasoning.model == "local-deterministic"
