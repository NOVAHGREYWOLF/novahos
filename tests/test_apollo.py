"""APOLLO compose/rank are pure (no DB) — the shared content brain any app can call.
LLM is monkeypatched so these run offline."""
import pytest

from novahos.agents.apollo import curator, wordsmith
from novahos.context import AgentContext


def _ctx():
    return AgentContext(app="x", channel="instagram", user_id="u",
                        playbook={"goal_type": "reach", "success_metric": "reach"},
                        lenses={"story": {"key": "story", "tone": "narrative"}})


@pytest.mark.asyncio
async def test_compose_returns_dicts(monkeypatch):
    async def fake_reason(system, user, max_tokens=2000):
        return '{"body":"hi","hooks":["h"],"tags":["#x"],"cta":"go"}'
    monkeypatch.setattr(wordsmith.llm, "reason", fake_reason)
    out = await wordsmith.compose(_ctx(), "transcript text")
    assert out and out[0]["body"] == "hi" and out[0]["lens_key"] == "story"
    assert out[0]["tags"] == ["#x"]


@pytest.mark.asyncio
async def test_compose_fallback_on_error(monkeypatch):
    async def boom(*a, **k):
        raise RuntimeError("no key")
    monkeypatch.setattr(wordsmith.llm, "reason", boom)
    out = await wordsmith.compose(_ctx(), "First sentence. Second.")
    assert out[0]["body"]  # transcript-derived fallback, never empty


@pytest.mark.asyncio
async def test_rank_single_variant():
    d = await curator.rank_dicts(_ctx(), [{"lens_key": "story", "body": "a"}])
    assert d["index"] == 0


@pytest.mark.asyncio
async def test_rank_picks_top_of_ranking(monkeypatch):
    async def fake_reason(system, user, max_tokens=2000):
        return '{"ranking":[1,0],"reason":"b is stronger"}'
    monkeypatch.setattr(curator.llm, "reason", fake_reason)
    d = await curator.rank_dicts(_ctx(), [{"lens_key": "a", "body": "a"},
                                          {"lens_key": "b", "body": "b"}])
    assert d["index"] == 1 and d["ranking"][0] == 1
