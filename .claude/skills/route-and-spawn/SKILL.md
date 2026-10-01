---
name: route-and-spawn
description: Coordinator skill. Pick the cheapest safe model for a board task and start a fresh, size-limited session for it from the standard brief. Use whenever you are about to hand a task to a session, resume work after a handoff, or decide whether to reuse an idle session.
---

# route-and-spawn

For coordinators only. Goal: every task runs in a **small, fresh session on the cheapest model that is safe**.

## 1. Reuse or fresh?
Call `get_session` on the candidate. Reuse an idle session only if `context_usage.used_tokens` < 200k **and** it is the same repo and area. Otherwise start fresh. Never wake a session over 300k for new work. Keep Haiku tasks under 150k (its window is 200k).

## 2. Pick the model
```
python3 .claude/skills/route-and-spawn/route.py '{"title":"<task title>","effort":"<effort>","envelope":"<envelope>"}'
```
Returns `{"model","model_id","reason"}`. Rules: Opus for `critical`/`door` envelopes, high/xhigh effort, or security/auth/migration/architecture/rewrite in the title; Haiku for small/low mechanical work (sweeps, typos, docs, display text); Sonnet otherwise. Override by setting `model_pin` on the task, and say why on the task. If a Sonnet/Haiku session fails the same step twice, escalate one tier for the retry, not before.

## 3. Spawn
`create_session` with `model` = the returned `model_id`, the repo as `source_url`, tags `["<task id>", "model:<name>"]`, and the brief from board doc `TEMPLATE-child-brief` (fill task id, one-line goal, done-criteria). One task, one session, one PR. Prefer a task that fits in ~80k tokens; split anything larger on the board first.

## 4. Record
On the board task write `session_id`, `model`, `model_id`, `started_at`; on finish write `context_tokens` and `cost_usd` from `get_session`. Those fields are what lets us see where credits go.

## 5. Babysitting PRs
After a child opens a PR it hands off and stops. If CI goes red, start a **new small session** (Sonnet) with a two-line brief: repo, PR number, "make CI green, minimal fix, then stop". Do not wake the original session.

## 6. Every work block
Check your own `used_tokens`. At 200k write your coordinator handoff (see `handoff` skill) and start a successor.
