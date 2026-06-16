"""Inference compression: behavioral fingerprints with a validation loop (Doc #26 §2.5).

Instead of retaining raw data forever, the system extracts a compact behavioral fingerprint,
validates it against held-out raw data, and (per the lifecycle) archives or deletes the raw.

The inference quality bar — a fingerprint is valid only if it is:
  - lossless for purpose,
  - privacy-preserving (non-reversible to raw — we store features + a source digest, never raw),
  - versioned,
  - validated against held-out raw data (>= 85% similarity target),
  - composable only where explicitly authorized.

Fingerprints are versioned and rollback-capable.
"""

from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Callable

DEFAULT_SIMILARITY_THRESHOLD = 0.85

# An extractor turns raw samples into a feature vector. It must not embed raw data.
Extractor = Callable[[list], dict[str, float]]


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _digest(samples: list) -> str:
    canonical = json.dumps(samples, sort_keys=True, default=str, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _cosine(a: dict[str, float], b: dict[str, float]) -> float:
    keys = set(a) | set(b)
    if not keys:
        return 1.0
    dot = sum(a.get(k, 0.0) * b.get(k, 0.0) for k in keys)
    na = math.sqrt(sum(v * v for v in a.values()))
    nb = math.sqrt(sum(v * v for v in b.values()))
    if na == 0.0 or nb == 0.0:
        return 0.0
    return max(0.0, min(1.0, dot / (na * nb)))


@dataclass(frozen=True)
class InferenceFingerprint:
    """A compact, non-reversible behavioral fingerprint. Carries no raw data."""

    category: str
    version: int
    features: dict[str, float]
    source_digest: str
    sample_count: int
    created_at: str = field(default_factory=_utc_now_iso)
    authorized_compositions: tuple[str, ...] = ()

    def is_reversible(self) -> bool:
        """A fingerprint must never let raw data be reconstructed. Always False here."""
        return False

    def may_compose_with(self, other_category: str) -> bool:
        return other_category in self.authorized_compositions


@dataclass(frozen=True)
class ValidationResult:
    similarity: float
    threshold: float
    valid: bool


class InferenceStore:
    """Versioned store of fingerprints per category, with validation and rollback."""

    def __init__(self, *, threshold: float = DEFAULT_SIMILARITY_THRESHOLD) -> None:
        self._threshold = threshold
        self._versions: dict[str, list[InferenceFingerprint]] = {}
        self._active: dict[str, int] = {}

    def extract(
        self,
        category: str,
        raw_samples: list,
        extractor: Extractor,
        *,
        authorized_compositions: tuple[str, ...] = (),
    ) -> InferenceFingerprint:
        """Build a candidate fingerprint from raw samples (not yet committed)."""
        features = extractor(raw_samples)
        next_version = len(self._versions.get(category, [])) + 1
        return InferenceFingerprint(
            category=category,
            version=next_version,
            features=dict(features),
            source_digest=_digest(raw_samples),
            sample_count=len(raw_samples),
            authorized_compositions=authorized_compositions,
        )

    def validate(
        self,
        fingerprint: InferenceFingerprint,
        holdout_samples: list,
        extractor: Extractor,
    ) -> ValidationResult:
        """Validate a fingerprint against held-out raw data via the same extractor."""
        holdout_features = extractor(holdout_samples)
        similarity = _cosine(fingerprint.features, holdout_features)
        return ValidationResult(
            similarity=similarity,
            threshold=self._threshold,
            valid=similarity >= self._threshold,
        )

    def commit(self, fingerprint: InferenceFingerprint, validation: ValidationResult) -> bool:
        """Store a fingerprint only if it passed validation. Returns whether it was stored."""
        if not validation.valid:
            return False
        versions = self._versions.setdefault(fingerprint.category, [])
        versions.append(fingerprint)
        self._active[fingerprint.category] = fingerprint.version
        return True

    def latest(self, category: str) -> InferenceFingerprint | None:
        v = self._active.get(category)
        if v is None:
            return None
        return self.get(category, v)

    def get(self, category: str, version: int) -> InferenceFingerprint | None:
        for fp in self._versions.get(category, []):
            if fp.version == version:
                return fp
        return None

    def versions(self, category: str) -> list[InferenceFingerprint]:
        return list(self._versions.get(category, []))

    def rollback(self, category: str, version: int) -> InferenceFingerprint:
        """Make a previous version the active one. Raises if the version does not exist."""
        fp = self.get(category, version)
        if fp is None:
            raise ValueError(f"No version {version} for inference category '{category}'.")
        self._active[category] = version
        return fp
