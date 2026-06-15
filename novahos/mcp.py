"""MCP substrate — a thin, standards-aligned registry for external integrations. (Foundation; stdlib.)

Every integration is a named Tool with a JSON-schema input and a callable. Apps register tools;
the connector framework + agents discover them uniformly.
"""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field


@dataclass
class Tool:
    name: str
    description: str
    input_schema: dict = field(default_factory=dict)
    handler: Callable | None = None
    consent_kind: str = "read"
    privacy_default: str = "semi"


class Registry:
    def __init__(self) -> None:
        self._tools: dict[str, Tool] = {}

    def register(self, tool: Tool) -> None:
        self._tools[tool.name] = tool

    def get(self, name: str) -> Tool | None:
        return self._tools.get(name)

    def list(self) -> list[Tool]:
        return list(self._tools.values())

    def manifest(self) -> list[dict]:
        return [
            {"name": t.name, "description": t.description, "input_schema": t.input_schema}
            for t in self._tools.values()
        ]


registry = Registry()
