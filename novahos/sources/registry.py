"""Resolve a SourceBackend by key. (Sources.)

Apps call `resolve("plaid")` → the shared backend class, or `all_sources()` to list what the
platform can pull. Adding a source = `@register` it (or it self-registers on import); apps
don't change. Mirrors `channels/registry.py`.
"""
from __future__ import annotations

from .base import SourceBackend

_REGISTRY: dict[str, type[SourceBackend]] = {}


def register(cls: type[SourceBackend]) -> type[SourceBackend]:
    """Class decorator — register a source backend under its `source` key."""
    _REGISTRY[cls.source] = cls
    return cls


def resolve(source: str) -> type[SourceBackend] | None:
    return _REGISTRY.get(source)


def all_sources() -> dict[str, type[SourceBackend]]:
    return dict(_REGISTRY)
