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
1. Rate limit. `get_session` with no session id (your own), read `rate_limit_info`. If `status` is not `"allowed"` or `isUsingOverage` is true, start nothing: skip the babysit in step 3 and steps 5 and 6, run the read-only steps, and report the limit.
2. Pull-first reporting. For each task with a `session_id` that is `doing`/`pr`/`review`: `list_events` (kinds `assistant`,`result`, limit 3) and read the latest `STATUS: DONE|BLOCKED|NEEDS-NOVAH|CONTINUING` line. Children also `send_message` a STATUS, but do not depend on it. If `post_turn_summary.status_detail` starts with "Waiting on permission", the session is `blocked` (it cannot report).
3. For each task in `review` with a `pr`: check the PR with the GitHub tool.
   - Merged: `python3 -m conductor.cloud mark-done <task_id> --pr <n>`. That is what lets `auto_archive` act.
   - CI red: report the PR and the failing check names. Start at most ONE small babysit session per PR, per `route-and-spawn` section 5, and only if the project allows it; otherwise just report.
4. `python3 -m conductor.cloud plan --repo-url <repo url> --revision <branch>` -> JSON `{spawns, reuses, archives, archive_candidates, stops}`. Starts are already claimed (`doing`), so a second tick will not repeat them.
5. For each `spawns[i]`: call `create_session` with its `create_session` object as-is (model, source_url, source_revision, tags, title, prompt). Make sure the call carries:
   - tags `project:<slug>`, `role:task`, `task:<id>`, `model:<m>` (taxonomy in `docs/CONDUCTOR_DESIGN.md`), plus any tags the object already has;
   - `extra_allowed_tools: ["mcp__claude-code-remote__send_message"]`.
   Then `python3 -m conductor.cloud start <task_id> <new session id>`.
6. For each `reuses[i]`: `send_message` to its `session_id` with its `send_message` text; no create.
7. For every task that has a `session_id` and is `doing`/`pr`/`review`: `get_session`, save the JSON to a scratch file, then `python3 -m conductor.cloud status <task_id> <file>`. This records status, `context_tokens` (from `context_usage.used_tokens`) and `cost_usd` when present.
8. Archive rule (the only one). Archive only when ALL hold: (1) its PR is merged, (2) its last message says `STATUS: DONE` (or "DONE"), (3) a handoff or final report exists, (4) it is idle, not a router, not you or your parent. `archives` (only emitted when the project sets `auto_archive: true`): check 2 to 4, then `archive_session` for each that passes. A failing one, and every `archive_candidates` row, is listed in your reply, not archived. `role:scratch` sessions and routers are archived only with the owner's yes. The nightly close-out applies this same rule and skips sessions already archived.
9. `stops` (soft/hard budget): start nothing more, report the reason. Hard stop: also tell the user in-flight sessions should wrap up; do not interrupt them yourself.
10. Ungrouped sessions: `list_sessions` (mine: true) and list in your reply every session with no `project:` and no `role:` tag (id and title). Do not tag or archive them.
11. `python3 -m conductor.cloud report` and commit `.conductor/` only if the repo tracks it. Reply with started/reused/status changes/stops/ungrouped in a few lines.

## Rules
- Model choice comes from the router (`route-and-spawn`); never override it here. Briefs follow `TEMPLATE-child-brief` via `child_brief()`.
- A `failed`/`blocked` session marks the task `blocked`; retry only by the escalation rule in `route-and-spawn`, in a new tick.
- Never force-push, never print secrets, never spawn from inside a child task session. Check your own `used_tokens` and hand off per the `handoff` skill at 90k.

## /board and /publish-report (view only)
- `python3 -m conductor.cloud board` writes `.conductor/board.md` from tasks.json. It never writes back to tasks or any board.
- `python3 -m conductor.cloud publish-doc` regenerates report.md and prints the arguments for the docs `batch` tool
  (`container.create` with the report as markdown). Call `batch` with that JSON as-is, then give the user the doc link. Publish only when asked or at project end.

## Adopting existing sessions (/adopt)
`list_sessions` (mine: true, save to a file), keep the rows to track, then `python3 -m conductor.cloud import <file>`. Imported tasks get ids `s-<last 8 of session id>`,
status from `status_bucket` (default `review`), and never start new work. Archive them by `mark-done` + `config --auto-archive on`. Turn auto-archive on with
`python3 -m conductor.cloud config --auto-archive on`.
