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


def test_mark_done_then_auto_archive(tmp_path):
    from conductor.cloud import mark_done
    c = setup(tmp_path, [{"id": "a", "title": "x", "status": "review", "session_id": "S1"}], auto_archive=True)
    assert plan_tick(c, "https://github.com/o/r")["archives"] == []
    mark_done(c, ["a"], pr=7)
    out = plan_tick(c, "https://github.com/o/r")
    assert out["archives"] == [{"task_id": "a", "session_id": "S1"}]
    assert load_tasks(c / "tasks.json")[0].pr == 7


def test_import_sessions_and_config(tmp_path, capsys):
    from conductor.cloud import import_sessions
    c = setup(tmp_path, [])
    rows = [{"id": "session_abcdef12", "title": "old work", "status_bucket": "working"}, {"id": "session_zzzzzzzz"}]
    assert [t.status for t in import_sessions(c, rows)] == ["doing", "review"]
    assert import_sessions(c, rows) == []  # idempotent
    f = tmp_path / "s.json"
    f.write_text(json.dumps([]))
    assert main(["--dir", str(c), "config", "--auto-archive", "on"]) == 0
    assert '"auto_archive": true' in capsys.readouterr().out


def test_import_accepts_prefixed_buckets(tmp_path):
    from conductor.cloud import import_sessions
    c = setup(tmp_path, [])
    rows = [{"id": "session_aaaaaaaa", "status_bucket": "SESSION_STATUS_BUCKET_WORKING"},
            {"id": "session_bbbbbbbb", "status_bucket": "SESSION_STATUS_BUCKET_FAILED"}]
    assert [t.status for t in import_sessions(c, rows)] == ["doing", "blocked"]


LIVE_RECORD = {"ccr": {
    "id": "session_0000000000000001", "session_status": "idle",
    "status_bucket": "SESSION_STATUS_BUCKET_REVIEW_READY", "tags": ["conductor"],
    "external_metadata": {"context_usage": {"max_tokens": 1000000, "used_tokens": 54321},
                          "usage": {"cost_usd": 2.25, "input_tokens": 10, "output_tokens": 20}}}}


def test_record_status_live_wrapped_record(tmp_path):
    c = setup(tmp_path, [{"id": "a", "title": "t"}])
    t = record_status(c, "a", LIVE_RECORD)
    assert (t.status, t.context_tokens, t.cost_usd) == ("review", 54321, 2.25)
    assert t.session_id == "session_0000000000000001"


def test_record_status_zero_mid_turn_keeps_larger_value(tmp_path):
    c = setup(tmp_path, [{"id": "a", "title": "t", "context_tokens": 70000, "cost_usd": 3.0}])
    running = {"ccr": {"id": "s", "status_bucket": "SESSION_STATUS_BUCKET_WORKING",
                       "external_metadata": {"context_usage": {"used_tokens": 0}, "usage": {"cost_usd": 0}}}}
    t = record_status(c, "a", running)
    assert (t.context_tokens, t.cost_usd) == (70000, 3.0)
    done = {"ccr": {"id": "s", "status_bucket": "SESSION_STATUS_BUCKET_COMPLETED",
                    "external_metadata": {"context_usage": {"used_tokens": 0}}}}
    assert record_status(c, "a", done).context_tokens == 0  # a finished session's value is taken as-is


def test_child_brief_appends_full_brief(tmp_path):
    from conductor.cloud import child_brief
    from conductor.plan import Task
    task = Task(id="a", title="t")
    assert "FULL BRIEF" not in child_brief(task) and "FULL BRIEF" not in child_brief(task, tmp_path)
    (tmp_path / "a.md").write_text("Design: do the thing.\n")
    out = child_brief(task, tmp_path)
    assert out.startswith("Conductor task a: t") and "## FULL BRIEF" in out and out.rstrip().endswith("Design: do the thing.")
    assert "FULL BRIEF" not in child_brief(Task(id="../a", title="t"), tmp_path / "x")


def test_plan_brief_dir_flag_reaches_prompt(tmp_path, capsys):
    c = setup(tmp_path, [{"id": "a", "title": "t"}])
    (c / "briefs").mkdir()
    (c / "briefs" / "a.md").write_text("SECRET-FREE DESIGN TEXT")
    assert main(["--dir", str(c), "plan", "--repo-url", "u", "--brief-dir", str(c / "briefs")]) == 0
    assert "SECRET-FREE DESIGN TEXT" in json.loads(capsys.readouterr().out)["spawns"][0]["create_session"]["prompt"]


def test_handoff_due_in_plan_output(tmp_path):
    c = setup(tmp_path, [{"id": "a", "title": "t", "status": "doing", "session_id": "S", "context_tokens": 320000}])
    out = plan_tick(c, "u")
    assert [h["session_id"] for h in out["handoffs"]] == ["S"] and "handoff" in out["handoffs"][0]["send_message"]


def test_import_marks_adopted_and_frees_slots(tmp_path):
    from conductor.cloud import import_sessions
    c = setup(tmp_path, [{"id": "n", "title": "new work"}])
    rows = [{"id": f"session_{i:08d}", "status_bucket": "review_ready"} for i in range(10)]
    assert all(t.adopted for t in import_sessions(c, rows))
    assert [s["task_id"] for s in plan_tick(c, "u", max_parallel=1)["spawns"]] == ["n"]
