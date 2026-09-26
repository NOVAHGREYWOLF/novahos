"""Loading a manifest without PyYAML must say what to install.

`novahos` declares NO core dependencies — deliberately, so the stdlib rails stay installable
with nothing behind them. `AgentManifest.from_file` therefore lazy-imports PyYAML, which means
a consumer on plain `novahos` can import the class, call the method, and get
`ModuleNotFoundError: No module named 'yaml'`.

That error is importable-but-unusable, and it names a package the caller never asked for. It
cost reach six red tests on main and two misdiagnoses: first as a missing line in reach's own
requirements.txt, then as a missing declaration in the kernel's `agents` extra. Neither was it.
The traceback pointed into `site-packages/novahos/agent/manifest.py`, and the actual chain was
plain `novahos` -> no core deps -> no PyYAML -> lazy import fails at call time.

The fix is not to make PyYAML a core dependency, which would break the zero-dependency promise
for every consumer that never touches a manifest. It is to fail with an error that names the
extra. `novahos[manifests]` exists so that a service which only READS manifests does not have
to install litellm, river and sqlalchemy to do it.
"""
from __future__ import annotations

import builtins

import pytest

from novahos.agent.manifest import AgentManifest, ManifestError


@pytest.fixture
def no_pyyaml(monkeypatch, tmp_path):
    """Simulate plain `novahos`: PyYAML absent, everything else present."""
    real_import = builtins.__import__

    def fake_import(name, *a, **kw):
        if name == "yaml":
            raise ModuleNotFoundError("No module named 'yaml'")
        return real_import(name, *a, **kw)

    monkeypatch.setattr(builtins, "__import__", fake_import)
    p = tmp_path / "m.yaml"
    p.write_text("name: HERALD\n", encoding="utf-8")
    return p


def test_it_raises_manifest_error_not_module_not_found(no_pyyaml):
    """A ModuleNotFoundError escaping here is the bug: callers catch ManifestError."""
    with pytest.raises(ManifestError):
        AgentManifest.from_file(no_pyyaml)


def test_the_error_names_the_extra_to_install(no_pyyaml):
    """The whole point. 'No module named yaml' does not tell anyone what to do."""
    with pytest.raises(ManifestError) as ei:
        AgentManifest.from_file(no_pyyaml)
    msg = str(ei.value)
    assert "novahos[manifests]" in msg, msg
    assert "PyYAML" in msg, msg


def test_the_original_cause_is_chained(no_pyyaml):
    """Keep the real traceback: a clearer message must not cost anyone the evidence."""
    with pytest.raises(ManifestError) as ei:
        AgentManifest.from_file(no_pyyaml)
    assert isinstance(ei.value.__cause__, ModuleNotFoundError)


def test_the_manifests_extra_exists_and_is_lightweight():
    """It must stay cheap, or consumers will reach for `agents` and pull the whole runtime."""
    import pathlib
    import tomllib
    root = pathlib.Path(__file__).resolve().parent.parent
    extras = tomllib.loads((root / "pyproject.toml").read_text(
        encoding="utf-8"))["project"]["optional-dependencies"]
    assert "manifests" in extras, "novahos[manifests] is what the error message tells people to install"
    assert all("yaml" in d.lower() for d in extras["manifests"]), extras["manifests"]


def test_from_dict_still_needs_nothing(no_pyyaml):
    """The zero-dependency path must stay zero-dependency — that is why the import is lazy.

    Reuses the suite's existing valid manifest rather than hand-rolling one here, so this
    cannot drift into passing against a shape the real validator would reject."""
    from tests.test_agent import MANIFEST
    assert AgentManifest.from_dict(dict(MANIFEST)) is not None
