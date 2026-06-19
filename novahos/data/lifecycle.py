"""The data lifecycle: hot -> warm -> cold -> archive (Doc #26 §2.5).

By absolute age from creation:
  - age <= hot_days                  -> HOT   (full raw data, real-time access)
  - hot_days < age <= warm_days      -> WARM  (raw + inference both stored)
  - age > warm_days                  -> COLD  (apply cold strategy: inference | archive | delete)

Compliance-required data types are retained in full and never cold-compressed. Per-type
overrides (e.g. a longer hot window for a journaling diary) come from the app's config —
construct with ``LifecyclePolicy.from_dict(...)`` (the kernel stays YAML/config-agnostic;
each app loads its own ``lifecycle`` config and passes the dict in).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class Stage(Enum):
    HOT = "hot"
    WARM = "warm"
    COLD = "cold"
    ARCHIVE = "archive"


class ColdAction(Enum):
    COMPRESS_TO_INFERENCE = "inference"  # keep fingerprint, archive/delete raw
    ARCHIVE = "archive"                  # move raw to cold storage
    DELETE = "delete"                    # delete raw
    RETAIN_FULL = "retain_full"          # compliance-exempt: keep everything


@dataclass
class LifecyclePolicy:
    hot_days: int = 7
    warm_days: int = 90
    cold_strategy: ColdAction = ColdAction.COMPRESS_TO_INFERENCE
    overrides: dict[str, dict] = field(default_factory=dict)
    compliance_exempt: set[str] = field(default_factory=set)

    @classmethod
    def from_dict(cls, raw: dict | None) -> "LifecyclePolicy":
        """Build from an app's ``lifecycle`` config dict (kernel-agnostic; no YAML here)."""
        raw = raw or {}
        defaults = raw.get("defaults", {})
        return cls(
            hot_days=int(defaults.get("hot_days", 7)),
            warm_days=int(defaults.get("warm_days", 90)),
            cold_strategy=ColdAction(defaults.get("cold_strategy", "inference")),
            overrides=raw.get("overrides") or {},
            compliance_exempt=set(raw.get("compliance_exempt") or []),
        )

    def _hot_days(self, data_type: str) -> int:
        return int(self.overrides.get(data_type, {}).get("hot_days", self.hot_days))

    def _warm_days(self, data_type: str) -> int:
        return int(self.overrides.get(data_type, {}).get("warm_days", self.warm_days))

    def stage_for(self, data_type: str, age_days: float) -> Stage:
        if age_days <= self._hot_days(data_type):
            return Stage.HOT
        if age_days <= self._warm_days(data_type):
            return Stage.WARM
        return Stage.COLD

    def cold_action_for(self, data_type: str) -> ColdAction:
        """What to do with raw data once it reaches COLD."""
        if data_type in self.compliance_exempt:
            return ColdAction.RETAIN_FULL
        return self.cold_strategy

    def action_for(self, data_type: str, age_days: float) -> ColdAction | None:
        """The lifecycle action to take now: None while HOT/WARM, a ColdAction at COLD."""
        if self.stage_for(data_type, age_days) is Stage.COLD:
            return self.cold_action_for(data_type)
        return None
