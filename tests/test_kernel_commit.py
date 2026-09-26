"""`novahos.__commit__` names the kernel actually running, or says nothing at all.

Every spoke pins the kernel by sha, and on this machine they have drifted: as of this commit
novahub's venv holds `d8de1241`, lucid's holds `82003222`, and main is elsewhere again. Three
different kernels, all reporting `__version__ == "0.4.0"`, because the version string has
meant a dozen trees. `__commit__` is how a running process answers "which one am I".

The load-bearing test here is `test_a_different_installed_tree_reports_nothing`. Fifty-two
checkouts share interpreters through worktrees, so `Distribution.from_name("novahos")` will
cheerfully find a site-packages distribution that has nothing to do with the code being
executed. Returning that sha would be worse than returning nothing: a wrong sha and a right
sha are the same shape, so it would read as a successful check. Unknown must look unknown.
"""
from __future__ import annotations

import importlib.metadata

import pytest

import novahos


class _FakeDist:
    """Stands in for an installed distribution, with a controllable location and payload."""

    def __init__(self, root, payload):
        self._root, self._payload = root, payload

    def locate_file(self, _name):
        return self._root

    def read_text(self, _name):
        return self._payload


def _install(monkeypatch, root, payload):
    monkeypatch.setattr(importlib.metadata.Distribution, "from_name",
                        staticmethod(lambda _n: _FakeDist(root, payload)))


@pytest.fixture
def here():
    """The directory novahos is genuinely running from."""
    import os
    return os.path.dirname(novahos.__file__)


def test_the_public_value_is_a_sha_or_nothing():
    """Never a guess, never a placeholder, never the version string."""
    assert novahos.__commit__ is None or (
        isinstance(novahos.__commit__, str) and len(novahos.__commit__) == 40
        and all(c in "0123456789abcdef" for c in novahos.__commit__)
    )


def test_a_vcs_install_of_this_tree_reports_its_sha(monkeypatch, here):
    """The mechanism must actually work — otherwise every test below passes vacuously."""
    sha = "0983c6736fe838c5ad3cf383a74cbdafa79923c8"
    _install(monkeypatch, here, '{"vcs_info": {"commit_id": "%s"}}' % sha)
    assert novahos._installed_commit() == sha


def test_a_different_installed_tree_reports_nothing(monkeypatch):
    """The case this function exists for: the dist found is not the code running.

    A sha from somebody else's checkout is indistinguishable from a correct answer, so it
    must not be returned. This is the same rule as a probe that times out saying `unknown`
    rather than `down` — a check that cannot establish a state must not report one.
    """
    sha = "0983c6736fe838c5ad3cf383a74cbdafa79923c8"
    _install(monkeypatch, "/somewhere/else/novahos", '{"vcs_info": {"commit_id": "%s"}}' % sha)
    assert novahos._installed_commit() is None


@pytest.mark.parametrize("payload", [
    None,                                   # no direct_url.json at all — not a VCS install
    "",                                     # present but empty
    "{}",                                   # no vcs_info — a path or sdist install
    '{"vcs_info": {}}',                     # vcs_info without a commit
    '{"vcs_info": {"commit_id": ""}}',      # commit recorded as empty
    '{"vcs_info": {"commit_id": "   "}}',   # whitespace is not a sha
    "not json at all",                      # corrupt metadata
])
def test_anything_short_of_a_recorded_sha_reports_nothing(monkeypatch, here, payload):
    _install(monkeypatch, here, payload)
    assert novahos._installed_commit() is None


def test_a_missing_distribution_is_not_an_error(monkeypatch):
    """Importing the kernel must never fail because its own metadata is unreadable."""
    def boom(_n):
        raise importlib.metadata.PackageNotFoundError("novahos")
    monkeypatch.setattr(importlib.metadata.Distribution, "from_name", staticmethod(boom))
    assert novahos._installed_commit() is None
