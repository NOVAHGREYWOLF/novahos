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

STATUSES = ("todo", "doing", "pr", "review", "done", "blocked")
EFFORTS = ("small", "low", "medium", "high", "xhigh")
ENVELOPES = ("standard", "production", "critical", "door")
# The owner groups sessions in the Claude app sidebar by lane. The API has no group field, so a spawned
# session mirrors its lane as the tag `lane:<NAME>` and as a "NAME · " title prefix. Case-sensitive.
LANES = ("ROUTER", "SENSORS", "DOORS", "INTELLIGENCE", "ARMS", "NODE", "SURFACE", "LAB", "MONEY", "VAULT",
         "SUITE", "ROUNDTRIP", "COMMS", "FIELD", "PRIVACY", "PRODUCT", "WATCH", "MARKET", "BRAIN", "WEBSITES")

ROUTE_PATH = Path(__file__).resolve().parent.parent / ".claude" / "skills" / "route-and-spawn" / "route.py"


class PlanError(ValueError):
    """Raised for an invalid plan; the message lists every problem found."""


@dataclass
class Budget:
    soft: int = 100_000
    hard: int = 150_000


@dataclass
class Project:
    name: str
    slug: str
    goal: str
    auto_archive: bool = False
    budget: Budget = field(default_factory=Budget)
    lane: str | None = None  # default lane for tasks that do not set their own


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
    lane: str | None = None  # overrides the project's default lane
    brief: str | None = None  # full task text for the session; prompts append it when set


def lane_error(lane: Any, where: str) -> str | None:
    """None when `lane` is None or an allowed lane name; otherwise a one-line error for `where`."""
    if lane is None or (isinstance(lane, str) and lane in LANES):
        return None
    return f"{where}: invalid lane {lane!r} (one of {', '.join(LANES)}; upper-case)"


def effective_lane(project: Project, task: Task) -> str | None:
    """The task's own lane, else the project's default lane, else None."""
    return task.lane or project.lane


# ---------------------------------------------------------------- load / save

def project_from_dict(d: dict[str, Any]) -> Project:
    errs = []
    for key in ("name", "slug", "goal"):
        if not isinstance(d.get(key), str) or not d[key].strip():
            errs.append(f"project: '{key}' is required and must be a non-empty string")
    if not isinstance(d.get("auto_archive", False), bool):
        errs.append("project: 'auto_archive' must be true or false")
    b = d.get("budget") or {}
    soft, hard = b.get("soft", Budget.soft), b.get("hard", Budget.hard)
    if not all(isinstance(x, int) and not isinstance(x, bool) and x > 0 for x in (soft, hard)):
        errs.append("project: budget.soft and budget.hard must be positive integers")
    elif soft > hard:
        errs.append(f"project: budget.soft ({soft}) must not exceed budget.hard ({hard})")
    if (e := lane_error(d.get("lane"), "project")):
        errs.append(e)
    if errs:
        raise PlanError("\n".join(errs))
    return Project(d["name"], d["slug"], d["goal"], d.get("auto_archive", False), Budget(soft, hard), d.get("lane"))


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


def _plain(obj: Project | Task) -> dict[str, Any]:
    """asdict, minus an unset lane so files that never used lanes stay byte-identical."""
    d = asdict(obj)
    for optional in ("lane", "brief"):
        if d.get(optional) is None:
            d.pop(optional, None)
    return d


def save_project(project: Project, path: str | Path) -> None:
    Path(path).write_text(json.dumps(_plain(project), indent=2) + "\n")


def save_tasks(tasks: list[Task], path: str | Path) -> None:
    validate(tasks)
    Path(path).write_text(json.dumps([_plain(t) for t in tasks], indent=2) + "\n")


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
        if (e := lane_error(t.lane, f"task {t.id!r}")):
            errs.append(e)
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

    Tasks already in flight (doing/pr/review) count against max_parallel.
    """
    by_id = {t.id: t for t in tasks}
    in_flight = sum(t.status in ("doing", "pr", "review") for t in tasks)
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
