"""Cloud runner helpers: the deterministic half of the conductor skill.

Stdlib only, no network. The skill (.claude/skills/conductor/SKILL.md) makes the create_session /
get_session / send_message / archive_session calls; this module decides what to call and records the
results in .conductor/tasks.json. Sessions replace worktrees; tick() is reused unchanged.

CLI (JSON in/out, see the skill):
  python3 -m conductor.cloud plan  [--repo-url U] [--revision R] [--max-parallel N]
  python3 -m conductor.cloud start TASK_ID SESSION_ID
  python3 -m conductor.cloud status TASK_ID SESSION_JSON_FILE
  python3 -m conductor.cloud report
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from .plan import Task, assign_models, load_project, load_tasks, save_tasks, validate, _load_router
from .report import write_report
from .tick import State, tick

BUCKET_TO_STATUS = {"working": "doing", "review_ready": "review", "completed": "review",
                    "blocked": "blocked", "failed": "blocked"}


def child_brief(task: Task) -> str:
    return (f"Conductor task {task.id}: {task.title}\nEffort: {task.effort}. Envelope: {task.envelope}.\n"
            "One task, one session, one PR (draft). Read docs/ and the handoff section first. Budget: handoff at "
            "100k tokens, hard stop 150k. No polling, no wake-ups, never archive sessions, never force-push. "
            "Write a short handoff and stop when done or blocked.")


def plan_tick(cdir: Path, repo_url: str, revision: str = "main", max_parallel: int = 3, claim: bool = True) -> dict:
    """Run tick() and translate it into session calls. Claimed starts are saved as `doing` before returning,
    so a repeated tick never re-selects them (same rule as the local runner)."""
    project = load_project(cdir / "project.json")
    tasks_path = cdir / "tasks.json"
    tasks = assign_models(load_tasks(tasks_path))
    validate(tasks)
    by_id = {t.id: t for t in tasks}
    ids = _load_router().IDS
    actions = tick(State(project, tasks, max_parallel))

    spawns, reuses, archives, candidates, stops = [], [], [], [], []
    for a in actions:
        if a.kind == "start_fresh":
            t = by_id[a.task_id]
            spawns.append({"task_id": t.id, "create_session": {
                "model": ids[t.model or "sonnet"], "source_url": repo_url, "source_revision": revision,
                "tags": ["conductor", f"task:{t.id}", f"model:{t.model}"],
                "title": f"Conductor {project.slug}: {t.id} {t.title}"[:200], "prompt": child_brief(t)}})
        elif a.kind == "start_reuse":
            reuses.append({"task_id": a.task_id, "session_id": a.session_id,
                           "send_message": child_brief(by_id[a.task_id])})
        elif a.kind == "archive":
            archives.append({"task_id": a.task_id, "session_id": a.session_id})
        elif a.kind == "archive_candidate":
            candidates.append({"task_id": a.task_id, "session_id": a.session_id})
        elif a.kind.startswith("stop_"):
            stops.append({"kind": a.kind, "reason": a.reason})
    if claim and (spawns or reuses):
        for s in (*spawns, *reuses):
            by_id[s["task_id"]].status = "doing"
        save_tasks(tasks, tasks_path)
    write_report(cdir / "report.md", project, tasks, open_items=[f"{s['kind']}: {s['reason']}" for s in stops])
    return {"spawns": spawns, "reuses": reuses, "archives": archives, "archive_candidates": candidates, "stops": stops}


def record_start(cdir: Path, task_id: str, session_id: str) -> Task:
    tasks = load_tasks(cdir / "tasks.json")
    t = next(t for t in tasks if t.id == task_id)
    t.session_id, t.status = session_id, "doing"
    save_tasks(tasks, cdir / "tasks.json")
    return t


def _dig(d: Any, *paths: str) -> Any:
    for p in paths:
        cur = d
        for k in p.split("."):
            cur = cur.get(k) if isinstance(cur, dict) else None
        if cur is not None:
            return cur
    return None


def record_status(cdir: Path, task_id: str, session: dict) -> Task:
    """Fold a get_session result into the task: status from status_bucket, context from context_usage,
    cost if the result carries one. Missing fields leave the task's values alone."""
    tasks = load_tasks(cdir / "tasks.json")
    t = next(t for t in tasks if t.id == task_id)
    status = BUCKET_TO_STATUS.get(str(session.get("status_bucket")))
    if status and t.status != "done":
        t.status = status
    tokens = _dig(session, "context_usage.used_tokens", "context_tokens")
    if tokens is not None:
        t.context_tokens = int(tokens)
    cost = _dig(session, "cost_usd", "usage.cost_usd", "total_cost_usd")
    if cost is not None:
        t.cost_usd = float(cost)
    t.session_id = session.get("id") or session.get("session_id") or t.session_id
    save_tasks(tasks, cdir / "tasks.json")
    return t


def render_report(cdir: Path) -> Path:
    write_report(cdir / "report.md", load_project(cdir / "project.json"), load_tasks(cdir / "tasks.json"))
    return cdir / "report.md"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="conductor.cloud")
    ap.add_argument("--dir", default=".conductor")
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("plan")
    p.add_argument("--repo-url", required=True)
    p.add_argument("--revision", default="main")
    p.add_argument("--max-parallel", type=int, default=3)
    s = sub.add_parser("start")
    s.add_argument("task_id")
    s.add_argument("session_id")
    st = sub.add_parser("status")
    st.add_argument("task_id")
    st.add_argument("session_json")
    sub.add_parser("report")
    a = ap.parse_args(argv)
    cdir = Path(a.dir)
    if a.cmd == "plan":
        out: Any = plan_tick(cdir, a.repo_url, a.revision, a.max_parallel)
    elif a.cmd == "start":
        out = {"task": record_start(cdir, a.task_id, a.session_id).id, "status": "doing"}
    elif a.cmd == "status":
        t = record_status(cdir, a.task_id, json.loads(Path(a.session_json).read_text()))
        out = {"task": t.id, "status": t.status, "context_tokens": t.context_tokens, "cost_usd": t.cost_usd}
    else:
        out = {"report": str(render_report(cdir))}
    json.dump(out, sys.stdout, indent=2)
    print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
