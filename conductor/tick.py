"""One conductor tick as a pure function: tick(state) -> list of actions.

Stdlib only, no I/O, no clock. A runner executes the actions and writes results back to tasks.json.
Budget is measured like report.py: sum of Task.context_tokens against project.budget (soft/hard).
"""
from __future__ import annotations

from dataclasses import dataclass, field

from .plan import Project, Task, ready_tasks

# Owner's size policy (2026-10-01): reuse an idle session only under 200k tokens; Haiku tasks stay under 150k.
# Same numbers as the handoff / route-and-spawn skills.
REUSE_BELOW_TOKENS = 200_000
REUSE_BELOW_TOKENS_HAIKU = 150_000


def reuse_limit(task: Task) -> int:
    """Context size under which an idle session may be reused for this task."""
    return REUSE_BELOW_TOKENS_HAIKU if task.model == "haiku" else REUSE_BELOW_TOKENS


@dataclass
class State:
    project: Project
    tasks: list[Task]
    max_parallel: int = 3


@dataclass(frozen=True)
class Action:
    """kind: start_fresh | start_reuse | archive | archive_candidate | stop_soft | stop_hard."""
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


def tick(state: State) -> list[Action]:
    """Actions for this tick, in order: stops, archive handling, then task starts.

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

    for t in archive_candidates(tasks):
        if p.auto_archive:
            actions.append(Action("archive", t.id, t.session_id, "done and auto_archive is on"))
        else:
            actions.append(Action("archive_candidate", t.id, t.session_id, "auto_archive is off: list only"))

    if level is None:
        for t in ready_tasks(tasks, state.max_parallel):
            limit = reuse_limit(t)
            if t.session_id and t.context_tokens < limit:
                actions.append(Action("start_reuse", t.id, t.session_id,
                                      f"{t.context_tokens} < {limit} context tokens"))
            else:
                why = "no session yet" if not t.session_id else f"{t.context_tokens} >= {limit} context tokens"
                actions.append(Action("start_fresh", t.id, None, why))
    return actions
