"""Playbook + lens loader mechanics (fixtures registered by conftest)."""
import pytest

from novahos.playbooks import loader


def test_fixtures_loaded():
    assert "demo" in loader.all_playbooks()
    assert "plain" in loader.all_lenses()


def test_resolve_returns_playbook_and_lenses():
    r = loader.resolve("demo")
    assert r["playbook"]["key"] == "demo"
    assert "plain" in r["lenses"] and r["lenses"]["plain"].get("tone")


def test_override_merges():
    pb = loader.get_playbook("demo", {"stakes": "high"})
    assert pb["stakes"] == "high"


def test_unknown_playbook_raises():
    with pytest.raises(KeyError):
        loader.get_playbook("does_not_exist")
