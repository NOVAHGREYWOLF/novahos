"""The agent registry — discovery and cross-agent coordination.

Holds the set of activated agents, supports lookup by name and tier, and routes a proposed
action to the agent(s) that handle its action class. WARDEN still gates every action; the
registry only decides *who* is asked to act, never whether an action is allowed.
"""

from __future__ import annotations

from .base import Agent, OnboardingState


class RegistryError(Exception):
    pass


class AgentRegistry:
    def __init__(self) -> None:
        self._agents: dict[str, Agent] = {}

    def register(self, agent: Agent) -> None:
        if agent.name in self._agents and self._agents[agent.name] is not agent:
            raise RegistryError(f"An agent named '{agent.name}' is already registered.")
        self._agents[agent.name] = agent

    def get(self, name: str) -> Agent:
        if name not in self._agents:
            raise RegistryError(f"No agent named '{name}'.")
        return self._agents[name]

    def all(self) -> list[Agent]:
        return list(self._agents.values())

    def by_tier(self, tier: str) -> list[Agent]:
        return [a for a in self._agents.values() if a.manifest.tier == tier]

    def active(self) -> list[Agent]:
        return [a for a in self._agents.values() if a.state is OnboardingState.ACTIVE]

    def handlers_for(self, action: str) -> list[Agent]:
        return [a for a in self._agents.values() if a.handles(action)]

    def __len__(self) -> int:
        return len(self._agents)

    def __contains__(self, name: object) -> bool:
        return name in self._agents
