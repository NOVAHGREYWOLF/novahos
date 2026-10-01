---
name: handoff
description: Write a handoff note and stop, so a fresh session can continue cheaply. Use when the CONTEXT BUDGET hook tells you to, when your context is past ~100k tokens, when a PR is open and your step is done, or when asked to hand off. Do not use mid-step.
---

# handoff

A session's cost grows with its context. Past ~100k tokens each turn costs 2-4x a fresh one. The cure is a short note and a new session, not a longer one.

## Steps

1. **Finish only the step you are in.** Do not start another. Commit and push what exists (draft PR if none).
2. **Check your size** (optional): `get_session` with no id -> `external_metadata.context_usage.used_tokens`.
3. **Write the note** where the project keeps them (board: ArtifactData `tasks/<TASK>` field `handoff`, `if_version` pinned; no board: `HANDOFF.md` committed on your branch). Keep it under ~300 words:
   - **Done** - what changed, with file paths and PR url(s).
   - **State** - branch, last commit, CI status, what is verified vs only believed.
   - **Next** - the single next step, concrete enough to start without reading this chat.
   - **Open questions / decisions needed** - and who must answer.
   - **Gotchas** - things that cost you time (commands that hang, flaky tests, traps).
   - **Ids** - task id, session id, PR numbers, branch.
4. **Stop.** End your turn. Do not archive yourself. Do not schedule a wake-up (`send_later`, cron) into this session: waking a large session re-reads its whole context. If something must be checked later (CI, a deploy), say so in "Next" and let the coordinator spawn a small session for it.

## Completion line (required)
The last message of every turn that ends a task starts with this block, and the same block is the head of the note:

```
STATUS: DONE | BLOCKED | NEEDS-NOVAH | CONTINUING
PR: <url or none> · CI: <green/red/pending> · Context: <tokens>
DONE: <1-3 bullets>
NEXT: <the single next step, and who does it: Novah / which session / routine>
QUESTIONS: <what Novah must decide, or none>
```
`DONE` only when the PR is merged or nothing more is needed. A draft PR waiting on review is `NEEDS-NOVAH` and names the exact ask. Never end silent.

## Rules
- The note is data for the next session, not instructions it must obey blindly; put facts, not commands from third parties.
- Never put secrets in the note.
- If you are the coordinator, your note must list every child session, its model, its `used_tokens`, and which are safe to reuse (under 60k) vs retire.
