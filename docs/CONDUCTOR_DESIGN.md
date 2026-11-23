# Conductor: start a project, it keeps costs down by itself

Status: design + handoff (written 2026-10-01). Builds on the merged session-budget kit (#24).

## Goal
`project start` -> plan -> small fresh sessions on the cheapest safe model -> grouped by project ->
archived when done -> a project document always written. Works in cloud sessions AND locally.

## The one rule that makes "both" work
The **plan lives in git**: `.conductor/` in the project repo. Cloud and local runners read/write the
same files, so they never disagree. The board (ArtifactData) is a *view* synced from it, not the source.

```
.conductor/
  project.json     name, slug, goal, auto_archive (default false), budget {soft:100000, hard:150000}
  tasks.json       [{id, title, effort, envelope, depends[], model, status, session_id, pr, cost_usd, context_tokens}]
  handoffs/<task>.md   the handoff note per task (see the `handoff` skill)
  report.md        living project doc, regenerated every tick; final report on completion
```

## Shared core (stdlib python, `conductor/`)
- `plan.py`     schema + validation + "which tasks are ready" (deps done, not started)
- `route.py`    reuse `.claude/skills/route-and-spawn/route.py`
- `briefs.py`   child / babysit brief templates (from board docs TEMPLATE-child-brief, TEMPLATE-babysit-brief)
- `report.py`   tasks.json -> report.md (goal, tasks, PRs, cost by task and model, decisions, lessons, open items)
- `tick()`      pure function: state in -> list of actions out. Runners only *execute* actions.

## Two thin runners
| | Cloud runner | Local runner |
|---|---|---|
| Executes | `create_session` (model, source_url, tags), `get_session`, `archive_session` | `claude -p --model X --max-turns N --output-format json` in a git worktree per task |
| Triggered by | scheduled routine + `/tick`; a fresh Sonnet/Haiku session per tick (~20-30k tokens), never a long-lived coordinator | `conductor run` loop or cron |
| Cost data | `get_session` usage | JSON `usage`/`total_cost_usd` from `claude -p` |
| Size guard | context_guard hook + `get_session` | fresh process per task + `--max-turns`; hook still active |
| Tags | `project:<slug>`, `task:<id>`, `model:<m>` | same, written to tasks.json |

## Behaviours (both runners)
1. **Start**: `/project-start` interviews briefly, writes `.conductor/*`, creates tasks with effort/envelope, routes models.
2. **Each tick**: sync -> pick ready tasks (parallel up to a cap) -> spawn fresh session per task -> record cost/context -> red CI gets a small babysit session -> regenerate `report.md` -> exit.
3. **Archive**: when a task is merged AND its handoff exists, archive its session only if `auto_archive` is true (the standing rule is "never archive without Novah's yes"); otherwise list candidates in the report.
4. **Document always**: `report.md` every tick; on the last tick also publish it via the docs tool and link it from the project.
5. **Every session knows the rules**: ship as one kit (hook + handoff + route-and-spawn + conductor skills) via `scripts/install_session_budget.sh`, ideally as a plugin (unverified whether cloud sessions accept account-level plugins).

## Build order (each step is its own small session, Sonnet unless noted)
1. `conductor/plan.py` + `route.py` import + tests (pure, no network).  
2. `report.py` + tests (golden file).  
3. `tick()` pure function + tests (ready-task selection, reuse vs fresh, archive policy, budget stop).  
4. Local runner (`claude -p` executor, worktrees, cost capture). Smoke test on a toy repo.  
5. Cloud runner as a skill (`/tick`, `/project-start`) calling create/get/archive; one scheduled routine.  
6. Board sync (view only) + docs publish for the final report. Opus only for step 3 design review.

## Known gaps / decisions
- Account-level plugin install for cloud sessions: unverified.
- Haiku routing untested on real tasks; backtest sends none of 49 past tasks to Haiku.
- Hook behaviour in `create_session` sessions: unverified.
- The install of the kit into the other repos is blocked on `add_repo` permission (session_013enoai3KJ3s6X4ZKUcHpW3).
- Weekly limit reset: 2026-10-03 21:00 UTC; ticks must stay on Sonnet/Haiku.

## Handoff (from the design session)
Done: session-budget kit merged (#24); board has RULE-session-budget, TEMPLATE-child-brief, TEMPLATE-babysit-brief.
Next: build step 1 above in a fresh session reading this file. Ids: novahos main, board A4uS9xn1emqupohdE4DUfV.

## Handoff (build step 1)
Done: `conductor/plan.py` (+ `__init__.py`) and `tests/test_conductor_plan.py` (16 tests pass). Draft PR stacked on #25
(base `claude/conductor-design`). Stdlib only; `route.py` is loaded by path, rules not duplicated.
`conductor/` is NOT in `[tool.setuptools.packages.find] include` (novahos*, leadfuel_core*), so it does not ship in the
installed package and cannot affect the `bare import` job; the test inserts the repo root on `sys.path`.
Next: step 2, `conductor/report.py` (tasks.json -> report.md) + golden-file test, reading `plan.Task`/`plan.Project`.
Gotchas:
- `Task.model` holds the router's short name (`opus|sonnet|haiku`), not the full model id; `model_pin` is an extra optional
  field (pin wins even when `model` is already set). Unknown task fields are rejected.
- `ready_tasks` counts doing/pr/review tasks against `max_parallel`.
- Valid envelopes: standard, production, critical, door; efforts: small, low, medium, high, xhigh.
- `pip install pytest` may be needed in a fresh cloud session (not preinstalled).

## Reports program link
Written 2026-10-01 by a read-only coordination session. Sources: `get_session`/`list_events` on the four sessions below and
`get_trigger` on the nightly routine. No session was messaged, interrupted or archived. Session snapshots are from
2026-09-30 (last activity) unless noted, so re-check status before acting. Related: #25 (design), #26 (build step 1).

### Who owns the command book
The briefing/command book ("Your command book · <date>", from NovahPrime, ~12:10 UTC) is built in
**NOVAHGREYWOLF/novahub**, in `command_book.py` (`compose` builds a `book` dict; `book['needs_you']` is rendered to HTML and
plain text). All four sessions were created on novahub. It is fed by modules that `compose` calls fail-soft
(e.g. `relevance_questions(owner)`, `mail_auto_archive.recent_auto_archives(owner, hours=48)`). Decision A in that program:
**one email**. The leadfuel repos are out of scope for this repo/session; any wiring below is a novahub change.

### The four sessions
| Session | What | Status (snapshot) |
|---|---|---|
| `session_013KaA5oWtyQXtWULYd32wx7` | "LeadFuel Reports program" coordinator (Sonnet, parent of P5-F4). Runs one board task at a time; board = ArtifactData collection `tasks`. | Idle, ~113k ctx. Waiting on Novah: 6 open questions (R14 email vs briefing only; `SPOKE_PULL`/`SPOKE_SUBMIT_AUTHORITY`; `LOCAL_ZONE_STALE_HOURS=12`; P9 PDF lib + P8 DMARC rua; pin `tzfpy`; accept CI as the full-suite check), OK to archive two old sessions, and a decision on leadfuel-core PR #2 (stale `docs/REPORTS_PLAN.md`). Next: P5-F1 re-check, then P6. |
| `session_01YRqpKWgtn1FCn1RkWoyMpN` | P5 "Prime digests all spokes, infers, shows time windows and what is missing". | Archived. Opened novahub PR #683 (`claude/p5-prime-digest`). Transcript not read in detail; whether #683 merged is **unverified** (the coordinator calls a separate session "the stray #683 merge session"). |
| `session_01AqEe6LghcvzuWQHGmvaSFs` | P5-F2: wire R14 `relevance_questions(owner)` into the briefing as NEEDS YOU. | Done. PR #691 merged by Novah 2026-09-30, CI green. Session idle; archive awaits Novah's OK. |
| `session_01E4SGoX7VSuJHKATRrcVsde` | P5-F4: "auto-archived N messages" line in the briefing. | Draft PR #692 open. pytest + pip-audit passed; the `gates` check was cancelled and one re-run was queued. Needs: gates green, Novah merge. Known gap: no undo route exists yet, the "Undo" link points at the list route `GET /api/inbound/manage/auto-archives?hours=48`. |

### Overlap with the nightly routine (`trig_01U9CpzgkUWKbLeymJ46qmuA`, 03:07 UTC)
- **Archive is not actually duplicated.** P5-F4's "auto-archive" is about **email messages** archived by
  `mail_auto_archive` (novahub #684); it only *reports* them in the briefing. Routine step 2 archives **conductor
  sessions** (Claude sessions) under strict eligibility. Different objects, same word. Recommendation: the **routine owns
  session archiving** (it is the only thing with the eligibility rules and Novah's explicit approval); **P5-F4/novahub
  owns the mail-archive line**. Rename the briefing line to "Mail auto-archived ..." to prevent confusion, and never let the
  briefing archive sessions.
- **Real overlap is the end-of-day report vs the briefing.** Both summarise "what happened / what needs you". The routine
  writes `docs/reports/YYYY-MM-DD.md` (intent, done, worked, didn't, budget/spend, tasks/goals, archived, next, open
  questions) to a draft PR that nobody reads by email. The briefing is the thing Novah reads daily. Keep one source of
  truth per fact: the report is the record, the briefing shows a short digest plus a link.
- Possible duplicate work: the coordinator's "archive two old sessions, ask Novah" step and the nightly routine's step 2.
  Those two sessions are not tagged `conductor`, so the routine will skip them; they stay a manual Novah decision.
- Session-budget numbers: report data (cost, context) comes from `get_session` in both places; do not build a second collector.

### Where the nightly report plugs into the command book
| Option | How | Pros | Cons / unverified |
|---|---|---|---|
| A. Brain document | Routine stores the report (short form) in the Novah brain (`store_document`); `command_book.compose` reads the latest one and adds a CONDUCTOR section | One email (decision A); report searchable by NovahPrime; no cross-repo file reads at runtime | Unverified: that `compose` can read brain documents internally; the routine currently has **no connectors** (`mcp_connections: []`), so it could not call the brain tool today |
| B. Separate email | Routine mails the report | Trivial, no novahub change | Breaks "one email"; needs a mail connector; Novah asked for it in the command book |
| C. File the generator reads | Briefing generator fetches `docs/reports/latest.md` from novahos on GitHub | No brain write | Railway-deployed novahub needs a GitHub token for novahos at runtime; PR is a draft on a side branch, so "latest" is not on main |

**Recommendation: A.** Routine step 5 (new): store a ≤1.5k-char digest + link to the report PR as a brain document tagged
`conductor_report`, date-keyed. novahub `compose` adds a fail-soft, quiet-when-absent CONDUCTOR block (HTML + text) with:
done today, what didn't, spend vs budget, tasks/goals completed, next, and anything needing Novah, following the P5-F2/F4
pattern (#691/#692). Fall back to C only if A cannot be done. Do not use B.

Unverified: (1) brain tool/connector availability inside the routine's fresh sessions; (2) the document API available to
`command_book.py`; (3) how `compose` is scheduled relative to the 03:07 UTC report (the 12:10 UTC briefing is later, so a
same-day report is available); (4) whether #683 merged; (5) final status of #692 gates.

### Next steps for the owning repo (novahub; nothing here was done by this session)
1. Merge #692 once `gates` is green; add an undo route or relabel the link; rename the line to "Mail auto-archived".
2. Decide A vs C with Novah (open question below). If A: confirm `compose` can read a brain document by tag.
3. novahub: add a CONDUCTOR block in `command_book.compose` + HTML/text renderers + tests beside
   `tests/test_command_book_auto_archives.py` (fail-soft, quiet when no report or report older than 36h).
4. novahos: after step 2 of the conductor build order ships `report.py`, add a `digest()` that emits the short form; update
   the routine (Novah's call) to add the connector and the store step. Not changed here.
5. Resolve the Reports coordinator's pending asks (6 questions, two session archives, leadfuel-core PR #2) so the program has one
   open owner.

### Decisions (Novah, 2026-10-01)
- **Wiring: option A (brain document), option C (GitHub file read) as backup** if A cannot be done (e.g. the routine cannot get the brain connector, or `compose` cannot read brain documents).
- **Routine step 2 stays limited to `conductor`-tagged sessions.** The two Reports sessions are Novah's manual decision.
- **Briefing shows both**: the full report is stored/available, and the CONDUCTOR block shows a digest plus link.
- Still requires Novah to add the brain connector to the routine; not changed here.

### Session completion contract (Novah, 2026-10-01)
Every conductor/Reports session must say when it is done, or what comes next. No silent idle.
The **last message of every turn that ends a task** starts with one status line, then the next steps:

```
STATUS: DONE | BLOCKED | NEEDS-NOVAH | CONTINUING
PR: <url or none> · CI: <green/red/pending> · Context: <tokens>
DONE: <1-3 bullets>
NEXT: <the single next step, who does it (Novah / which session / routine)>
QUESTIONS: <only what Novah must decide, or none>
```
Rules: DONE only when the PR is merged or the task needs nothing more; a draft PR waiting on review is `NEEDS-NOVAH` with
the exact ask. The same block is written to the task's handoff note (`.conductor/handoffs/<task>.md` or the board task) so a
fresh session and the nightly report can read it without the transcript. The block is now in the `handoff` and `route-and-spawn` skills. The board docs `TEMPLATE-child-brief`/`TEMPLATE-babysit-brief` live on the board, outside this repo: they still need the same block added (not changed here). The nightly report should list any session whose last message has no
STATUS line as "no completion note" (proposed addition to the routine; Novah's call, routine not changed here).

## Handoff (build step 2)
Done: `conductor/report.py` (`render(project, tasks, decisions=(), lessons=(), open_items=())`, `write_report(path, ...)`) and
`tests/test_conductor_report.py` with golden `tests/fixtures/conductor_report.md` (empty, all statuses, over soft/hard budget,
auto_archive on/off). Stdlib only, no timestamps. Draft PR stacked on #26 (base `claude/conductor-plan`); retarget to main once #26 merges.
Next: step 3, `tick()` pure function + tests (ready-task selection via `plan.ready_tasks`, reuse vs fresh session, archive policy, budget stop).
Gotchas:
- `Budget.soft/hard` are compared with the sum of `Task.context_tokens` (tokens); `cost_usd` is reported but not budgeted. Tick's budget stop should use the same measure.
- Archive candidates = `done` + `session_id`; with `auto_archive` false they are listed only. `tick()` should reuse that rule, not redo it.
- Blocked tasks are auto-added to "Open items"; tasks without a model group under `unassigned`.
- Regenerate the golden by deleting the fixture and running the test once (it writes it when missing); review the diff.
- Cost numbers use `$x,xxx.xx` and tokens `x,xxx`; changing formats means regenerating the golden.

## Handoff (build step 3)
Done: `conductor/tick.py` (`State(project, tasks, max_parallel=3)`, frozen `Action(kind, task_id, session_id, reason)`,
`tick(state) -> list[Action]`, helpers `archive_candidates`, `budget_level`) and `tests/test_conductor_tick.py` (7 tests; 28 pass with plan/report).
Pure, stdlib only, no I/O or clock. Draft PR stacked on #27 (base `claude/conductor-report`); retarget as #25/#26/#27 merge.
Action kinds, in order: `stop_soft|stop_hard`, then `archive` (only if `auto_archive` true) or `archive_candidate` (list only), then `start_reuse|start_fresh`.
Rules: reuse = task has `session_id` and `context_tokens` < 60,000, else fresh; soft budget (sum of context_tokens > soft) blocks new starts, hard blocks them too and is reported as `stop_hard` (runner should also halt in-flight work); exactly at the limit is not exceeded (same as report.py).
Next: step 4, local runner: `claude -p --model X --max-turns N --output-format json` executor, git worktree per task, capture `total_cost_usd`/usage into `cost_usd`/`context_tokens`, apply tick actions, write tasks.json + report.md. Smoke test on a toy repo (no network in unit tests: inject the executor).
Gotchas:
- `start_reuse` for a `todo` task assumes a prior session exists; the runner decides how to resume it (`claude -p --resume` locally).
- `tick` does not mutate tasks or set `doing`; the runner must record starts itself or the next tick will re-select them.
- `ready_tasks` caps by max_parallel minus in-flight, so a tick during a stop emits no starts at all.
- Keep `conductor/` out of setuptools `include`; tests insert the repo root on `sys.path`.

## Handoff (build step 4)
Done: `conductor/runner.py` and `tests/test_conductor_runner.py` (3 tests; 31 pass with plan/report/tick). Stdlib only.
Draft PR stacked on #28 (base `claude/conductor-tick`); retarget as #25/#26/#27/#28 merge.
API: `run_tick(repo, executor=claude_executor, max_parallel=3, conductor_dir=None) -> list[Action]` reads `.conductor/{project,tasks}.json`,
runs `assign_models` + `tick`, and for each start: `ensure_worktree` (`.conductor/worktrees/<id>`, branch `conductor/<id>`), records `doing`
in tasks.json, calls the executor, then writes `session_id`, `cost_usd` (accumulated), `context_tokens` (latest context size) and status
(`review` on success, `blocked` on failure); finally regenerates `report.md` (stop reasons go to Open items).
Executor = `Callable[[ExecRequest], ExecResult]`; default builds `claude -p PROMPT --model X --max-turns N --output-format json [--resume ID]`
and parses `total_cost_usd`, `session_id`, `usage` (input + cache create/read + output tokens). Tests inject a fake; the smoke test uses a temp git repo.
Next: step 5, cloud runner as a skill (`/tick`, `/project-start`) calling create/get/archive session tools, plus one scheduled routine. Reuse `tick()` unchanged;
only the executor/state store differs (sessions instead of worktrees; read session status via get_session).
Gotchas:
- The real `claude` CLI path is untested here (no network/claude in unit tests); verify the JSON shape and the `--resume` + `-p` combination on first real use.
- Starts run sequentially, not in parallel; `max_parallel` only caps how many a tick starts.
- Local runs never archive: `archive`/`archive_candidate` actions are ignored (listed in report only).
- `context_tokens` is the last run's usage total, an approximation of context size, not a sum.
- Worktrees are created from `HEAD` of the repo; the runner never pushes.
- tmp-path tests need `mkdir(parents=True)`; `pip install pytest` may be needed in a fresh session.

## Handoff (build step 5)
Done: `conductor/cloud.py` (+ `tests/test_conductor_cloud.py`, 4 tests; 35 pass with plan/report/tick/runner), skill `.claude/skills/conductor/SKILL.md`,
entry points `.claude/commands/tick.md` and `project-start.md`, and the routine definition `docs/CONDUCTOR_ROUTINE.md` (documented only, no trigger created).
Draft PR stacked on #29 (base `claude/conductor-runner`); retarget as #25/#26/#27/#28/#29 merge.
Design: `python3 -m conductor.cloud plan|start|status|report` does the deterministic work (reuses `tick()` unchanged); the skill makes the
`create_session` / `send_message` / `get_session` / `archive_session` calls. `plan` claims starts as `doing` so repeated ticks never re-select them.
Next: step 6, board sync view only (render tasks.json to a board view, no write-back) + docs publish for the final report (`report.md`).
Gotchas:
- The `get_session` shape is assumed, not verified here: `status_bucket` (working/review_ready/completed/blocked/failed) and `context_usage.used_tokens`; cost is read from `cost_usd`/`usage.cost_usd`/`total_cost_usd` if present, otherwise left unchanged. Verify on first real run.
- `completed` maps to `review`, never `done`: a human (or PR merge) marks `done`; only then does `auto_archive` act.
- `start_reuse` sends the brief via `send_message`; it does not check the session is idle.
- `conductor/` stays out of the setuptools include list; tests insert the repo root on `sys.path`. `pip install pytest` may be needed.


## Handoff (build step 6) - BUILD COMPLETE
Done: `conductor/board.py` (`render_board(project, tasks)`, `write_board`, `doc_payload(report_md)`), CLI `python3 -m conductor.cloud board|publish-doc`,
`tests/test_conductor_board.py` (3 tests; 38 pass with plan/report/tick/runner/cloud), and a skill section. All six build steps (#25-#30 plus this PR) are done; the conductor build is complete.
Board = read-only Markdown kanban (one section per status, file order), written to `.conductor/board.md`; tasks.json is never modified.
Docs publish = `publish-doc` prints the docs `batch` create payload for report.md; the skill makes the actual call (no network in code or tests).
Gotchas:
- The docs `batch` payload shape follows the docs connector instructions (`container.kind=project`, `create.doc.markdown`); verify on first real publish.
- No external board (GitHub Projects etc.) is synced; there is deliberately no write-back.
- PR stack: #25 <- #26 <- #27 <- #28 <- #29 <- #30 <- this PR; retarget each to main as the one below merges.
- `conductor/` stays out of the setuptools include list; `pip install pytest` may be needed.
