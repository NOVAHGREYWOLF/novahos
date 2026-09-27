"""A service's own outbound token must never authenticate it inbound.

THE DEFECT THIS PINS. `_per_spoke_tokens()` accepted every `SERVICE_TOKEN_*` in the
environment, on the stated grounds that it "accepts MORE tokens, never fewer". A service
presents its own token on every call it makes, so every callee receives it and anything
logging a request records it. Accepting it inbound let any of them replay it back and be
authenticated as a trusted mesh peer. And because a spoke's env holds the tokens of every
sibling it calls, one leaked token opened the inbound door of every service holding it —
collapsing per-spoke isolation back to "one token opens everything", which is the
arrangement the per-spoke migration existed to end.

HOW IT WAS FOUND, which is worth recording. lucid's `app/suite.py` had already excluded its
own token locally and stopped delegating to the kernel. Its `test_superset_of_shared_core`
asserted `not core.token_matches("hub-secret")` to document that lucid's inline path was a
deliberate superset of the kernel — and that assertion went red when the kernel widened
underneath it. A test written to characterise someone else's narrower behaviour caught a
security regression in it. The temptation was to repair the assertion; DOORS refused, on the
house rule that a test which exists to refuse a colour is never edited to make it green.

THE PROPERTY THAT PREVENTS AN OUTAGE, tested explicitly below: `SERVICE_TOKEN_HUB` is never
the excluded token. On novahub that one secret does two jobs — the hub presents it outbound
to spokes, and the cron services present it inbound to the hub. Excluding it would 403 every
cron tick. `own_outbound_token_env()` can only ever return a NON-hub name, so that failure is
structurally unreachable here rather than merely avoided.
"""
from __future__ import annotations

import pytest

from novahos import service_auth as sa

SPOKE = {"SERVICE_TOKEN_LUCID": "lucid-secret", "SERVICE_TOKEN_HUB": "hub-secret"}
ALL_TOKEN_ENVS = ("LEADFUEL_SERVICE_TOKEN", "SERVICE_TOKEN_LUCID", "SERVICE_TOKEN_HUB",
                  "SERVICE_TOKEN_ECHO", "SERVICE_TOKEN_ODYSSEY", "SERVICE_TOKEN_REACH")


@pytest.fixture(autouse=True)
def clean_env(monkeypatch):
    """Delete every token var explicitly, so a developer's real shell cannot make a
    fail-closed assertion pass by accident, and reset the once-only warning latch."""
    for k in ALL_TOKEN_ENVS:
        monkeypatch.delenv(k, raising=False)
    monkeypatch.setattr(sa, "_warned_self_only", False)


def env(monkeypatch, **kw):
    for k, v in kw.items():
        monkeypatch.setenv(k, v)


# ── the defect ───────────────────────────────────────────────────────────────────────────

def test_a_spoke_refuses_its_own_outbound_token_inbound(monkeypatch):
    """THE regression. Before the fix this returned True."""
    env(monkeypatch, **SPOKE)
    assert not sa.token_matches("lucid-secret")


def test_a_spoke_still_accepts_the_hub(monkeypatch):
    """The exclusion must not cost us the caller we exist to recognise."""
    env(monkeypatch, **SPOKE)
    assert sa.token_matches("hub-secret")


def test_a_spoke_still_accepts_the_legacy_shared_token(monkeypatch):
    """Migration-safe in the direction that was always true: nothing that worked stops."""
    env(monkeypatch, LEADFUEL_SERVICE_TOKEN="shared", **SPOKE)
    assert sa.token_matches("shared")


def test_junk_and_empty_are_still_refused(monkeypatch):
    env(monkeypatch, **SPOKE)
    assert not sa.token_matches("wrong")
    assert not sa.token_matches("")
    assert not sa.token_matches(None)


# ── the property that makes an outage structurally impossible ────────────────────────────

def test_the_hub_token_is_never_the_excluded_one(monkeypatch):
    """novahub's cron presents SERVICE_TOKEN_HUB INBOUND to novahub. If this exclusion could
    ever land on the hub token, every cron tick would 403 — a failure novahub has already
    suffered twice from the adjacent mismatch. own_outbound_token_env() filters HUB out of
    its candidates, so it cannot be returned no matter what else is set."""
    for extra in ({}, {"SERVICE_TOKEN_LUCID": "lucid-secret"},
                  {"SERVICE_TOKEN_LUCID": "a", "SERVICE_TOKEN_ECHO": "b"}):
        for k in ALL_TOKEN_ENVS:
            monkeypatch.delenv(k, raising=False)
        env(monkeypatch, SERVICE_TOKEN_HUB="hub-secret", **extra)
        assert sa.own_outbound_token_env() != "SERVICE_TOKEN_HUB"
        assert sa.token_matches("hub-secret"), f"hub token refused with extra={extra}"


def test_on_the_hub_nothing_is_excluded(monkeypatch):
    """The hub holds every spoke's token and must accept them all inbound, because every
    spoke calls the hub presenting its own. With more than one non-hub candidate there is no
    single answer, so the helper returns None and this is a deliberate no-op."""
    env(monkeypatch, SERVICE_TOKEN_HUB="hub-secret", SERVICE_TOKEN_LUCID="lucid-secret",
        SERVICE_TOKEN_ECHO="echo-secret", SERVICE_TOKEN_ODYSSEY="odyssey-secret")
    assert sa.own_outbound_token_env() is None
    for t in ("lucid-secret", "echo-secret", "odyssey-secret", "hub-secret"):
        assert sa.token_matches(t), f"hub refused {t}"


# ── honest edges ─────────────────────────────────────────────────────────────────────────

def test_self_only_config_disables_the_mesh_loudly(monkeypatch, caplog):
    """A service whose only token is its own can authenticate nobody. It used to report
    enabled by accepting its own outbound secret — the hole. 503 is the honest answer, and
    the warning means it never has to be diagnosed from a bare 503."""
    env(monkeypatch, SERVICE_TOKEN_LUCID="lucid-secret")
    with caplog.at_level("WARNING"):
        assert not sa.is_enabled()
    assert "must not authenticate inbound" in caplog.text
    assert "SERVICE_TOKEN_LUCID" in caplog.text


def test_a_spoke_with_the_hub_token_stays_enabled(monkeypatch):
    """The retirement path still works: the legacy shared token can go."""
    env(monkeypatch, **SPOKE)
    assert sa.is_enabled()


def test_a_duplicated_value_still_matches_through_its_other_name(monkeypatch):
    """Documented, not silently chosen. If the self token and the hub token hold the SAME
    value, excluding that value would refuse the hub — so the value stays accepted and the
    duplication is the misconfiguration to fix. Pinning it so the behaviour is deliberate."""
    env(monkeypatch, SERVICE_TOKEN_LUCID="same", SERVICE_TOKEN_HUB="same")
    assert sa.token_matches("same")


def test_an_unset_or_blank_self_token_is_not_a_candidate(monkeypatch):
    """A blank value is absence. With only a blank self token set, nothing is excluded and
    the hub is still recognised."""
    env(monkeypatch, SERVICE_TOKEN_LUCID="   ", SERVICE_TOKEN_HUB="hub-secret")
    assert sa.own_outbound_token_env() is None
    assert sa.token_matches("hub-secret")
