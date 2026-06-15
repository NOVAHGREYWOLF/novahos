"""leadfuel_core — backward-compat shim. The kernel is now `novahos`.

Every symbol the live apps import from `leadfuel_core` (rails + the stdlib governance layer)
is re-exported here from `novahos`, so existing apps keep working unchanged while we migrate
imports to `novahos` over time. The richer kernel additions (numeric WARDEN, agents, channels)
are available from `novahos` directly.

    from leadfuel_core import service_auth, service_client, knowledge   # rails (unchanged)
    from leadfuel_core import constitution, consent, privacy, warden, mcp  # governance (unchanged)
"""
import sys

from novahos import (  # noqa: F401
    consent,
    constitution,
    knowledge,
    mcp,
    privacy,
    service_auth,
    service_client,
    warden,
)

# Make `import leadfuel_core.<mod>` (not just `from leadfuel_core import <mod>`) resolve too.
for _name, _mod in {
    "service_auth": service_auth, "service_client": service_client, "knowledge": knowledge,
    "constitution": constitution, "consent": consent, "privacy": privacy,
    "warden": warden, "mcp": mcp,
}.items():
    sys.modules[f"{__name__}.{_name}"] = _mod

__all__ = [
    "service_auth", "service_client", "knowledge",
    "constitution", "consent", "privacy", "warden", "mcp",
]
