"""Local runner: applies tick() actions with `claude -p` in a git worktree per task.

Stdlib only. The executor is injectable (unit tests pass a fake; nothing here touches the network
unless the default `claude_executor` runs). tick() does not set `doing`, so the runner records every
start in tasks.json before executing it, then regenerates report.md.
Local runs never archive sessions: archive actions are reported as skipped.
"""
from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from .plan import Task, assign_models, load_project, load_tasks, save_tasks, validate
from .report import write_report
from .tick import Action, State, tick

DEFAULT_MAX_TURNS = {"small": 10, "low": 15, "medium": 25, "high": 40, "xhigh": 60}


@dataclass(frozen=True)
class ExecRequest:
    task: Task
    cwd: Path
    prompt: str
    model: str
    max_turns: int
    resume: str | None = None  # session id for start_reuse


@dataclass(frozen=True)
class ExecResult:
    ok: bool
    session_id: str | None = None
    cost_usd: float = 0.0
    context_tokens: int = 0
    summary: str = ""


Executor = Callable[[ExecRequest], ExecResult]


def parse_claude_json(stdout: str) -> ExecResult:
    """Parse `claude -p --output-format json` output (a result object, or a list of events ending in one)."""
    data = json.loads(stdout)
    if isinstance(data, list):
        data = next((e for e in reversed(data) if isinstance(e, dict) and e.get("type") == "result"), {})
    u = data.get("usage") or {}
    tokens = sum(int(u.get(k) or 0) for k in
                 ("input_tokens", "cache_creation_input_tokens", "cache_read_input_tokens", "output_tokens"))
    return ExecResult(ok=not data.get("is_error", False) and data.get("subtype", "success") == "success",
                      session_id=data.get("session_id"), cost_usd=float(data.get("total_cost_usd") or 0.0),
                      context_tokens=tokens, summary=str(data.get("result") or "")[:500])


def build_command(req: ExecRequest) -> list[str]:
    cmd = ["claude", "-p", req.prompt, "--model", req.model, "--max-turns", str(req.max_turns),
           "--output-format", "json"]
    if req.resume:
        cmd += ["--resume", req.resume]
    return cmd


def claude_executor(req: ExecRequest) -> ExecResult:
    """Default executor: runs the real `claude` CLI in the task worktree."""
    try:
        proc = subprocess.run(build_command(req), cwd=req.cwd, capture_output=True, text=True, timeout=3600)
        return parse_claude_json(proc.stdout)
    except (OSError, subprocess.TimeoutExpired, ValueError) as e:
        return ExecResult(ok=False, summary=f"executor failed: {type(e).__name__}: {e}")


def _git(repo: Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True, text=True)


def ensure_worktree(repo: Path, task: Task, base: str = "HEAD") -> Path:
    """One worktree per task at <repo>/.conductor/worktrees/<id> on branch conductor/<id> (reused if present)."""
    path = repo / ".conductor" / "worktrees" / task.id
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        _git(repo, "worktree", "add", "-b", f"conductor/{task.id}", str(path), base)
    return path


def task_prompt(task: Task) -> str:
    return (f"Task {task.id}: {task.title}\nEffort: {task.effort}. Envelope: {task.envelope}.\n"
            "Work on this branch only, commit your changes, do not push or force-push, "
            "and write a short handoff if you run out of budget."
            + (f"\n\n{task.brief}" if task.brief else ""))


def run_tick(repo: str | Path, executor: Executor = claude_executor, max_parallel: int = 3,
             conductor_dir: str | Path | None = None) -> list[Action]:
    """One tick: load state, ask tick() what to do, run the starts, persist, regenerate report.md.

    Starts are recorded (status `doing`) and saved before each executor call, so a crash or a second
    tick never re-selects them. Success -> `review`; failure -> `blocked`. Stop actions halt new starts
    (tick already emits none); archive actions are never executed locally.
    """
    repo = Path(repo)
    cdir = Path(conductor_dir) if conductor_dir else repo / ".conductor"
    project = load_project(cdir / "project.json")
    tasks_path = cdir / "tasks.json"
    tasks = assign_models(load_tasks(tasks_path))
    validate(tasks)
    by_id = {t.id: t for t in tasks}

    actions = tick(State(project, tasks, max_parallel))
    for a in actions:
        if a.kind not in ("start_fresh", "start_reuse"):
            continue
        t = by_id[a.task_id]
        wt = ensure_worktree(repo, t)
        t.status = "doing"
        save_tasks(tasks, tasks_path)
        res = executor(ExecRequest(t, wt, task_prompt(t), t.model or "sonnet",
                                   DEFAULT_MAX_TURNS.get(t.effort, 25),
                                   resume=a.session_id if a.kind == "start_reuse" else None))
        t.session_id = res.session_id or t.session_id
        t.cost_usd += res.cost_usd
        if res.context_tokens:
            t.context_tokens = res.context_tokens  # latest context size, not cumulative
        t.status = "review" if res.ok else "blocked"
        save_tasks(tasks, tasks_path)

    write_report(cdir / "report.md", project, tasks,
                 open_items=[f"{a.kind}: {a.reason}" for a in actions if a.kind.startswith("stop_")])
    return actions
