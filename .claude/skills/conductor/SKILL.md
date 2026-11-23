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
0. TOOLS CHECK. The session tools are `mcp__claude-code-remote__*` (`create_session`, `get_session`, `list_events`, `send_message`, `archive_session`). If they are missing, the routine has no connectors: reply `STATUS: NEEDS-NOVAH | routine has no connectors` and stop. Do not improvise.
1. Your own state. `get_session` with no session id (your own).
   - Rate limit: read `rate_limit_info`. If `status` is not `"allowed"` or `isUsingOverage` is true, start nothing: skip steps 5 and 6, run the read-only steps, and report the limit.
   - Size: read `external_metadata.context_usage.used_tokens`. At 200k: write a handoff note (`handoff` skill), spawn a successor with `create_session` carrying that note, and ask the owner to confirm before archiving yourself. Do not archive yourself unasked. Then stop; do not run the tick.
2. Pull-first reporting. For each task with a `session_id` that is `doing`/`pr`/`review`: `list_events` (kinds `assistant`,`result`, limit 3) and read the latest `STATUS: DONE|BLOCKED|NEEDS-NOVAH|CONTINUING` line. Children also `send_message` a STATUS, but do not depend on it. If `post_turn_summary.status_detail` starts with "Waiting on permission", the session is `blocked` (it cannot report).
3. For each task in `review` with a `pr`: check the PR with the GitHub tool.
   - Merged: `python3 -m conductor.cloud mark-done <task_id> --pr <n>`. That is what lets `auto_archive` act.
   - CI red: report the PR and the failing check names. Do not start a babysit session yourself: the router decides (one small babysit session per PR, brief `TEMPLATE-babysit-brief` on the board).
4. `python3 -m conductor.cloud plan --repo-url <repo url> --revision <branch> [--brief-dir DIR]` (default `.conductor/briefs`) -> JSON `{spawns, reuses, archives, archive_candidates, handoffs, stops}`. If `<brief-dir>/<task id>.md` exists it is appended to that task's prompt under "FULL BRIEF". Starts are already claimed (`doing`), so a second tick will not repeat them.
5. For each `spawns[i]`: call `create_session` with its `create_session` object as-is (model, source_url, source_revision, tags, title, prompt). Make sure the call carries:
   - tags `lane:<LANE>`, `role:task`, `task:<id>`, `model:<m>`, and `project:<slug>` for a plan project (taxonomy in `docs/CONDUCTOR_DESIGN.md`), plus any tags the object already has;
   - title `<LANE> · <task id> <task title>` (the Claude app groups sessions by lane; the lane comes from the task, else the project default; if neither is set, ask in your reply, do not guess);
   - `extra_allowed_tools: ["mcp__claude-code-remote__send_message"]`.
   Then `python3 -m conductor.cloud start <task_id> <new session id>`.
6. For each `reuses[i]`: `send_message` to its `session_id` with its `send_message` text; no create.
7. For every task that has a `session_id` and is `doing`/`pr`/`review`: `get_session`, save the JSON to a scratch file, then `python3 -m conductor.cloud status <task_id> <file>`. This records status, `context_tokens` (from `external_metadata.context_usage.used_tokens`) and `cost_usd` (`external_metadata.usage.cost_usd`) when present; the `{"ccr": {...}}` wrapper is handled. A 0 from a session still running never overwrites a larger value.
7b. For each `handoffs[i]`: `send_message` to its `session_id` with its `send_message` text (asks for a handoff note and stop). That is the per-session soft limit, `project.per_session.soft`.
8. Archive rule (the only one). Archive only when ALL hold: (1) its PR is merged, (2) its last message says `STATUS: DONE` (or "DONE"), (3) a handoff or final report exists, (4) it is idle, not a router, not you or your parent. `archives` (only emitted when the project sets `auto_archive: true`): check 2 to 4, then `archive_session` for each that passes. A failing one, and every `archive_candidates` row, is listed in your reply, not archived. `role:scratch` sessions and routers are archived only with the owner's yes. The nightly close-out applies this same rule and skips sessions already archived.
9. `stops`: `stop_soft`/`stop_hard` are the project TOTAL budget: start nothing more, report the reason. `stop_session` (a session over `per_session.hard`) is list only: report it, never interrupt. Hard total stop: also tell the user in-flight sessions should wrap up; do not interrupt them yourself.
10. `python3 -m conductor.cloud report` and commit `.conductor/` only if the repo tracks it. Reply with started/reused/status changes/stops in a few lines. Do not run `list_sessions` here (about 100KB per call); the nightly close-out reports ungrouped sessions.

## Rules
- Model choice comes from the router (`route-and-spawn`); never override it here. Briefs follow `TEMPLATE-child-brief` via `child_brief()`.
- A `failed`/`blocked` session marks the task `blocked`; retry only by the escalation rule in `route-and-spawn`, in a new tick.
- Never force-push, never print secrets, never spawn from inside a child task session. Check your own `used_tokens` and hand off per the `handoff` skill at 200k (owner policy 2026-10-01: guard soft 300k, hard 450k).

## /board and /publish-report (view only)
- `python3 -m conductor.cloud board` writes `.conductor/board.md` from tasks.json. It never writes back to tasks or any board.
- `python3 -m conductor.cloud publish-doc` regenerates report.md and prints the arguments for the docs `batch` tool
  (`container.create` with the report as markdown). Call `batch` with that JSON as-is, then give the user the doc link. Publish only when asked or at project end.

## Adopting existing sessions (/adopt)
`list_sessions` (mine: true, save to a file), keep the rows to track, then `python3 -m conductor.cloud import <file>`. Imported tasks get ids `s-<last 8 of session id>`,
status from `status_bucket` (default `review`), and never start new work. Archive them by `mark-done` + `config --auto-archive on`. Imported tasks are marked `adopted` and do not count against `max_parallel`. Never archive without the owner's yes. Turn auto-archive on with
`python3 -m conductor.cloud config --auto-archive on`.

## Briefs
`<brief-dir>/<task id>.md` (default `.conductor/briefs/`) holds a task's full brief or design. Briefs can contain private details: a PUBLIC project repo must gitignore its briefs dir; a private repo may track it.
