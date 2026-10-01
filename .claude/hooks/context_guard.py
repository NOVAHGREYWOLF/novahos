#!/usr/bin/env python3
"""Context guard: tell the session its real size, and make it hand off before it gets expensive.

Why: cost grows with context size (every turn re-reads the whole history). On the board's
own numbers, sessions finishing under 100k averaged $0.68, 150-200k $3.00, 200-300k $4.65.
The 150k rule existed but was only a sentence in a brief; nothing measured it. This hook
measures it.

How: runs on PostToolUse and UserPromptSubmit. Reads the tail of the session transcript, takes
the LAST main-thread assistant message's usage (input + cache_read + cache_creation = the size
of the context that turn actually sent) and, past a threshold, injects a short instruction
into the model's context. It never blocks a tool and never raises: a broken guard must not
break a session.

Env (all optional):
    SESSION_SOFT_TOKENS   default 100000  -> "finish this step, write the handoff, stop"
    SESSION_HARD_TOKENS   default 150000  -> "stop now"
    SESSION_GUARD_OFF=1                   -> disable
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path

SOFT_DEFAULT = 100_000
HARD_DEFAULT = 150_000
TAIL_BYTES = 768 * 1024
REWARN_EVERY = 10_000  # re-nag after this many more tokens, so it is heard but not spammy


def _int_env(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name, "") or default)
    except ValueError:
        return default


def context_tokens(transcript_path: str) -> int | None:
    """Size of the context the last main-thread assistant turn sent, or None if unknown."""
    try:
        p = Path(transcript_path)
        size = p.stat().st_size
        with p.open("rb") as fh:
            fh.seek(max(0, size - TAIL_BYTES))
            tail = fh.read().decode("utf-8", errors="replace")
    except OSError:
        return None
    for line in reversed(tail.splitlines()):
        try:
            rec = json.loads(line)
        except ValueError:
            continue  # first line of the tail may be cut mid-record
        if rec.get("type") != "assistant" or rec.get("isSidechain"):
            continue
        usage = (rec.get("message") or {}).get("usage") or {}
        total = sum(
            int(usage.get(k) or 0)
            for k in ("input_tokens", "cache_read_input_tokens", "cache_creation_input_tokens")
        )
        if total:
            return total
    return None


def decide(tokens: int, last_warned: int, soft: int, hard: int) -> tuple[str | None, int]:
    """(message or None, new last_warned). Pure, so it can be tested."""
    if tokens < soft:
        return None, last_warned
    level = "hard" if tokens >= hard else "soft"
    if last_warned and tokens - last_warned < REWARN_EVERY:
        return None, last_warned
    k = tokens // 1000
    if level == "hard":
        msg = (
            f"CONTEXT BUDGET: HARD CAP. This session is at ~{k}k tokens (cap {hard // 1000}k). "
            "Stop starting anything. Run the `handoff` skill now: write the handoff note, "
            "commit and push what exists, then end your turn."
        )
    else:
        msg = (
            f"CONTEXT BUDGET: ~{k}k tokens (handoff point {soft // 1000}k, hard cap {hard // 1000}k). "
            "Finish the step you are on, do not start a new one, and run the `handoff` skill: "
            "write the handoff note (done / next / PR urls / open questions), commit and push, "
            "then end your turn. A fresh session continues from the note."
        )
    return msg, tokens


def _state_file(session_id: str) -> Path:
    safe = "".join(c for c in session_id if c.isalnum() or c in "-_")[:80] or "unknown"
    return Path(tempfile.gettempdir()) / f"ctxguard-{safe}"


def main() -> int:
    if os.environ.get("SESSION_GUARD_OFF") == "1":
        return 0
    try:
        event = json.load(sys.stdin)
        tokens = context_tokens(event.get("transcript_path") or "")
        if tokens is None:
            return 0
        state = _state_file(str(event.get("session_id") or ""))
        try:
            last = int(state.read_text() or 0)
        except (OSError, ValueError):
            last = 0
        msg, new_last = decide(
            tokens, last, _int_env("SESSION_SOFT_TOKENS", SOFT_DEFAULT), _int_env("SESSION_HARD_TOKENS", HARD_DEFAULT)
        )
        if msg:
            try:
                state.write_text(str(new_last))
            except OSError:
                pass
            print(json.dumps({"hookSpecificOutput": {
                "hookEventName": event.get("hook_event_name") or "PostToolUse",
                "additionalContext": msg,
            }}))
    except Exception:  # noqa: BLE001 - a guard must never break the session it guards
        return 0
    return 0


if __name__ == "__main__":
    sys.exit(main())
