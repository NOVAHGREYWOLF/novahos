import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))  # conductor/ is not an installed package

from conductor import report  # noqa: E402
from conductor.plan import Budget, Project, Task  # noqa: E402

GOLDEN = Path(__file__).parent / "fixtures" / "conductor_report.md"
SEP = "\n<!-- case -->\n"


def P(auto=False, soft=100_000, hard=150_000):
    return Project("Demo", "demo", "Ship the demo.", auto, Budget(soft, hard))


def all_statuses():
    return [
        Task("a", "plan | schema", status="done", model="sonnet", session_id="s_a", pr=26, cost_usd=1.5, context_tokens=40_000),
        Task("b", "report", status="review", model="sonnet", pr="27", cost_usd=0.755, context_tokens=30_000),
        Task("c", "tick", status="pr", model="opus", pr=28, cost_usd=3.0, context_tokens=20_000),
        Task("d", "runner", status="doing", model="haiku", cost_usd=0.1, context_tokens=5_000),
        Task("e", "cloud", status="blocked", depends=["d"]),
        Task("f", "board", status="todo"),
        Task("g", "docs", status="done", model="sonnet", cost_usd=0.2, context_tokens=1_000),
    ]


def cases():
    over = [Task("x", "big", status="done", model="opus", session_id="s_x", cost_usd=12, context_tokens=160_000)]
    return [
        ("empty", report.render(P(), [])),
        ("all-statuses", report.render(P(), all_statuses(), ["Use Sonnet for ticks"], ["Keep steps small"], ["Confirm weekly reset"])),
        ("over-soft", report.render(P(soft=50_000), all_statuses())),
        ("over-hard", report.render(P(), over)),
        ("auto-archive-on", report.render(P(auto=True), all_statuses())),
        ("auto-archive-off", report.render(P(auto=False), all_statuses())),
    ]


def build():
    return SEP.join(f"<!-- {n} -->\n{t}" for n, t in cases())


def test_golden():
    got = build()
    if not GOLDEN.exists():
        GOLDEN.write_text(got)
    assert got == GOLDEN.read_text()


def test_deterministic():
    assert build() == build()


def test_archive_policy():
    on = report.render(P(auto=True), all_statuses())
    off = report.render(P(auto=False), all_statuses())
    assert "eligible for archiving" in on and "listed only" in off
    assert "a: session s_a" in on and "g:" not in on.split("## Decisions")[0].split("## Archive")[1]


def test_over_budget_flag():
    assert "OVER HARD BUDGET" in report.render(P(), [Task("x", "t", context_tokens=200_000)])
    assert "within budget" in report.render(P(), [])


def test_write_report(tmp_path):
    text = report.write_report(tmp_path / "report.md", P(), [])
    assert (tmp_path / "report.md").read_text() == text


def test_lane_column_only_when_a_task_has_a_lane():
    plain = report.render(P(), all_statuses())
    assert "| id | title | status | model | PR |" in plain and "Lane" not in plain
    tasks = all_statuses()
    tasks[0].lane = "INTELLIGENCE"
    tasks[4].lane = "MONEY"
    got = report.render(P(), tasks)
    assert "| id | Lane | title | status | model | PR |" in got
    assert "|---|---|---|---|---|---|" in got
    assert "| a | INTELLIGENCE | plan \\| schema | done | sonnet | #26 |" in got
    assert "| e | MONEY | cloud | blocked | - | - |" in got
    assert "| b | - | report | review | sonnet | #27 |" in got  # a task without a lane shows "-"
    # only the Tasks table changes; every other section is identical to the no-lane render
    assert got.split("## Cost", 1)[1] == plain.split("## Cost", 1)[1]


def test_lane_column_uses_project_default_lane():
    proj = P()
    proj.lane = "ROUTER"
    got = report.render(proj, [Task("a", "t"), Task("b", "u", lane="MONEY")])
    assert "| id | Lane | title | status | model | PR |" in got
    assert "| a | ROUTER | t | todo | - | - |" in got and "| b | MONEY | u | todo | - | - |" in got
    assert "Lane" not in report.render(P(), [Task("a", "t")])


def test_lane_report_is_deterministic():
    tasks = all_statuses()
    tasks[1].lane = "ARMS"
    assert report.render(P(), tasks) == report.render(P(), tasks)
