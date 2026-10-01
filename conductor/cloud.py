"""Cloud runner helpers: the deterministic half of the conductor skill.

Stdlib only, no network. The skill (.claude/skills/conductor/SKILL.md) makes the create_session /
get_session / send_message / archive_session calls; this module decides what to call and records the
results in .conductor/tasks.json. Sessions replace worktrees; tick() is reused unchanged.

CLI (JSON in/out, see the skill):
  python3 -m conductor.cloud plan  [--repo-url U] [--revision R] [--max-parallel N]
  python3 -m conductor.cloud start TASK_ID SESSION_ID
  python3 -m conductor.cloud status TASK_ID SESSION_JSON_FILE
  python3 -m conductor.cloud report
  python3 -m conductor.cloud mark-done TASK_ID... [--pr N]
  python3 -m conductor.cloud import SESSIONS_JSON_FILE
  python3 -m conductor.cloud config --auto-archive on|off
  python3 -m conductor.cloud board        # writes .conductor/board.md (view only)
  python3 -m conductor.cloud publish-doc  # prints the docs `batch` payload for report.md
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from .plan import (Task, assign_models, load_project, load_tasks, save_project, save_tasks, validate,
                   _load_router)
from .report import write_report
from .tick import State, tick

BUCKET_TO_STATUS = {"working": "doing", "review_ready": "review", "completed": "review",
                    "blocked": "blocked", "failed": "blocked"}
# A child stopped on a permission prompt cannot send STATUS, so the tick reads it from the session instead.
WAITING_ON_PERMISSION = "Waiting on permission"
# Pre-approves the child's STATUS report; entries the spawner lacks are dropped by create_session.
CHILD_ALLOWED_TOOLS = ["mcp__claude-code-remote__send_message"]


def _bucket(raw: Any) -> str:
    """'SESSION_STATUS_BUCKET_WORKING' (as list_sessions returns it) or 'working' -> 'working'."""
    return str(raw).lower().removeprefix("session_status_bucket_")


def child_brief(task: Task) -> str:
    haiku = " This is a Haiku task: keep it under 150k tokens." if task.model == "haiku" else ""
    return (f"Conductor task {task.id}: {task.title}\nEffort: {task.effort}. Envelope: {task.envelope}.\n"
            "One task, one session, one PR (draft). Read docs/ and the handoff section first. Budget: handoff at "
            f"300k tokens, hard stop 450k.{haiku} No polling, no wake-ups, never archive sessions, never force-push. "
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
            model = t.model or "sonnet"
            spawns.append({"task_id": t.id, "create_session": {
                "model": ids[model], "source_url": repo_url, "source_revision": revision,
                "tags": ["conductor", f"project:{project.slug}", "role:task", f"task:{t.id}", f"model:{model}"],
                "extra_allowed_tools": list(CHILD_ALLOWED_TOOLS),
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
    cost if the result carries one. Missing fields leave the task's values alone. A session whose
    post_turn_summary.status_detail starts with "Waiting on permission" is `blocked`: it cannot report."""
    tasks = load_tasks(cdir / "tasks.json")
    t = next(t for t in tasks if t.id == task_id)
    status = BUCKET_TO_STATUS.get(_bucket(session.get("status_bucket")))
    detail = _dig(session, "post_turn_summary.status_detail", "external_metadata.post_turn_summary.status_detail")
    if isinstance(detail, str) and detail.lstrip().startswith(WAITING_ON_PERMISSION):
        status = "blocked"
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


def mark_done(cdir: Path, task_ids: list[str], pr: str | int | None = None) -> list[Task]:
    """Mark tasks `done` (their PR merged). Once done, a task with a session is an archive candidate, and with
    auto_archive on the next plan emits `archive` for it."""
    tasks = load_tasks(cdir / "tasks.json")
    by_id = {t.id: t for t in tasks}
    missing = [i for i in task_ids if i not in by_id]
    if missing:
        raise SystemExit(f"unknown task id(s): {', '.join(missing)}")
    for i in task_ids:
        by_id[i].status = "done"
        if pr is not None and len(task_ids) == 1:
            by_id[i].pr = pr
    save_tasks(tasks, cdir / "tasks.json")
    return [by_id[i] for i in task_ids]


def import_sessions(cdir: Path, sessions: list[dict]) -> list[Task]:
    """Adopt existing sessions (list_sessions rows: id/session_id, title, status_bucket) as tasks so the
    conductor tracks and archives them. Already-tracked session ids are skipped. Imported tasks never start."""
    tasks = load_tasks(cdir / "tasks.json") if (cdir / "tasks.json").exists() else []
    known = {t.session_id for t in tasks} | {t.id for t in tasks}
    added = []
    for s in sessions:
        sid = s.get("id") or s.get("session_id")
        tid = f"s-{str(sid)[-8:]}"
        if not sid or sid in known or tid in known:
            continue
        status = BUCKET_TO_STATUS.get(_bucket(s.get("status_bucket")), "review")
        t = Task(id=tid, title=str(s.get("title") or sid)[:120], status=status, session_id=sid,
                 model_pin=None)
        tasks.append(t)
        added.append(t)
        known.add(sid)
    save_tasks(tasks, cdir / "tasks.json")
    return added


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
    md = sub.add_parser("mark-done")
    md.add_argument("task_ids", nargs="+")
    md.add_argument("--pr")
    im = sub.add_parser("import")
    im.add_argument("sessions_json", help="JSON list of sessions (list_sessions rows)")
    cf = sub.add_parser("config")
    cf.add_argument("--auto-archive", choices=["on", "off"])
    sub.add_parser("report")
    sub.add_parser("board")
    sub.add_parser("publish-doc")
    a = ap.parse_args(argv)
    cdir = Path(a.dir)
    if a.cmd == "plan":
        out: Any = plan_tick(cdir, a.repo_url, a.revision, a.max_parallel)
    elif a.cmd == "start":
        out = {"task": record_start(cdir, a.task_id, a.session_id).id, "status": "doing"}
    elif a.cmd == "status":
        t = record_status(cdir, a.task_id, json.loads(Path(a.session_json).read_text()))
        out = {"task": t.id, "status": t.status, "context_tokens": t.context_tokens, "cost_usd": t.cost_usd}
    elif a.cmd == "mark-done":
        out = {"done": [t.id for t in mark_done(cdir, a.task_ids, a.pr)]}
    elif a.cmd == "import":
        out = {"imported": [t.id for t in import_sessions(cdir, json.loads(Path(a.sessions_json).read_text()))]}
    elif a.cmd == "config":
        proj = load_project(cdir / "project.json")
        if a.auto_archive:
            proj.auto_archive = a.auto_archive == "on"
            save_project(proj, cdir / "project.json")
        out = {"auto_archive": proj.auto_archive}
    elif a.cmd == "board":
        from .board import write_board
        out = {"board": str(write_board(cdir / "board.md", load_project(cdir / "project.json"), load_tasks(cdir / "tasks.json")))}
    elif a.cmd == "publish-doc":
        from .board import doc_payload
        out = doc_payload(render_report(cdir).read_text())
    else:
        out = {"report": str(render_report(cdir))}
    json.dump(out, sys.stdout, indent=2)
    print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
