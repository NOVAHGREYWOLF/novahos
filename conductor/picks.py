"""Pick-to-run bridge: turn the owner's queued picks ("Do now") into tasks.json entries.

The owner picks tasks on the Conductor desk artifact. A script cannot read that database (it needs the
owner's auth); a Claude session exports it with ArtifactData (`list` with out_dir) into two directories:
picks/*.json and desks/*.json. This module reads those exports, so it never touches the network.

    python -m conductor.picks --picks DIR --desks DIR --out .conductor

writes/merges <out>/tasks.json and <out>/picks-skipped.json. Then run the existing tick. Only picks with
choice == "now" are ever queued; owner-only and blocked tasks are skipped with a reason, never started.
Pure and stdlib-only. Doc shape is {"id":..,"data":{...}} or the data object itself.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

from .plan import LANES, PlanError, Task, assign_models, load_tasks, save_tasks

RULES = (
    "Rules: re-read the current state of the repo and any files named here before acting; the status and "
    "source above may be stale. Work in a git worktree and open a DRAFT PR. Do not merge, do not deploy, "
    "use no secrets, send nothing off this machine. Use the ratified arm names: hub, signal, scope, reach, "
    "orbit, odyssey."
)


HUMAN_OWNERS = {"owner", "you"}  # the real export also has "Novah", "novah-then-session", ...
STARTABLE = {"open", "unverified", "todo"}  # real statuses: open, unverified, blocked, needs-owner


def _docs(directory: str | Path) -> list[dict[str, Any]]:
    """Every *.json in `directory` as {id, data}; accepts {"id","data"} wrappers or bare data objects."""
    out = []
    for f in sorted(Path(directory).glob("*.json")):
        raw = json.loads(f.read_text(encoding="utf-8"))
        if not isinstance(raw, dict):
            continue
        data = raw["data"] if isinstance(raw.get("data"), dict) else raw
        out.append({"id": str(raw.get("id") or f.stem), "data": data})
    return out


def queued_tasks(picks_dir: str | Path, desks_dir: str | Path) -> list[dict[str, Any]]:
    """Picks with choice == 'now', ordered by rank, each joined to its task record.

    A pick whose task record cannot be found is returned with `missing: True` so the caller can report it.
    """
    desks: dict[str, dict[str, Any]] = {}
    for d in _docs(desks_dir):
        tasks = d["data"].get("tasks")
        if isinstance(tasks, dict):
            # the real export keys desks by lower-case id ("watch") while picks say "WATCH": match case-blind
            desks[str(d["data"].get("desk") or d["id"]).lower()] = tasks
            desks.setdefault(d["id"].lower(), tasks)
    queued = []
    for p in _docs(picks_dir):
        data = p["data"]
        if data.get("choice") != "now":
            continue
        desk, tkey = data.get("desk"), data.get("tkey")
        if (not desk or not tkey) and "~" in p["id"]:
            desk, tkey = p["id"].split("~", 1)
        rec = (desks.get(str(desk).lower()) or {}).get(str(tkey))
        entry: dict[str, Any] = {"desk": desk, "tkey": tkey, "rank": data.get("rank")}
        if isinstance(rec, dict):
            entry.update({k: v for k, v in rec.items() if k not in entry})
            entry["title"] = rec.get("title") or str(tkey)
        else:
            entry.update(missing=True, title=str(tkey))
        queued.append(entry)

    def order(e: dict[str, Any]):
        r = e["rank"]
        ranked = isinstance(r, (int, float)) and not isinstance(r, bool)
        return (not ranked, r if ranked else 0, str(e["desk"]), str(e["tkey"]))

    queued.sort(key=order)
    return queued


def skip_reason(entry: dict[str, Any]) -> str | None:
    if entry.get("missing"):
        return "task record not found in desks export"
    owner = str(entry.get("owner") or "").strip().lower()
    if owner in HUMAN_OWNERS or owner.startswith("novah"):
        return "owner-only task (only Novah can do it)"
    status = str(entry.get("status") or "").strip().lower()
    if status == "blocked":
        return "status is blocked"
    if status not in STARTABLE:  # fail closed: needs-owner, done, or any status we have not seen
        return f"status {status or 'missing'!r} is not startable"
    if "BLOCKED on" in str(entry.get("title", "")):
        return "title says BLOCKED on"
    return None


def task_id(entry: dict[str, Any]) -> str:
    raw = f"pick-{entry['desk']}-{entry['tkey']}"
    return re.sub(r"[^A-Za-z0-9._-]+", "-", raw).strip("-")[:80]


def build_brief(entry: dict[str, Any]) -> str:
    lines = [f"Owner-queued task: {entry['title']}", f"Desk: {entry.get('desk')}"]
    if entry.get("repo"):
        lines.append(f"Repo: {entry['repo']}")
    unverified = str(entry.get("basis") or "unverified").lower() == "unverified"
    tag = " (UNVERIFIED)" if unverified else f" (basis: {entry.get('basis')})"
    lines.append(f"Status: {entry.get('status', 'unknown')}; source: {entry.get('source', 'unknown')}{tag}")
    if unverified:
        lines.append("The status and source above are UNVERIFIED claims: check them yourself first.")
    dec = entry.get("decision")
    if isinstance(dec, dict):
        text = dec.get("text") or dec.get("decision") or dec.get("answer")  # real shape: answer/note/q/source
        if text:
            lines.append(f"Owner decision: {text}")
        if dec.get("note"):
            lines.append(f"Decision note: {dec['note']}")
        if dec.get("source"):
            lines.append(f"Decision source: {dec['source']}")
        cond = dec.get("conditions") or dec.get("condition")
        if cond:
            cond = "; ".join(map(str, cond)) if isinstance(cond, list) else cond
            lines.append(f"Conditions: {cond}")
    lines.append(RULES)
    return "\n".join(lines)


def to_task(entry: dict[str, Any]) -> Task:
    desk = str(entry.get("desk") or "").upper()
    return Task(id=task_id(entry), title=str(entry["title"])[:200], effort="medium", envelope="standard",
                lane=desk if desk in LANES else None, brief=build_brief(entry))


def write_tasks(entries: list[dict[str, Any]], out_dir: str | Path) -> tuple[list[Task], list[dict[str, str]]]:
    """Merge queued entries into <out>/tasks.json (existing tasks, incl. their status, are never altered).

    Returns (tasks added, skipped list of {id, title, reason}); also writes <out>/picks-skipped.json.
    """
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    tpath = out / "tasks.json"
    existing = load_tasks(tpath) if tpath.exists() else []
    have = {t.id for t in existing}
    added: list[Task] = []
    skipped: list[dict[str, str]] = []
    for e in entries:
        reason = skip_reason(e)
        if reason:
            skipped.append({"id": task_id(e), "title": str(e.get("title")), "reason": reason})
            continue
        t = to_task(e)
        if t.id in have:
            continue  # already planned (possibly running or done): never reset it
        have.add(t.id)
        added.append(t)
    assign_models(added)
    save_tasks(existing + added, tpath)
    (out / "picks-skipped.json").write_text(json.dumps(skipped, indent=2) + "\n", encoding="utf-8")
    return added, skipped


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m conductor.picks", description=__doc__.splitlines()[0])
    ap.add_argument("--picks", required=True, help="dir of exported picks/*.json")
    ap.add_argument("--desks", required=True, help="dir of exported desks/*.json")
    ap.add_argument("--out", default=".conductor", help="conductor dir holding tasks.json")
    a = ap.parse_args(argv)
    try:
        added, skipped = write_tasks(queued_tasks(a.picks, a.desks), a.out)
    except (PlanError, OSError, ValueError) as e:
        print(f"picks: {e}", file=sys.stderr)
        return 1
    print(f"queued {len(added)} task(s): {', '.join(t.id for t in added) or '-'}")
    for s in skipped:
        print(f"skipped {s['id']}: {s['reason']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
