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
