import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))  # conductor/ is not an installed package

from conductor.plan import load_tasks  # noqa: E402
from conductor.runner import ExecResult, build_command, parse_claude_json, run_tick, ExecRequest  # noqa: E402
from conductor.plan import Task  # noqa: E402


def make_repo(tmp_path, tasks, budget=None):
    r = tmp_path / "toy"
    r.mkdir(parents=True)
    g = lambda *a: subprocess.run(["git", "-C", str(r), *a], check=True, capture_output=True)  # noqa: E731
    g("init", "-q", "-b", "main")
    g("config", "user.email", "t@t")
    g("config", "user.name", "t")
    (r / "README.md").write_text("toy\n")
    c = r / ".conductor"
    c.mkdir()
    proj = {"name": "Toy", "slug": "toy", "goal": "g"}
    if budget:
        proj["budget"] = budget
    (c / "project.json").write_text(json.dumps(proj))
    (c / "tasks.json").write_text(json.dumps(tasks))
    g("add", "-A")
    g("commit", "-qm", "init")
    return r


class Fake:
    def __init__(self, ok=True):
        self.calls, self.ok = [], ok

    def __call__(self, req):
        self.calls.append(req)
        assert req.cwd.is_dir()
        (req.cwd / f"{req.task.id}.txt").write_text("work\n")
        return ExecResult(self.ok, f"sess-{req.task.id}", 0.25, 12_345, "done")


def test_parse_and_command():
    out = json.dumps({"type": "result", "subtype": "success", "is_error": False, "session_id": "s1",
                      "total_cost_usd": 0.5, "result": "ok",
                      "usage": {"input_tokens": 10, "cache_read_input_tokens": 5, "output_tokens": 2}})
    r = parse_claude_json(out)
    assert (r.ok, r.session_id, r.cost_usd, r.context_tokens) == (True, "s1", 0.5, 17)
    assert parse_claude_json(json.dumps([{"type": "system"}, json.loads(out)])).session_id == "s1"
    assert not parse_claude_json(json.dumps({"is_error": True})).ok
    cmd = build_command(ExecRequest(Task("a", "t"), Path("."), "p", "haiku", 7, resume="s9"))
    assert cmd[:2] == ["claude", "-p"] and cmd[cmd.index("--max-turns") + 1] == "7"
    assert cmd[cmd.index("--output-format") + 1] == "json" and cmd[cmd.index("--resume") + 1] == "s9"


def test_smoke_toy_repo(tmp_path):
    repo = make_repo(tmp_path, [{"id": "a", "title": "A"}, {"id": "b", "title": "B", "depends": ["a"]}])
    fake = Fake()
    actions = run_tick(repo, fake)
    assert [a.kind for a in actions] == ["start_fresh"] and len(fake.calls) == 1
    t = {x.id: x for x in load_tasks(repo / ".conductor" / "tasks.json")}
    assert (t["a"].status, t["a"].session_id, t["a"].cost_usd, t["a"].context_tokens) == ("review", "sess-a", 0.25, 12_345)
    assert t["b"].status == "todo" and t["a"].model
    assert (repo / ".conductor" / "worktrees" / "a" / "a.txt").exists()
    assert (repo / ".conductor" / "report.md").read_text().startswith("#")
    assert run_tick(repo, fake) == [] and len(fake.calls) == 1  # a is in review, b still blocked on a


def test_failure_blocks_and_hard_budget_stops(tmp_path):
    repo = make_repo(tmp_path, [{"id": "a", "title": "A"}])
    run_tick(repo, Fake(ok=False))
    assert load_tasks(repo / ".conductor" / "tasks.json")[0].status == "blocked"
    repo2 = make_repo(tmp_path / "x", [{"id": "a", "title": "A", "context_tokens": 500}, {"id": "b", "title": "B"}],
                      budget={"soft": 100, "hard": 200})
    fake = Fake()
    assert [a.kind for a in run_tick(repo2, fake)] == ["stop_hard"] and not fake.calls
    assert "stop_hard" in (repo2 / ".conductor" / "report.md").read_text()
