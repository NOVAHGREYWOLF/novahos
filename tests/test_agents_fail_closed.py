"""A closed door reaches the caller. It is not absorbed into a plausible-looking answer.

WHY THIS FILE EXISTS. Pinning the litellm calls at the gateway is only half of fail-closed. All
four agents that call `llm.reason()` wrap it in a bare `except Exception`, each for a good
reason of its own: a model that returns malformed JSON should not take down a content pipeline.
But `GatewayNotConfigured` is not a model that answered badly — it is a model that was never
asked, because we deliberately refused to spend. Absorbed into those handlers it becomes:

  * WORDSMITH   — a transcript-stub "draft". novahound publishes whatever `compose()` returns,
                  so the refusal ends as fallback prose on a real Instagram account.
  * CURATOR     — `{"index": 0, "reason": "default"}`, indistinguishable from a real ranking.
  * ORACLE      — `[]`, indistinguishable from a quiet week with nothing to suggest.
  * CROESUS     — `{}`, which lucid's Steward renders as a generic-but-real financial reading,
                  shown to a person, with nothing behind it.

Every one of those is a configuration failure wearing the costume of a normal result. The
gateway exceptions must pass through; everything else must still be caught, because the
existing fail-soft behaviour is deliberate and is not what this change is for.

The pairing is the point: each agent gets BOTH assertions, so a future edit cannot satisfy this
file by making the handler catch nothing at all.
"""
from __future__ import annotations

import pytest

pytest.importorskip("litellm", reason="novahos[substrate] not installed")
pytest.importorskip("pydantic_settings", reason="novahos[substrate] not installed")

from novahos import llm  # noqa: E402
from novahos.agents.apollo import curator, wordsmith  # noqa: E402
from novahos.agents.athena import oracle  # noqa: E402
from novahos.agents.croesus import advisor  # noqa: E402
from novahos.context import AgentContext  # noqa: E402


def _ctx():
    return AgentContext(app="x", channel="instagram", user_id="u",
                        playbook={"goal_type": "reach", "success_metric": "reach"},
                        lenses={"story": {"key": "story", "tone": "narrative"}})


def _refuse(exc):
    async def _boom(*_a, **_k):
        raise exc("the door is shut")
    return _boom


def _model_stumbled(*_a, **_k):
    """The failure the bare handlers were written for, and must keep absorbing."""
    async def _boom(*_a, **_k):
        raise ValueError("model returned malformed JSON")
    return _boom


GATEWAY_ERRORS = [llm.GatewayNotConfigured, llm.GatewayMisconfigured]


# ── WORDSMITH ────────────────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("exc", GATEWAY_ERRORS)
async def test_wordsmith_lets_a_closed_door_out(monkeypatch, exc):
    monkeypatch.setattr(wordsmith.llm, "reason", _refuse(exc))
    with pytest.raises(exc):
        await wordsmith.compose(_ctx(), "transcript text")


async def test_wordsmith_still_falls_back_when_the_model_merely_stumbles(monkeypatch):
    monkeypatch.setattr(wordsmith.llm, "reason", _model_stumbled())
    out = await wordsmith.compose(_ctx(), "First sentence. Second.")
    assert out[0]["body"], "the deliberate fallback for a bad answer must survive"


# ── CURATOR ──────────────────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("exc", GATEWAY_ERRORS)
async def test_curator_lets_a_closed_door_out(monkeypatch, exc):
    monkeypatch.setattr(curator.llm, "reason", _refuse(exc))
    with pytest.raises(exc):
        await curator.rank_dicts(_ctx(), [{"lens_key": "a", "body": "a"},
                                          {"lens_key": "b", "body": "b"}])


async def test_curator_still_defaults_when_the_model_merely_stumbles(monkeypatch):
    monkeypatch.setattr(curator.llm, "reason", _model_stumbled())
    d = await curator.rank_dicts(_ctx(), [{"lens_key": "a", "body": "a"},
                                          {"lens_key": "b", "body": "b"}])
    assert d["index"] == 0 and d["reason"] == "default"


# ── ORACLE ───────────────────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("exc", GATEWAY_ERRORS)
async def test_oracle_lets_a_closed_door_out(monkeypatch, exc):
    monkeypatch.setattr(oracle.llm, "reason", _refuse(exc))
    monkeypatch.setattr(oracle.suite, "get_journal_signals",
                        lambda *a, **k: {"text": "some notes"})
    with pytest.raises(exc):
        await oracle.content_angles("someone@example.com")


async def test_oracle_still_returns_empty_when_the_model_merely_stumbles(monkeypatch):
    monkeypatch.setattr(oracle.llm, "reason", _model_stumbled())
    monkeypatch.setattr(oracle.suite, "get_journal_signals",
                        lambda *a, **k: {"text": "some notes"})
    assert await oracle.content_angles("someone@example.com") == []


# ── CROESUS ──────────────────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("exc", GATEWAY_ERRORS)
async def test_croesus_lets_a_closed_door_out(monkeypatch, exc):
    """The one a person reads. A financial opinion with nothing behind it is worse than none."""
    monkeypatch.setattr(llm, "reason", _refuse(exc))
    with pytest.raises(exc):
        await advisor.assess({"monthly_burn": 4200})


async def test_croesus_still_returns_empty_when_the_model_merely_stumbles(monkeypatch):
    monkeypatch.setattr(llm, "reason", _model_stumbled())
    assert await advisor.assess({"monthly_burn": 4200}) == {}


async def test_croesus_needs_no_model_at_all_for_an_empty_snapshot(monkeypatch):
    """The pre-existing short-circuit: no snapshot means no call, so no door is involved."""
    monkeypatch.setattr(llm, "reason", _refuse(llm.GatewayNotConfigured))
    assert await advisor.assess({}) == {}
