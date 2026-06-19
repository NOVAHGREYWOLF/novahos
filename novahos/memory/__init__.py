"""novahos.memory — the 3-tier memory contract every agent shares. (Foundation; stdlib.)

  • working   — volatile per-session scratchpad (TTL)          WorkingMemory
  • episodic  — durable event log (sqlite)                     EpisodicMemory / Event
  • semantic  — relevance retrieval (pure-Python TF-IDF)       SemanticMemory

All stdlib, no heavy deps — `import novahos` stays light; import these on demand.
The hub (novahub) provides a richer semantic store (pgvector/Voyage) over the mesh;
`SemanticMemory` here is the dependency-free local/default implementation + the contract.

Harvested from the NovahPrime foundation reference implementation (Blueprint §6).
"""
from .episodic import EpisodicMemory, Event  # noqa: F401
from .semantic import SemanticMemory, tokenize  # noqa: F401
from .working import ScopedWorkingMemory, WorkingMemory  # noqa: F401

__all__ = [
    "WorkingMemory", "ScopedWorkingMemory",
    "EpisodicMemory", "Event",
    "SemanticMemory", "tokenize",
]
