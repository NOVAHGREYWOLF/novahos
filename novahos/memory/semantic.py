"""Semantic memory — a pure-Python TF-IDF vector store (Blueprint §6).

Semantic memory answers *what do I know that is relevant to this query*. Each document is
tokenized and represented as a sparse TF-IDF vector; ``search`` ranks stored documents by
cosine similarity to the query vector and returns the closest matches.

There are no third-party dependencies — no numpy, no external embedding service. Vectors
are plain ``dict[str, float]`` term maps and similarity is computed directly, so results
are fully deterministic and reproducible. IDF is recomputed lazily (only when the corpus
has changed since the last query), keeping repeated searches cheap.

(The hub provides a richer pgvector/Voyage store over the mesh; this is the dependency-free
default + the contract every app can rely on.)
"""

from __future__ import annotations

import math
import re
import threading
from dataclasses import dataclass, field
from typing import Any

_TOKEN_RE = re.compile(r"[a-z0-9]+")


def tokenize(text: str) -> list[str]:
    """Lowercase and split on runs of non-alphanumeric characters."""
    return _TOKEN_RE.findall(text.lower())


def _term_frequencies(tokens: list[str]) -> dict[str, float]:
    """Raw term counts for a token list."""
    tf: dict[str, float] = {}
    for tok in tokens:
        tf[tok] = tf.get(tok, 0.0) + 1.0
    return tf


@dataclass
class _Document:
    doc_id: str
    text: str
    metadata: dict[str, Any]
    term_freqs: dict[str, float] = field(default_factory=dict)


class SemanticMemory:
    """An in-memory TF-IDF document store with cosine-similarity search.

    Thread-safe via a re-entrant lock. Adding or removing documents invalidates the cached
    IDF, which is recomputed on the next search.
    """

    def __init__(self) -> None:
        self._docs: dict[str, _Document] = {}
        self._idf: dict[str, float] = {}
        self._idf_dirty = True
        self._lock = threading.RLock()

    # --- mutation ---

    def add(
        self, doc_id: str, text: str, metadata: dict[str, Any] | None = None
    ) -> None:
        """Add or replace a document. Re-adding an existing ``doc_id`` overwrites it."""
        with self._lock:
            self._docs[doc_id] = _Document(
                doc_id=doc_id,
                text=text,
                metadata=dict(metadata or {}),
                term_freqs=_term_frequencies(tokenize(text)),
            )
            self._idf_dirty = True

    def remove(self, doc_id: str) -> bool:
        """Remove a document. Returns True if it existed, False otherwise."""
        with self._lock:
            existed = self._docs.pop(doc_id, None) is not None
            if existed:
                self._idf_dirty = True
            return existed

    def __len__(self) -> int:
        with self._lock:
            return len(self._docs)

    def __contains__(self, doc_id: str) -> bool:
        with self._lock:
            return doc_id in self._docs

    # --- TF-IDF machinery ---

    def _ensure_idf(self) -> None:
        """Recompute IDF over the current corpus if it has changed."""
        if not self._idf_dirty:
            return
        n_docs = len(self._docs)
        doc_freq: dict[str, int] = {}
        for doc in self._docs.values():
            for term in doc.term_freqs:
                doc_freq[term] = doc_freq.get(term, 0) + 1
        # Smoothed IDF: ln((1 + N) / (1 + df)) + 1, always positive, deterministic.
        self._idf = {
            term: math.log((1.0 + n_docs) / (1.0 + df)) + 1.0
            for term, df in doc_freq.items()
        }
        self._idf_dirty = False

    def _tfidf_vector(self, term_freqs: dict[str, float]) -> dict[str, float]:
        """Project raw term frequencies onto the current IDF space."""
        return {
            term: tf * self._idf[term]
            for term, tf in term_freqs.items()
            if term in self._idf
        }

    @staticmethod
    def _cosine(a: dict[str, float], b: dict[str, float]) -> float:
        if not a or not b:
            return 0.0
        # Iterate the smaller vector for the dot product.
        if len(a) > len(b):
            a, b = b, a
        dot = sum(weight * b.get(term, 0.0) for term, weight in a.items())
        if dot == 0.0:
            return 0.0
        norm_a = math.sqrt(sum(w * w for w in a.values()))
        norm_b = math.sqrt(sum(w * w for w in b.values()))
        if norm_a == 0.0 or norm_b == 0.0:
            return 0.0
        return dot / (norm_a * norm_b)

    # --- query ---

    def search(
        self, query: str, k: int = 5
    ) -> list[tuple[str, float, dict[str, Any]]]:
        """Return up to ``k`` documents most similar to ``query``.

        Results are ``(doc_id, score, metadata)`` tuples sorted by descending cosine
        similarity; ties break on ``doc_id`` for determinism. Documents with zero
        similarity are excluded.
        """
        with self._lock:
            self._ensure_idf()
            query_vec = self._tfidf_vector(_term_frequencies(tokenize(query)))
            if not query_vec:
                return []
            scored: list[tuple[str, float, dict[str, Any]]] = []
            for doc in self._docs.values():
                doc_vec = self._tfidf_vector(doc.term_freqs)
                score = self._cosine(query_vec, doc_vec)
                if score > 0.0:
                    scored.append((doc.doc_id, score, dict(doc.metadata)))
            scored.sort(key=lambda item: (-item[1], item[0]))
            return scored[:k] if k is not None else scored
