"""The shared agent registry — every entry must actually resolve.

WHY THIS TEST AND NOT A DOC. `REGISTRY` maps a capability to a `"module:function"` STRING, so
nothing checks it at import time: a renamed function, a moved module or a typo leaves an entry
that looks right and returns `None` at the call site, in another repo, at runtime. `resolve()`
swallows the ImportError deliberately (an app must not crash because one capability moved), which
is correct and is exactly why the mistake is silent.

So the check has to be here. A registry entry that points nowhere is worse than a missing one: a
missing capability sends the caller looking, a broken one sends them debugging their own code.

IT VERIFIES BY READING THE SOURCE, NOT BY IMPORTING IT, and that is not a shortcut. Half these
targets pull `litellm` or `river`, which live in the `substrate` extra -- so an import-based test
passes or fails on which extras happen to be installed rather than on whether the registry is
right. It would go red in any environment without the extras, including the one novahound
installs. Parsing the module's AST answers the only question this file is asking (does that
module define that name) with no dependencies at all, so it gives the same verdict everywhere.

The live import still gets exercised, in the one test that skips when the extras are absent --
that catches an import-time error the AST cannot see, without making the suite depend on it.
"""
from __future__ import annotations

import ast
import importlib
import importlib.util
from pathlib import Path

import pytest

from novahos import agents


def _all_entries():
    return [(c, cap, spec)
            for c, caps in agents.REGISTRY.items()
            for cap, spec in caps.items()]


def _module_path(mod_name: str) -> Path | None:
    """Where a module's source lives, without importing it or its dependencies."""
    try:
        spec = importlib.util.find_spec(mod_name)
    except (ImportError, ValueError):
        return None
    return Path(spec.origin) if spec and spec.origin else None


def _defines(path: Path, name: str) -> bool:
    """True when this source file defines `name` at module level — def, async def, class or
    assignment. Reads the file; imports nothing."""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            if node.name == name:
                return True
        elif isinstance(node, ast.Assign):
            if any(isinstance(t, ast.Name) and t.id == name for t in node.targets):
                return True
    return False


@pytest.mark.parametrize("cluster,capability,spec", _all_entries())
def test_every_spec_names_a_real_module_and_attribute(cluster, capability, spec):
    """The load-bearing test. No imports, so it gives the same answer in every environment."""
    assert spec.count(":") == 1, f"{spec} must be 'module:function'"
    mod_name, fn_name = spec.split(":")

    path = _module_path(mod_name)
    assert path is not None and path.is_file(), (
        f"{cluster}.{capability} -> module '{mod_name}' does not exist")
    assert _defines(path, fn_name), (
        f"{cluster}.{capability} -> '{mod_name}' does not define '{fn_name}'")


@pytest.mark.parametrize("cluster,capability,spec", _all_entries())
def test_every_entry_resolves_when_its_dependencies_are_installed(cluster, capability, spec):
    """The live path, skipped rather than failed when an optional extra is absent.

    `resolve()` swallows ImportError on purpose, so this re-imports directly to see the real
    reason and skips only on a genuinely missing third-party module — never on a missing
    attribute, which is a real defect and must still fail here."""
    mod_name, fn_name = spec.split(":")
    try:
        importlib.import_module(mod_name)
    except ModuleNotFoundError as e:
        missing = (e.name or "").split(".")[0]
        if missing and missing != "novahos":
            pytest.skip(f"optional dependency '{missing}' not installed (substrate extra)")
        raise
    fn = agents.resolve(cluster, capability)
    assert fn is not None, f"{cluster}.{capability} -> {spec} did not resolve"
    assert callable(fn), f"{cluster}.{capability} -> {spec} is not callable"


def test_the_four_clusters_are_registered():
    """apollo and ig lived under agents/ for months with no entry, so resolve() returned None
    and novahound hard-imported them instead. Both are registered now; this pins that."""
    assert set(agents.REGISTRY) == {"athena", "croesus", "apollo", "ig"}


def test_capabilities_are_named_for_what_they_do():
    """A capability must not be named after its agent. The agent belongs on the right-hand side
    so it can be renamed, split or replaced without touching a caller."""
    agent_names = {"wordsmith", "curator", "publisher", "chronicle",
                   "oracle", "advisor", "bridge", "mediasmith", "dm_funnel", "insights"}
    for cluster, capability, _ in _all_entries():
        assert capability not in agent_names, (
            f"{cluster}.{capability} is named after an agent, not a capability")


def test_no_capability_shadows_another_in_the_same_cluster():
    for cluster, caps in agents.REGISTRY.items():
        assert len(caps) == len(set(caps)), f"{cluster} has a duplicate capability"


def test_resolve_answers_none_for_the_unknown():
    """Unknown degrades to None, never an exception — an app asking for a capability the kernel
    does not have must be able to fall back, not crash."""
    assert agents.resolve("apollo", "nope") is None
    assert agents.resolve("nope", "compose") is None
    assert agents.resolve("", "") is None


def test_novahounds_hard_imports_are_now_reachable_through_resolve():
    """The two hard imports that existed only because these clusters were unregistered.

    `novahound/compose.py`  -> from novahos.agents.apollo import curator, wordsmith
    `novahound/video_ingest.py` -> from novahos.agents.ig.transcriber import get_transcriber

    Both now have a registry route, so the app can switch to resolve() and stop pinning itself
    to the module layout. Asserted on the REGISTRY rather than on resolve(), so this holds
    whether or not the substrate extras are installed."""
    assert agents.REGISTRY["apollo"]["compose"].endswith("wordsmith:compose")
    assert agents.REGISTRY["apollo"]["rank_drafts"].endswith("curator:rank_dicts")
    assert agents.REGISTRY["ig"]["transcriber"].endswith("transcriber:get_transcriber")
