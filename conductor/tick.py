"""One conductor tick as a pure function: tick(state) -> list of actions.

Stdlib only, no I/O, no clock. A runner executes the actions and writes results back to tasks.json.
Budget is measured like report.py: sum of Task.context_tokens against project.budget (soft/hard, the project TOTAL).
Per-session limits (project.per_session) apply to each tracked task on its own.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from .plan import Project, Task, ready_tasks



@dataclass
class State:
    project: Project
    tasks: list[Task]
    max_parallel: int = 3


@dataclass(frozen=True)
class Action:
    """kind: start_fresh | start_reuse | archive | archive_candidate | stop_soft | stop_hard |
    handoff_due | stop_session (the last two are per task and never block starts)."""
    kind: str
    task_id: str | None = None
    session_id: str | None = None
    reason: str = ""


def archive_candidates(tasks: list[Task]) -> list[Task]:
    """Done tasks that still have a session (the rule report.py uses)."""
    return [t for t in tasks if t.status == "done" and t.session_id]


def budget_level(project: Project, tasks: list[Task]) -> str | None:
    """'hard' or 'soft' when total context tokens exceed that limit, else None."""
    total = sum(t.context_tokens for t in tasks)
    if total > project.budget.hard:
        return "hard"
    if total > project.budget.soft:
        return "soft"
    return None


def session_actions(project: Project, tasks: list[Task]) -> list[Action]:
    """Per-session limits: handoff_due above per_session.soft, stop_session (list only) above per_session.hard."""
    out = []
    lim = project.per_session
    for t in tasks:
        if not t.session_id or t.status not in ("doing", "pr", "review"):
            continue
        if t.context_tokens > lim.hard:
            out.append(Action("stop_session", t.id, t.session_id,
                              f"{t.context_tokens} context tokens > per-session hard {lim.hard}"))
        elif t.context_tokens > lim.soft:
            out.append(Action("handoff_due", t.id, t.session_id,
                              f"{t.context_tokens} context tokens > per-session soft {lim.soft}"))
    return out


def tick(state: State) -> list[Action]:
    """Actions for this tick, in order: stops, per-session handoff/stop, archive handling, then task starts.

    Soft budget stops new starts (in-flight work finishes); hard budget stops everything
    except housekeeping. Archive actions are emitted only when project.auto_archive is true;
    otherwise candidates are only listed.
    """
    p, tasks = state.project, state.tasks
    actions: list[Action] = []

    level = budget_level(p, tasks)
    if level:
        total = sum(t.context_tokens for t in tasks)
        limit = p.budget.hard if level == "hard" else p.budget.soft
        actions.append(Action(f"stop_{level}", reason=f"{total} context tokens > {level} budget {limit}"))

    actions.extend(session_actions(p, tasks))

    for t in archive_candidates(tasks):
        if p.auto_archive:
            actions.append(Action("archive", t.id, t.session_id, "done and auto_archive is on"))
        else:
            actions.append(Action("archive_candidate", t.id, t.session_id, "auto_archive is off: list only"))

    reuse_below = p.reuse_below
    if level is None:
        for t in ready_tasks(tasks, state.max_parallel):
            if t.session_id and t.context_tokens < reuse_below:
                actions.append(Action("start_reuse", t.id, t.session_id,
                                      f"{t.context_tokens} < {reuse_below} context tokens"))
            else:
                why = "no session yet" if not t.session_id else f"{t.context_tokens} >= {reuse_below} context tokens"
                actions.append(Action("start_fresh", t.id, None, why))
    return actions
