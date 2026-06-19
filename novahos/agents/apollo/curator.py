"""CURATOR (APOLLO) — shared draft selector. Context-driven. (Agents.)

Ranks WORDSMITH variants toward ctx.goal/playbook success metric.

  - `rank_dicts(ctx, drafts)` → {index, ranking, reason} — PURE (no DB). The shared ranking brain.
  - `curate(db, ctx, drafts)` → ContentDraft — ranks ORM drafts, annotates + marks the winner.
"""
from __future__ import annotations

from ... import llm
from ...context import AgentContext

# `rank_dicts()` is pure (LLM + context only). `curate()` operates on ORM draft objects passed in
# by the caller — it imports nothing heavy itself.


async def rank_dicts(ctx: AgentContext, drafts: list[dict]) -> dict:
    """Pick the best variant from plain draft dicts (each needs `lens_key` + `body`). No DB.
    Returns {"index": int, "ranking": list[int], "reason": str}."""
    if not drafts:
        raise ValueError("no drafts to rank")
    if len(drafts) == 1:
        return {"index": 0, "ranking": [0], "reason": "only variant"}
    pb = ctx.playbook or {}
    listing = "\n".join(f"[{i}] lens={d.get('lens_key')} | body={(d.get('body') or '')[:200]}"
                        for i, d in enumerate(drafts))
    system = ("You are CURATOR. Pick the variant most likely to advance the goal "
              f"'{pb.get('goal_type')}' (success metric: {pb.get('success_metric')}) on "
              f"{ctx.channel}. Return ONLY JSON.")
    prompt = (f"VARIANTS:\n{listing}\n\n"
              'Return JSON: {"ranking": [indices best→worst], "reason": "why the top one wins"}')
    try:
        data = llm.parse_json(await llm.reason(system, prompt))
        ranking = [int(i) for i in (data.get("ranking") or [0]) if 0 <= int(i) < len(drafts)]
        idx = ranking[0] if ranking else 0
        return {"index": idx, "ranking": ranking or [0], "reason": data.get("reason", "")}
    except Exception:
        return {"index": 0, "ranking": [0], "reason": "default"}


async def curate(db, ctx: AgentContext, *, drafts: list):
    if not drafts:
        raise ValueError("no drafts to curate")
    decision = await rank_dicts(ctx, [{"lens_key": d.lens_key, "body": d.body} for d in drafts])
    for rank, idx in enumerate(decision["ranking"], start=1):
        if 0 <= idx < len(drafts):
            drafts[idx].curator_rank = rank
    winner = drafts[decision["index"]]
    if winner.curator_rank is None:
        winner.curator_rank = 1
    winner.curator_reason = decision["reason"]
    winner.chosen = True
    await db.flush()
    return winner
