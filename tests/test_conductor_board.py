import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))  # conductor/ is not an installed package

from conductor.board import doc_payload, render_board  # noqa: E402
from conductor.cloud import main  # noqa: E402
from conductor.plan import project_from_dict, task_from_dict  # noqa: E402

P = project_from_dict({"name": "T", "slug": "t", "goal": "g"})
TASKS = [task_from_dict(d) for d in (
    {"id": "a", "title": "one", "status": "done", "pr": 5, "model": "m"},
    {"id": "b", "title": "two | x", "depends": ["a"]},
)]


def test_board_columns_and_determinism():
    out = render_board(P, TASKS)
    assert out == render_board(P, TASKS)
    assert "## done (1)\n\n- **a** one (m; PR #5)" in out
    assert "## todo (1)\n\n- **b** two / x (needs a)" in out
    assert "## blocked (0)\n\n- (none)" in out


def test_doc_payload_uses_report_title():
    p = doc_payload("# T - report\n\nbody\n")
    assert p["container"]["create"]["name"] == "T - report"
    assert p["container"]["create"]["doc"]["markdown"].startswith("# T - report")


def test_cli_board_is_view_only(tmp_path, capsys):
    c = tmp_path / ".conductor"
    c.mkdir()
    (c / "project.json").write_text(json.dumps({"name": "T", "slug": "t", "goal": "g"}))
    (c / "tasks.json").write_text(json.dumps([{"id": "a", "title": "x"}]))
    before = (c / "tasks.json").read_text()
    assert main(["--dir", str(c), "board"]) == 0
    assert main(["--dir", str(c), "publish-doc"]) == 0
    assert (c / "board.md").exists()
    assert (c / "tasks.json").read_text() == before
