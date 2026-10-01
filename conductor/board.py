"""Board view and docs publish payload. Read-only: renders tasks.json, never writes back to it.

Stdlib only, no network, no clock. The skill makes the docs `batch` call with the payload from
`doc_payload`; this module only builds it.
"""
from __future__ import annotations

import json
from pathlib import Path

from .plan import STATUSES, Project, Task


def _card(t: Task) -> str:
    bits = [f"**{t.id}** {t.title}".replace("|", "/").replace("\n", " ")]
    meta = [m for m in (t.model, f"PR #{t.pr}" if str(t.pr or "").isdigit() else t.pr,
                        f"needs {', '.join(t.depends)}" if t.depends else None) if m]
    if meta:
        bits.append("(" + "; ".join(str(m) for m in meta) + ")")
    return " ".join(bits)


def render_board(project: Project, tasks: list[Task]) -> str:
    """Kanban-style Markdown: one section per status in STATUSES order, tasks in file order."""
    L = [f"# {project.name} - board", "", "Read-only view of tasks.json.", ""]
    for s in STATUSES:
        col = [t for t in tasks if t.status == s]
        L += [f"## {s} ({len(col)})", ""]
        L += [f"- {_card(t)}" for t in col] or ["- (none)"]
        L.append("")
    return "\n".join(L).rstrip("\n") + "\n"


def write_board(path: str | Path, project: Project, tasks: list[Task]) -> Path:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(render_board(project, tasks))
    return p


def doc_payload(report_md: str, title: str | None = None) -> dict:
    """Arguments for the docs `batch` create call that publishes report.md as a doc."""
    first = next((ln[2:].strip() for ln in report_md.splitlines() if ln.startswith("# ")), "Conductor report")
    name = title or first
    return {"container": {"kind": "project", "create": {"name": name, "doc": {"markdown": report_md}}}, "batch": []}


def payload_json(cdir: str | Path) -> str:
    return json.dumps(doc_payload((Path(cdir) / "report.md").read_text()), indent=2)
