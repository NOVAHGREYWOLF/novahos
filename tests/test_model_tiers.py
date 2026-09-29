"""The model-tier map: one answer to "which model?", and no silent fallback.

Stdlib-only, mirroring the module under test — it must hold on a plain `novahos` install.
"""
from __future__ import annotations

import re

import pytest

from novahos.model_tiers import (
    LEGACY_IDS,
    TIERS,
    UnknownTier,
    is_current,
    model_for,
    tier_for,
)

#: The shape of a first-party Claude alias: family, then a major (and optional minor) version.
#: Catches the `claude-haiku-3-5` class of mistake — an ID that reads plausibly and is not one.
_ALIAS = re.compile(r"^claude-(opus|sonnet|haiku|fable)-\d+(-\d+)?$")


def test_the_three_tiers_exist():
    assert set(TIERS) == {"reason", "write", "classify"}


@pytest.mark.parametrize("tier", sorted(TIERS))
def test_every_tier_maps_to_a_well_formed_alias(tier):
    model = model_for(tier)
    assert _ALIAS.match(model), model
    assert not re.search(r"-\d{8}$", model), "use the alias, not a dated snapshot"


def test_tiers_are_ordered_by_family():
    assert "opus" in model_for("reason")
    assert "sonnet" in model_for("write")
    assert "haiku" in model_for("classify")


def test_each_tier_is_a_different_model():
    assert len(set(TIERS.values())) == len(TIERS)


@pytest.mark.parametrize("bad", ["", "Reason", "fast", "opus", None, 3])
def test_unknown_tier_raises_rather_than_falling_back(bad):
    with pytest.raises(UnknownTier):
        model_for(bad)


def test_unknown_tier_is_a_key_error_and_names_the_choices():
    with pytest.raises(KeyError, match="classify"):
        model_for("nope")


def test_the_map_cannot_be_mutated_at_runtime():
    with pytest.raises(TypeError):
        TIERS["reason"] = "claude-haiku-4-5"  # type: ignore[index]
    with pytest.raises(TypeError):
        LEGACY_IDS["x"] = "reason"  # type: ignore[index]


@pytest.mark.parametrize("app_id,tier", [
    ("claude-sonnet-4-5", "write"),     # reach, scope
    ("claude-sonnet-4-6", "write"),     # signal
    ("claude-haiku-4-5", "classify"),   # scope — already current
    ("claude-haiku-3-5", "classify"),   # odyssey — not a valid ID
    ("claude-opus-4-8", "reason"),      # lucid
])
def test_every_id_found_in_the_apps_has_a_tier(app_id, tier):
    assert tier_for(app_id) == tier


def test_legacy_ids_are_not_current_and_point_at_real_tiers():
    for model_id, tier in LEGACY_IDS.items():
        assert tier in TIERS
        assert not is_current(model_id), model_id


def test_tier_for_round_trips_current_ids():
    for tier, model in TIERS.items():
        assert tier_for(model) == tier
        assert is_current(model)


def test_unknown_ids_have_no_tier():
    assert tier_for("gpt-4o") is None
    assert not is_current("claude-haiku-3-5")
