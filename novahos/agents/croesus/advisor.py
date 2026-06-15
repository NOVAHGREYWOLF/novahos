"""CROESUS advisor — turn a financial snapshot into an honest read + recommendations. (Agents.)

Shared across apps (Lucid's finance coaching today; any future money app tomorrow). Operates on
a snapshot the APP assembles from its own data (finance is PRIVATE-tier → stays local; the app
passes a compact summary, not raw third-party dumps). Per the Constitution + the money-is-hands-off
rule, CROESUS is **analysis only** — it never moves money or proposes initiating a transaction.
Fail-quiet: returns {} if the snapshot is empty or the model is unavailable.
"""
from __future__ import annotations

import json

_SYSTEM = (
    "You are CROESUS, a blunt, practical finance coach. Given a person's financial snapshot, "
    "give an honest read: overall financial health, the top risks, and 2-3 concrete, high-leverage "
    "recommendations. You NEVER move money, initiate transfers/payments/trades, or tell the user to "
    "let software do so — analysis and recommendations the human acts on, only. Return ONLY JSON."
)


async def assess(snapshot: dict) -> dict:
    """snapshot e.g. {balances, recent_transactions, debts, income, monthly_burn}.

    Returns {"health","risks":[...],"recommendations":[...],"one_move"}.
    """
    if not snapshot:
        return {}
    from ... import llm  # lazy: keep the agent import-light (no litellm needed to import)
    prompt = (
        f"FINANCIAL SNAPSHOT:\n{json.dumps(snapshot, default=str)[:3000]}\n\n"
        'Return JSON: {"health":"surviving|tight|stable|strong",'
        '"risks":["..."],"recommendations":["..."],'
        '"one_move":"the single highest-leverage money action this week (the human does it)"}'
    )
    try:
        return llm.parse_json(await llm.reason(_SYSTEM, prompt))
    except Exception:
        return {}
