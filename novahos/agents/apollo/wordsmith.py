"""WORDSMITH (APOLLO) — shared copywriter. Context-driven. (Agents.)

The same agent writes an Instagram caption, a LinkedIn post, or an email body — ctx.channel +
ctx.playbook + ctx.lenses + ctx.voice decide the output. One draft VARIANT per lens (each a
bandit arm). LLM reasoning lives here, never in WARDEN.

Two entry points:
  - `compose(ctx, transcript)` → list[dict]  — PURE (no DB). The shared composition brain, usable
     by any app regardless of its database (NovaHound stores results in its own `posts`; the IG app
     persists via `generate`).
  - `generate(db, ctx, ...)` → list[ContentDraft] — composes then persists to the kernel's models.
"""
from __future__ import annotations

from ... import llm
from ...constitution import mission_clause
from ...context import AgentContext

# NOTE: `compose()` is pure (LLM + context only) and imports nothing heavy, so any app can call it
# without SQLAlchemy. The DB-backed `generate()` imports the models lazily, when actually used.

_SYSTEM = (
    mission_clause()
    + "\nYou are WORDSMITH, an expert social copywriter. Write in the account's voice — honest "
    "and specific, never hype or fabricated claims. Adapt format to the channel. Return ONLY JSON."
)


def _prompt(ctx: AgentContext, transcript: str, lens: dict, summary: str | None) -> str:
    pb = ctx.playbook or {}
    hs = pb.get("hashtag_strategy", {})
    cta = pb.get("cta", {})
    voice = ctx.voice or {}
    return (
        f"CHANNEL: {ctx.channel}\n"
        f"TRANSCRIPT:\n{transcript[:4000]}\n\n"
        f"SUMMARY: {summary or '(none)'}\n"
        f"BRAND VOICE: {voice.get('description', 'natural, authentic')}\n\n"
        f"PLAYBOOK GOAL: {pb.get('goal_type')} (success metric: {pb.get('success_metric')})\n"
        f"CAPTION DIRECTIVE: {pb.get('prompt', {}).get('caption_directive', '')}\n"
        f"CTA STYLE: {cta.get('style')}; templates: {cta.get('templates')}\n"
        f"LENS: {lens.get('key')} — tone: {lens.get('tone')}; structure: {lens.get('structure')}\n"
        f"TAGS: produce {hs.get('count', 8)} (mix {hs.get('mix')}); never use {hs.get('banned')}\n\n"
        "Return JSON: {\n"
        '  "body": "the post body in the lens tone, channel-appropriate length",\n'
        f'  "hooks": [{pb.get("prompt", {}).get("hook_count", 3)} alternative 1-line opening hooks],\n'
        '  "tags": ["#tag or keyword", ...],\n'
        '  "cta": "the single call to action"\n'
        "}"
    )


def _fallback(transcript: str) -> dict:
    head = (transcript or "").strip().split(".")[0][:120]
    return {"body": head or "New drop.", "hooks": [head or "Watch this"], "tags": [], "cta": ""}


async def compose(ctx: AgentContext, transcript: str, summary: str | None = None) -> list[dict]:
    """Pure composition — one draft dict per lens. No DB. Returns
    [{variant_key, lens_key, body, hooks, tags, cta}, ...]."""
    lenses = ctx.lenses or {"educational": {"key": "educational"}}
    out: list[dict] = []
    for lens_key, lens in lenses.items():
        try:
            data = llm.parse_json(await llm.reason(_SYSTEM, _prompt(ctx, transcript, lens, summary)))
        except Exception:
            data = _fallback(transcript)
        out.append({
            "variant_key": f"lens:{lens_key}", "lens_key": lens_key,
            "body": data.get("body", ""), "hooks": data.get("hooks", []),
            "tags": data.get("tags", []), "cta": data.get("cta", ""),
        })
    return out


async def generate(db, ctx: AgentContext, *, content_piece_id: str,
                   transcript: str, summary: str | None = None) -> list:
    """Compose, then persist one ContentDraft per variant to the kernel's models."""
    from ...models import ContentDraft  # lazy — only the DB path needs SQLAlchemy

    drafts = []
    for d in await compose(ctx, transcript, summary):
        draft = ContentDraft(
            user_id=ctx.user_id, content_piece_id=content_piece_id, variant_key=d["variant_key"],
            body=d["body"], hooks=d["hooks"], tags=d["tags"], cta=d["cta"], lens_key=d["lens_key"],
        )
        db.add(draft)
        drafts.append(draft)
    await db.flush()
    return drafts
