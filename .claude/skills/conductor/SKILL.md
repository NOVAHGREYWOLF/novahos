---
name: conductor
description: Cloud conductor. Drive one tick of a project plan (.conductor/project.json + tasks.json) by starting, reading and recording Claude Code sessions instead of local worktrees. Use for /tick, /project-start, or when the scheduled conductor routine fires.
---

# conductor (cloud runner)

Same `tick()` logic as the local runner (`conductor/runner.py`); sessions replace worktrees. The deterministic part is
`python3 -m conductor.cloud`, which prints JSON. You only make the session calls it asks for and record the results.
No polling, no wake-ups, no PR subscriptions: one tick = one pass, then stop.

## /project-start
1. Confirm `.conductor/project.json` and `.conductor/tasks.json` exist and validate (`python3 -m conductor.cloud --dir .conductor report`). If missing, stop and ask for the plan; do not invent tasks.
2. Run the tick below once.

## /tick
1. `python3 -m conductor.cloud plan --repo-url <repo url> --revision <branch>` -> JSON `{spawns, reuses, archives, archive_candidates, stops}`. Starts are already claimed (`doing`), so a second tick will not repeat them.
2. For each `spawns[i]`: call `create_session` with its `create_session` object as-is (model, source_url, source_revision, tags, title, prompt). Then `python3 -m conductor.cloud start <task_id> <new session id>`.
3. For each `reuses[i]`: `send_message` to its `session_id` with its `send_message` text; no create.
4. For every task that has a `session_id` and is `doing`/`pr`/`review`: `get_session`, save the JSON to a scratch file, then `python3 -m conductor.cloud status <task_id> <file>`. This records status, `context_tokens` (from `context_usage.used_tokens`) and `cost_usd` when present.
5. `archives` (only emitted when the project sets `auto_archive: true`): `archive_session` for each. `archive_candidates`: list them in your reply, do not archive.
6. `stops` (soft/hard budget): start nothing more, report the reason. Hard stop: also tell the user in-flight sessions should wrap up; do not interrupt them yourself.
7. `python3 -m conductor.cloud report` and commit `.conductor/` only if the repo tracks it. Reply with started/reused/status changes/stops in five lines or fewer.

## Rules
- Model choice comes from the router (`route-and-spawn`); never override it here. Briefs follow `TEMPLATE-child-brief` via `child_brief()`.
- A `failed`/`blocked` session marks the task `blocked`; retry only by the escalation rule in `route-and-spawn`, in a new tick.
- Never force-push, never print secrets, never spawn from inside a child task session. Check your own `used_tokens` and hand off per the `handoff` skill at 90k.

## /board and /publish-report (view only)
- `python3 -m conductor.cloud board` writes `.conductor/board.md` from tasks.json. It never writes back to tasks or any board.
- `python3 -m conductor.cloud publish-doc` regenerates report.md and prints the arguments for the docs `batch` tool
  (`container.create` with the report as markdown). Call `batch` with that JSON as-is, then give the user the doc link. Publish only when asked or at project end.
