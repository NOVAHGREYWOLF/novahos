"""novahos — the NovahOS kernel. One foundation every NOVAH app runs on.

Layered so apps take only what they need:
  • rails       service_auth · service_client · knowledge        (stdlib)
  • foundation  constitution · consent · privacy · warden · validators · mcp · context · auth  (stdlib)
  • substrate   config · db · models · events · llm · learning · content_learning ·
                suite_mesh · warden_gate · warden_audit                 (extras: novahos[substrate])
  • agents      apollo · ig · athena  (AgentContext-driven)            (extras: novahos[agents])
  • channels    registry · instagram · linkedin                        (extras: novahos[channels])

`import novahos` stays light: this module imports NOTHING heavy. The stdlib rails +
foundation modules can be imported with zero non-stdlib dependencies (what the live Flask
apps rely on). Heavy modules (anything importing SQLAlchemy/litellm/river/httpx) pull their
deps only when you import them, and are declared as install extras in pyproject.toml.

Back-compat: the separate `leadfuel_core` shim package re-exports the rails + foundation
modules under their old import paths, so existing apps keep working unchanged.
"""
__version__ = "0.4.0"


def _installed_commit():
    """The git commit pip recorded for the installed novahos, or ``None``.

    Every spoke pins the kernel by commit (``novahos @ git+...@<sha>``), and pip writes that
    sha into the distribution's ``direct_url.json`` as ``vcs_info.commit_id``. Reading it back
    is the only way a running process can say WHICH kernel it is actually executing — the
    version string cannot, because 0.4.0 has meant a dozen different trees.

    Returns ``None``, never a guess, in every case where the commit cannot be established:

    * not a VCS install (a path install, an sdist, a wheel) — there is no ``direct_url.json``,
      or it has no ``vcs_info``;
    * novahos is not installed as a distribution at all;
    * **the installed distribution is not the code being executed.** This is the case that
      matters on this machine: 52 checkouts share interpreters through worktrees, so
      ``Distribution.from_name`` can happily find a site-packages novahos whose recorded sha
      describes a completely different tree than the one this module was imported from.
      Reporting that sha would be worse than reporting nothing, because it would look exactly
      like a successful check. So we compare the distribution's own novahos directory against
      this file's and return ``None`` when they differ.

    A caller that needs to FAIL on an unknown kernel should treat ``None`` as unknown and
    refuse, rather than reading it as "fine". Unknown is not a pass.
    """
    try:
        import json
        import os
        from importlib.metadata import Distribution

        dist = Distribution.from_name("novahos")
        # Only speak for the tree we are actually running.
        located = dist.locate_file("novahos")
        if os.path.realpath(str(located)) != os.path.realpath(os.path.dirname(__file__)):
            return None
        raw = dist.read_text("direct_url.json")
        if not raw:
            return None
        commit = ((json.loads(raw).get("vcs_info") or {}).get("commit_id") or "").strip()
        return commit or None
    except Exception:
        # Metadata is best-effort telemetry: it must never be the reason an import fails.
        return None


#: Commit of the installed kernel, or None when it cannot be established (see above).
__commit__ = _installed_commit()

# Convenience: the stdlib modules are safe to surface eagerly (no heavy imports).
from . import (  # noqa: F401
    auth,
    constitution,
    consent,
    context,
    knowledge,
    mcp,
    privacy,
    service_auth,
    service_client,
    validators,
    warden,
)

__all__ = [
    "service_auth", "service_client", "knowledge",
    "constitution", "consent", "privacy", "warden", "validators", "mcp", "context", "auth",
]
