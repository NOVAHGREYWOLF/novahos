"""An unpriced model is metered as UNKNOWN cost (NULL), never as 0.0 ("free")."""
from __future__ import annotations

import logging

import pytest

pytest.importorskip("litellm", reason="novahos[substrate] not installed")
pytest.importorskip("pydantic_settings", reason="novahos[substrate] not installed")

from novahos import llm  # noqa: E402


def test_unpriced_model_is_unknown_not_zero(monkeypatch, caplog):
    def boom(**kw):
        raise Exception("This model isn't mapped yet: claude-opus-5-5")

    monkeypatch.setattr(llm.litellm, "completion_cost", boom)
    with caplog.at_level(logging.WARNING, logger=llm.log.name):
        assert llm._cost_or_none(object(), "claude-opus-5-5", 11, 7) is None
    assert "claude-opus-5-5" in caplog.text


def test_zero_price_for_a_call_that_used_tokens_is_unknown(monkeypatch):
    monkeypatch.setattr(llm.litellm, "completion_cost", lambda **kw: 0.0)
    assert llm._cost_or_none(object(), "m", 11, 7) is None


def test_priced_model_keeps_its_cost(monkeypatch, caplog):
    monkeypatch.setattr(llm.litellm, "completion_cost", lambda **kw: 0.0042)
    with caplog.at_level(logging.WARNING, logger=llm.log.name):
        assert llm._cost_or_none(object(), "claude-haiku-4-5", 11, 7) == 0.0042
    assert "cannot price" not in caplog.text


async def test_ledger_row_carries_null_cost_for_an_unpriced_model(monkeypatch):
    def boom(**kw):
        raise Exception("unmapped")

    monkeypatch.setattr(llm.litellm, "completion_cost", boom)
    seen = {}

    class _Conn:
        async def execute(self, stmt, params):
            seen.update(params)

    class _Begin:
        async def __aenter__(self):
            return _Conn()

        async def __aexit__(self, *a):
            return False

    class _Eng:
        def begin(self):
            return _Begin()

    monkeypatch.setattr(llm, "_shared_engine", lambda: _Eng())
    await llm._emit_shared(object(), "claude-opus-5-5", 11, 7)
    assert seen["cost"] is None and seen["model"] == "claude-opus-5-5"
