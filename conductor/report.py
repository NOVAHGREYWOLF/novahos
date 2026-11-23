"""Render tasks.json + project.json as a deterministic Markdown report (report.md).

Pure and stdlib-only: no clock, no I/O except write_report. Same input -> same bytes.
Budget (soft/hard) is in tokens and is compared with the sum of Task.context_tokens;
cost is shown in USD from Task.cost_usd.
"""
from __future__ import annotations

from pathlib import Path
from typing import Iterable

from .plan import STATUSES, Project, Task


def _cell(text: object) -> str:
    return str(text).replace("|", "\\|").replace("\n", " ").strip()


def _usd(x: float) -> str:
    return f"${x:,.2f}"


def _tok(n: int) -> str:
    return f"{n:,}"


def _pr(t: Task) -> str:
    return f"#{t.pr}" if isinstance(t.pr, int) or str(t.pr).isdigit() else (str(t.pr) if t.pr else "-")


def _table(header: list[str], rows: list[list[str]]) -> list[str]:
    out = ["| " + " | ".join(header) + " |", "|" + "|".join("---" for _ in header) + "|"]
    out += ["| " + " | ".join(_cell(c) for c in r) + " |" for r in rows]
    return out


def _bullets(items: Iterable[str], empty: str = "None.") -> list[str]:
    items = [str(i).strip() for i in items]
    return [f"- {i}" for i in items] if items else [empty]


def render(project: Project, tasks: list[Task], decisions: Iterable[str] = (),
           lessons: Iterable[str] = (), open_items: Iterable[str] = ()) -> str:
    L: list[str] = [f"# {project.name} - report", "", "## Goal", "", project.goal.strip(), ""]

    L += ["## Tasks", ""]
    counts = ", ".join(f"{s} {sum(t.status == s for t in tasks)}" for s in STATUSES)
    L += [f"{len(tasks)} task(s): {counts}.", ""]
    if tasks:
        L += _table(["id", "title", "status", "model", "PR"],
                    [[t.id, t.title, t.status, t.model or "-", _pr(t)] for t in tasks])
    else:
        L += ["No tasks."]
    L.append("")

    L += ["## Cost", "", "By task:", ""]
    if tasks:
        L += _table(["task", "model", "cost", "context tokens"],
                    [[t.id, t.model or "-", _usd(t.cost_usd), _tok(t.context_tokens)] for t in tasks])
    else:
        L += ["No spend."]
    L += ["", "By model:", ""]
    by_model: dict[str, list[float | int]] = {}
    for t in tasks:
        agg = by_model.setdefault(t.model or "unassigned", [0, 0.0, 0])
        agg[0] += 1
        agg[1] += t.cost_usd
        agg[2] += t.context_tokens
    if by_model:
        L += _table(["model", "tasks", "cost", "context tokens"],
                    [[m, str(a[0]), _usd(a[1]), _tok(a[2])] for m, a in sorted(by_model.items())])
    else:
        L += ["No spend."]
    L.append("")

    total_usd = sum(t.cost_usd for t in tasks)
    total_tok = sum(t.context_tokens for t in tasks)
    soft, hard = project.budget.soft, project.budget.hard
    status = "OVER HARD BUDGET" if total_tok > hard else "OVER SOFT BUDGET" if total_tok > soft else "within budget"
    L += ["## Budget", "",
          f"- Total spend: {_usd(total_usd)}",
          f"- Total context tokens: {_tok(total_tok)}",
          f"- Soft budget: {_tok(soft)} tokens ({'exceeded' if total_tok > soft else 'ok'})",
          f"- Hard budget: {_tok(hard)} tokens ({'exceeded' if total_tok > hard else 'ok'})",
          f"- Status: **{status}**", ""]

    L += ["## Archive candidates", ""]
    cands = [t for t in tasks if t.status == "done" and t.session_id]
    if cands:
        L += [("auto_archive is on: these sessions are eligible for archiving."
               if project.auto_archive else
               "auto_archive is off: listed only, nothing is archived without a yes."), ""]
        L += _bullets(f"{t.id}: session {t.session_id}" for t in cands)
    else:
        L += ["None."]
    L.append("")

    L += ["## Decisions", ""] + _bullets(decisions) + [""]
    L += ["## Lessons", ""] + _bullets(lessons) + [""]
    L += ["## Open items", ""]
    L += _bullets([f"{t.id} is blocked: {t.title}" for t in tasks if t.status == "blocked"] + list(open_items))
    return "\n".join(L) + "\n"


def write_report(path: str | Path, project: Project, tasks: list[Task], decisions: Iterable[str] = (),
                 lessons: Iterable[str] = (), open_items: Iterable[str] = ()) -> str:
    """Render and write the report; returns the text."""
    text = render(project, tasks, decisions, lessons, open_items)
    Path(path).write_text(text)
    return text
