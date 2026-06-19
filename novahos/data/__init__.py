"""novahos.data — own-your-data lifecycle + inference compression. (Foundation; stdlib.)

  • inference  — non-reversible behavioral fingerprints + validation loop + versioning
                 (InferenceFingerprint / InferenceStore / ValidationResult)
  • lifecycle  — hot → warm → cold → archive policy (LifecyclePolicy / Stage / ColdAction)

Privacy *classification* (PRIVATE/SEMI/PUBLIC) is the canonical `novahos.privacy`; this
package is the retention + compression half. Stdlib only — import on demand.

Harvested from the NovahPrime foundation reference implementation (Doc #26 §2.5).
"""
from .inference import (  # noqa: F401
    DEFAULT_SIMILARITY_THRESHOLD,
    InferenceFingerprint,
    InferenceStore,
    ValidationResult,
)
from .lifecycle import ColdAction, LifecyclePolicy, Stage  # noqa: F401

__all__ = [
    "InferenceFingerprint", "InferenceStore", "ValidationResult",
    "DEFAULT_SIMILARITY_THRESHOLD",
    "LifecyclePolicy", "Stage", "ColdAction",
]
