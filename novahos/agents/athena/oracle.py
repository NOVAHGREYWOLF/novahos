"""ORACLE (ATHENA) — mine journal/check-in signals for content angles. Pure suggestion. (Agents.)"""
from __future__ import annotations

from ... import llm, suite

_SYSTEM = ("You are ORACLE. Turn a person's recent journal/check-in notes into 3-5 specific, "
           "non-generic content angles that fit their voice. Return ONLY JSON.")


async def content_angles(account_email: str, since: str | None = None) -> list[str]:
    signals = suite.get_journal_signals(account_email, since)
    if not signals:
        return []
    notes = signals.get("text") if isinstance(signals, dict) else str(signals)
    prompt = (f"RECENT NOTES:\n{str(notes)[:3000]}\n\n"
              'Return JSON: {"angles": ["angle 1", "angle 2", ...]}')
    try:
        return list(llm.parse_json(await llm.reason(_SYSTEM, prompt)).get("angles", []))
    except Exception:
        return []
