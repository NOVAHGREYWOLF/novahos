"""Schema, validation and ready-task selection for .conductor/project.json and tasks.json.

Pure and stdlib-only. Model routing is delegated to .claude/skills/route-and-spawn/route.py,
loaded by path so the rules live in one place.
"""
from __future__ import annotations

import importlib.util
import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from . import policy

STATUSES = ("todo", "doing", "pr", "review", "done", "blocked")
EFFORTS = ("small", "low", "medium", "high", "xhigh")
ENVELOPES = ("standard", "production", "critical", "door")

ROUTE_PATH = Path(__file__).resolve().parent.parent / ".claude" / "skills" / "route-and-spawn" / "route.py"


class PlanError(ValueError):
    """Raised for an invalid plan; the message lists every problem found."""


@dataclass
class Budget:
    soft: int = policy.PROJECT_SOFT
    hard: int = policy.PROJECT_HARD


@dataclass
class Project:
    name: str
    slug: str
    goal: str
    auto_archive: bool = False
    budget: Budget = field(default_factory=Budget)  # project TOTAL across all tasks
    per_session: Budget = field(default_factory=lambda: Budget(policy.SESSION_SOFT, policy.SESSION_HARD))
    reuse_below: int = policy.REUSE_BELOW  # per_session.reuse_below: reuse an idle session only under this


@dataclass
class Task:
    id: str
    title: str
    effort: str = "medium"
    envelope: str = "standard"
    depends: list[str] = field(default_factory=list)
    model: str | None = None
    model_pin: str | None = None
    status: str = "todo"
    session_id: str | None = None
    pr: str | int | None = None
    cost_usd: float = 0.0
    context_tokens: int = 0
    adopted: bool = False  # picked up by `import`; never counts against max_parallel


# ---------------------------------------------------------------- load / save

def project_from_dict(d: dict[str, Any]) -> Project:
    errs = []
    for key in ("name", "slug", "goal"):
        if not isinstance(d.get(key), str) or not d[key].strip():
            errs.append(f"project: '{key}' is required and must be a non-empty string")
    if not isinstance(d.get("auto_archive", False), bool):
        errs.append("project: 'auto_archive' must be true or false")
    limits = {}
    defaults = {"budget": (policy.PROJECT_SOFT, policy.PROJECT_HARD),
                "per_session": (policy.SESSION_SOFT, policy.SESSION_HARD)}
    for key in ("budget", "per_session"):
        b = d.get(key) or {}
        soft, hard = b.get("soft", defaults[key][0]), b.get("hard", defaults[key][1])
        if not all(isinstance(x, int) and not isinstance(x, bool) and x > 0 for x in (soft, hard)):
            errs.append(f"project: {key}.soft and {key}.hard must be positive integers")
        elif soft > hard:
            errs.append(f"project: {key}.soft ({soft}) must not exceed {key}.hard ({hard})")
        limits[key] = Budget(soft, hard)
    reuse = (d.get("per_session") or {}).get("reuse_below", policy.REUSE_BELOW)
    if not (isinstance(reuse, int) and not isinstance(reuse, bool) and reuse > 0):
        errs.append("project: per_session.reuse_below must be a positive integer")
    if errs:
        raise PlanError("\n".join(errs))
    return Project(d["name"], d["slug"], d["goal"], d.get("auto_archive", False), limits["budget"],
                   limits["per_session"], reuse)


def task_from_dict(d: dict[str, Any]) -> Task:
    if not isinstance(d, dict):
        raise PlanError(f"task: expected an object, got {type(d).__name__}")
    known = set(Task.__dataclass_fields__)
    unknown = sorted(set(d) - known)
    if unknown:
        raise PlanError(f"task {d.get('id', '?')!r}: unknown field(s) {unknown}")
    if not isinstance(d.get("id"), str) or not d["id"]:
        raise PlanError("task: 'id' is required and must be a non-empty string")
    if not isinstance(d.get("title"), str) or not d["title"].strip():
        raise PlanError(f"task {d['id']!r}: 'title' is required")
    return Task(**d)


def load_project(path: str | Path) -> Project:
    return project_from_dict(json.loads(Path(path).read_text()))


