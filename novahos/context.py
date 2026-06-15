"""AgentContext — the object that makes one shared agent serve many apps. (Foundation; stdlib.)

Every shared agent takes an AgentContext describing WHAT it's doing and WHERE. Two calls to the
same WORDSMITH with different contexts produce an Instagram caption vs a LinkedIn post. This is
the heart of "agents are shared but use information according to the app/job."
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class AgentContext:
    app: str
    channel: str
    user_id: str
    account: Any = None
    goal: str | None = None
    playbook: dict | None = None
    lenses: dict | None = None
    voice: dict | None = None
    data_scope: frozenset[str] = frozenset()
    meta: dict = field(default_factory=dict)

    @property
    def compliance_mode(self) -> str:
        return getattr(self.account, "compliance_mode", "official") or "official"

    @property
    def playbook_key(self) -> str | None:
        return (self.playbook or {}).get("key")
