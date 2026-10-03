"""Inbound source backends (extras: novahos[sources]). Importing this registers them.

The shared, platform-level inbound layer — the mirror of `channels/`. Apps import
`RawItem`/`SourceBackend` from here and resolve concrete backends via the registry.

The API-backed backends (plaid, quickbooks) need `httpx`, which is an OPTIONAL extra
(`novahos[sources]`). Importing them unconditionally made this whole package unimportable
without that extra — which silently took the *stdlib-only* backends down with it. The iPhone
backup parser is pure `sqlite3` and its docstring promises it "runs anywhere"; that promise was
false in any environment lacking httpx, including the hub's own venv. So the httpx-backed
backends register when their dependency is present and are skipped when it is not, rather than
failing the import for everyone.
"""
import contextlib

from .base import Connector, NotSupported, RawItem, SourceBackend  # noqa: F401
from .registry import all_sources, register, resolve  # noqa: F401

with contextlib.suppress(ModuleNotFoundError):
    from . import plaid, quickbooks  # noqa: F401 — side-effect: @register populates the registry

__all__ = ["Connector", "NotSupported", "RawItem", "SourceBackend",
           "all_sources", "register", "resolve"]
