"""Inbound source backends (extras: novahos[sources]). Importing this registers them.

The shared, platform-level inbound layer — the mirror of `channels/`. Apps import
`RawItem`/`SourceBackend` from here and resolve concrete backends via the registry.
"""
from . import plaid, quickbooks  # noqa: F401 — side-effect: @register populates the registry
from .base import Connector, NotSupported, RawItem, SourceBackend  # noqa: F401
from .registry import all_sources, register, resolve  # noqa: F401

__all__ = ["RawItem", "SourceBackend", "Connector", "NotSupported",
           "register", "resolve", "all_sources"]
