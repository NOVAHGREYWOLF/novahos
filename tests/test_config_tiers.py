"""CoreSettings must not name a model itself: its defaults are the tier map's answers."""
import pytest

pytest.importorskip("pydantic_settings")

from novahos.config import CoreSettings
from novahos.model_tiers import model_for


def test_core_settings_model_defaults_come_from_the_tier_map(monkeypatch):
    monkeypatch.delenv("REASONING_MODEL", raising=False)
    monkeypatch.delenv("CHEAP_MODEL", raising=False)
    s = CoreSettings(_env_file=None)
    assert s.reasoning_model == model_for("reason")
    assert s.cheap_model == model_for("classify")


def test_env_still_overrides_the_defaults(monkeypatch):
    monkeypatch.setenv("REASONING_MODEL", "ollama/llama3.1")
    assert CoreSettings(_env_file=None).reasoning_model == "ollama/llama3.1"
