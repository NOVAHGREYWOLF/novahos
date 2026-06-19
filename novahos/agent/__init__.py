"""The agent contract (Doc #26 §6) — the universal way every app declares its agents.

`from novahos.agent import Agent, AgentManifest, AgentRegistry, OnboardingProcess` gives an
app everything it needs to declare a manifest, build an agent that proposes-through-WARDEN,
run the eight-step onboarding, and register it in the fleet. Additive + stdlib-only (PyYAML
is imported lazily, only when a manifest is loaded from a file).
"""

from __future__ import annotations

from .base import Agent, AgentActionResult, Handler, OnboardingState
from .manifest import AgentManifest, ManifestError, validate_manifest
from .onboarding import OnboardingError, OnboardingProcess
from .registry import AgentRegistry, RegistryError

__all__ = [
    "Agent",
    "AgentActionResult",
    "Handler",
    "OnboardingState",
    "AgentManifest",
    "ManifestError",
    "validate_manifest",
    "AgentRegistry",
    "RegistryError",
    "OnboardingProcess",
    "OnboardingError",
]
