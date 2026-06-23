"""Continuous behavioral authentication (Doc #26 §2.2).

Beyond point-in-time factors, the session is continuously validated against a behavioral
baseline (typing rhythm, interaction cadence, navigation patterns). When live behavior
diverges from the baseline beyond a threshold, the session is downgraded so the next
sensitive action forces step-up re-authentication.

The scoring is deterministic (cosine similarity to a baseline feature vector). It is a
signal, never an LLM judgment.

Ported into the shared kernel from NovahPrime/foundation/auth (Batch 1); only the import
path differs from the reference.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

from novahos.auth.three_factor import AuthSession


@dataclass(frozen=True)
class ContinuousResult:
    score: float          # 0.0 (no match) .. 1.0 (perfect match to baseline)
    ok: bool              # True if score >= threshold
    threshold: float


def _cosine_similarity(a: dict[str, float], b: dict[str, float]) -> float:
    keys = set(a) | set(b)
    if not keys:
        return 1.0
    dot = sum(a.get(k, 0.0) * b.get(k, 0.0) for k in keys)
    na = math.sqrt(sum(v * v for v in a.values()))
    nb = math.sqrt(sum(v * v for v in b.values()))
    if na == 0.0 or nb == 0.0:
        return 0.0
    return max(0.0, min(1.0, dot / (na * nb)))


@dataclass
class ContinuousAuth:
    """Maintains a behavioral baseline and scores live samples against it."""

    threshold: float = 0.70
    _baseline: dict[str, float] = field(default_factory=dict)
    _samples: int = 0

    def update_baseline(self, sample: dict[str, float]) -> None:
        """Fold a new behavioral sample into the running-average baseline."""
        self._samples += 1
        for k, v in sample.items():
            prev = self._baseline.get(k, v)
            self._baseline[k] = prev + (v - prev) / self._samples

    @property
    def has_baseline(self) -> bool:
        return self._samples > 0

    def score(self, sample: dict[str, float]) -> float:
        if not self.has_baseline:
            return 1.0  # nothing to compare against yet; do not penalize
        return _cosine_similarity(self._baseline, sample)

    def evaluate(self, sample: dict[str, float]) -> ContinuousResult:
        s = self.score(sample)
        return ContinuousResult(score=s, ok=s >= self.threshold, threshold=self.threshold)

    def monitor(self, session: AuthSession, sample: dict[str, float]) -> ContinuousResult:
        """Evaluate a live sample and revoke the session if behavior is anomalous."""
        result = self.evaluate(sample)
        if not result.ok:
            session.revoke()
        return result
