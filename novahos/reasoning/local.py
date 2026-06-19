"""A deterministic, offline reasoning provider — the zero-config default.

This is a *placeholder* for real reasoning: it does no network I/O and runs the same way on
every machine, so NovahOS boots and its agents "reason" with no API key and no model server.
It produces a structured extractive summary of the prompt (key sentences as bullets) which
is useful-ish for smoke tests and demos, and — crucially — fully deterministic so the test
suite can assert exact output.

A litellm/cloud-backed provider (consistent with `novahos.llm`) can be slotted into
`get_provider()` later without changing anything here.
"""

from __future__ import annotations

import re
from typing import Any

from .provider import ReasoningResult

MODEL_NAME = "local-deterministic"

# Split on sentence-ending punctuation followed by whitespace. Deterministic and stdlib-only.
_SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+")


def _sentences(text: str) -> list[str]:
    """Break `text` into trimmed, non-empty sentences in original order."""
    parts = _SENTENCE_SPLIT.split(text.strip())
    return [p.strip() for p in parts if p.strip()]


class LocalReasoningProvider:
    """Deterministic extractive-summary provider. No network, no randomness.

    The "reasoning" is a transparent stub: it echoes the leading sentences of the prompt as a
    bulleted summary, optionally prefixed with the system framing. Identical input always
    yields identical output.
    """

    model = MODEL_NAME

    def __init__(self, *, max_bullets: int = 5) -> None:
        self.max_bullets = max_bullets

    def complete(
        self,
        prompt: str,
        *,
        system: str | None = None,
        max_tokens: int = 1024,
        **kw: Any,
    ) -> ReasoningResult:
        sentences = _sentences(prompt)
        # Cap the number of bullets; respect max_tokens loosely as a sentence budget too.
        limit = max(1, min(self.max_bullets, max_tokens))
        selected = sentences[:limit]

        lines: list[str] = []
        if system:
            lines.append(f"[system] {system.strip()}")
        if selected:
            lines.append("Summary:")
            lines.extend(f"- {s}" for s in selected)
        else:
            lines.append("Summary: (no content to summarize)")

        text = "\n".join(lines)
        meta = {
            "provider": "local",
            "sentence_count": len(sentences),
            "bullets": len(selected),
            "deterministic": True,
        }
        return ReasoningResult(text=text, model=self.model, meta=meta)
