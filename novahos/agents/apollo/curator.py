"""CURATOR (APOLLO) — shared draft selector. Context-driven. (Agents.)

Ranks WORDSMITH variants toward ctx.goal/playbook success metric, annotates them, marks the
winner chosen. Phase 1: its LLM ranking is the selector; Phase 2: it becomes the bandit prior.
"""
from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from ... import llm
from ...context import AgentContext
from ...models import ContentDraft


async def curate(db: AsyncSession, ctx: AgentContext, *, drafts: list[ContentDraft]) -> ContentDraft:
    if not drafts:
        raise ValueError("no drafts to curate")
    pb = ctx.playbook or {}

    if len(drafts) == 1:
        drafts[0].curator_rank = 1
        drafts[0].curator_reason = "only variant"
        drafts[0].chosen = True
        await db.flush()
        return drafts[0]

    listing = "\n".join(f"[{i}] lens={d.lens_key} | body={(d.body or '')[:200]}" for i, d in enumerate(drafts))
    system = ("You are CURATOR. Pick the variant most likely to advance the goal "
              f"'{pb.get('goal_type')}' (success metric: {pb.get('success_metric')}) on "
              f"{ctx.channel}. Return ONLY JSON.")
    prompt = (f"VARIANTS:\n{listing}\n\n"
              'Return JSON: {"ranking": [indices best→worst], "reason": "why the top one wins"}')

    chosen_idx, reason = 0, "default"
    try:
        data = llm.parse_json(await llm.reason(system, prompt))
        ranking = data.get("ranking") or [0]
        chosen_idx = int(ranking[0])
        reason = data.get("reason", "")
        for rank, idx in enumerate(ranking, start=1):
            if 0 <= int(idx) < len(drafts):
                drafts[int(idx)].curator_rank = rank
    except Exception:
        drafts[0].curator_rank = 1

    chosen_idx = chosen_idx if 0 <= chosen_idx < len(drafts) else 0
    winner = drafts[chosen_idx]
    winner.curator_reason = reason
    winner.chosen = True
    await db.flush()
    return winner
