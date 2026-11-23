import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))  # conductor/ is not an installed package

from conductor.cloud import main, plan_tick, record_start, record_status  # noqa: E402
from conductor.plan import load_tasks  # noqa: E402


def setup(tmp_path, tasks, **proj):
    c = tmp_path / ".conductor"
    c.mkdir(parents=True)
    (c / "project.json").write_text(json.dumps({"name": "T", "slug": "t", "goal": "g", **proj}))
    (c / "tasks.json").write_text(json.dumps(tasks))
    return c


def test_plan_spawns_claims_and_does_not_repeat(tmp_path):
    c = setup(tmp_path, [{"id": "a", "title": "fix typo", "effort": "small"}, {"id": "b", "title": "x", "depends": ["a"]}])
    out = plan_tick(c, "https://github.com/o/r", "main")
    assert [s["task_id"] for s in out["spawns"]] == ["a"]
    cs = out["spawns"][0]["create_session"]
    assert cs["model"].startswith("claude-") and "task:a" in cs["tags"] and cs["source_url"].endswith("o/r")
    assert load_tasks(c / "tasks.json")[0].status == "doing"
    assert plan_tick(c, "https://github.com/o/r")["spawns"] == []  # claimed, not re-selected
    assert (c / "report.md").exists()


def test_reuse_archive_and_budget(tmp_path):
    c = setup(tmp_path, [{"id": "a", "title": "t", "status": "done", "session_id": "session_1"},
                         {"id": "b", "title": "t", "session_id": "session_2", "context_tokens": 10}], auto_archive=True)
    out = plan_tick(c, "u")
    assert out["reuses"][0]["session_id"] == "session_2" and out["archives"][0]["session_id"] == "session_1"
    c2 = setup(tmp_path / "x", [{"id": "a", "title": "t", "context_tokens": 999}], budget={"soft": 5, "hard": 9})
    out = plan_tick(c2, "u")
    assert out["spawns"] == [] and out["stops"][0]["kind"] == "stop_hard"


def test_record_start_and_status(tmp_path):
    c = setup(tmp_path, [{"id": "a", "title": "t"}])
    record_start(c, "a", "session_9")
    t = record_status(c, "a", {"status_bucket": "review_ready", "context_usage": {"used_tokens": 42000}, "cost_usd": 1.5})
    assert (t.status, t.context_tokens, t.cost_usd, t.session_id) == ("review", 42000, 1.5, "session_9")
    t = record_status(c, "a", {"status_bucket": "failed"})
    assert t.status == "blocked" and t.context_tokens == 42000


def test_cli(tmp_path, capsys):
    c = setup(tmp_path, [{"id": "a", "title": "t"}])
    assert main(["--dir", str(c), "plan", "--repo-url", "u"]) == 0
    assert json.loads(capsys.readouterr().out)["spawns"][0]["task_id"] == "a"
    assert main(["--dir", str(c), "report"]) == 0
