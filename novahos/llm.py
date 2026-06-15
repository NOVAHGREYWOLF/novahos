"""LLM gateway over LiteLLM — shared by all agents. (Substrate.)

`reason()` = Opus-tier; `classify()` = cheap Haiku-tier. Nothing in the foundation imports
this — WARDEN stays deterministic.
"""
import json

import litellm

from .config import settings


async def reason(system: str, user: str, max_tokens: int = 2000) -> str:
    messages = [{"role": "system", "content": system}, {"role": "user", "content": user}]
    resp = await litellm.acompletion(model=settings.reasoning_model, messages=messages, max_tokens=max_tokens)
    return resp.choices[0].message.content or ""


async def classify(prompt: str) -> str:
    resp = await litellm.acompletion(model=settings.cheap_model,
                                     messages=[{"role": "user", "content": prompt}], max_tokens=400)
    return resp.choices[0].message.content or ""


def parse_json(text: str) -> dict:
    text = text.strip()
    if text.startswith("```"):
        text = text.split("```")[1].removeprefix("json").strip()
    return json.loads(text)
