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