def load_tasks(path: str | Path) -> list[Task]:
    raw = json.loads(Path(path).read_text())
    if not isinstance(raw, list):
        raise PlanError("tasks.json must be a JSON list of task objects")
    tasks = [task_from_dict(t) for t in raw]
    validate(tasks)
    return tasks


def save_project(project: Project, path: str | Path) -> None:
    d = asdict(project)
    d["per_session"]["reuse_below"] = d.pop("reuse_below")  # project.json nests it under per_session
    Path(path).write_text(json.dumps(d, indent=2) + "\n")


def save_tasks(tasks: list[Task], path: str | Path) -> None:
    validate(tasks)
    Path(path).write_text(json.dumps([asdict(t) for t in tasks], indent=2) + "\n")


# ------------------------------------------------------------------ validate

def validate(tasks: list[Task]) -> None:
    """Raise PlanError listing every problem: ids, enums, dangling deps, cycles."""
    errs: list[str] = []
    ids = [t.id for t in tasks]
    for i in sorted({i for i in ids if ids.count(i) > 1}):
        errs.append(f"duplicate task id {i!r}")
    known = set(ids)
    for t in tasks:
        if t.status not in STATUSES:
            errs.append(f"task {t.id!r}: invalid status {t.status!r} (one of {', '.join(STATUSES)})")
        if t.effort not in EFFORTS:
            errs.append(f"task {t.id!r}: invalid effort {t.effort!r} (one of {', '.join(EFFORTS)})")
        if t.envelope not in ENVELOPES:
            errs.append(f"task {t.id!r}: invalid envelope {t.envelope!r} (one of {', '.join(ENVELOPES)})")
        if not isinstance(t.depends, list):
            errs.append(f"task {t.id!r}: 'depends' must be a list")
            continue
        for d in t.depends:
            if d == t.id:
                errs.append(f"task {t.id!r}: depends on itself")
            elif d not in known:
                errs.append(f"task {t.id!r}: depends on unknown task {d!r}")
    if not errs:  # cycle check needs a well-formed graph
        cycle = _find_cycle(tasks)
        if cycle:
            errs.append("dependency cycle: " + " -> ".join(cycle))
    if errs:
        raise PlanError("\n".join(errs))


def _find_cycle(tasks: list[Task]) -> list[str] | None:
    deps = {t.id: t.depends for t in tasks}
    state: dict[str, int] = {}  # 1 = on stack, 2 = done
    stack: list[str] = []

    def visit(n: str) -> list[str] | None:
        state[n] = 1
        stack.append(n)
        for d in deps[n]:
            if state.get(d) == 1:
                return stack[stack.index(d):] + [d]
            if d not in state and (c := visit(d)):
                return c
        stack.pop()
        state[n] = 2
        return None

    for n in deps:
        if n not in state and (c := visit(n)):
            return c
    return None


# ------------------------------------------------------------------ selection

def ready_tasks(tasks: list[Task], max_parallel: int) -> list[Task]:
    """Todo tasks whose depends are all done, in plan order, capped by free slots.

    Tasks already in flight (doing/pr/review) count against max_parallel, except adopted ones
    (imported sessions), which are tracked but never occupy a slot.
    """
    by_id = {t.id: t for t in tasks}
    in_flight = sum(t.status in ("doing", "pr", "review") and not t.adopted for t in tasks)
    slots = max(0, max_parallel - in_flight)
    ready = [t for t in tasks if t.status == "todo" and all(by_id[d].status == "done" for d in t.depends)]
    return ready[:slots]


# -------------------------------------------------------------------- routing

def _load_router():
    spec = importlib.util.spec_from_file_location("_conductor_route", ROUTE_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def assign_models(tasks: list[Task]) -> list[Task]:
    """Fill a missing `model` with the router's pick. An explicit model_pin always wins.

    A task that already has a model (and no pin) is left alone. Mutates and returns tasks.
    """
    route = _load_router().route
    for t in tasks:
        if t.model and not t.model_pin:
            continue
        t.model = route({"title": t.title, "effort": t.effort, "envelope": t.envelope,
                         "model_pin": t.model_pin})["model"]
    return tasks
