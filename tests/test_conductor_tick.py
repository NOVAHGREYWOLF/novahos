import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))  # conductor/ is not an installed package

from conductor.plan import Budget, Project, Task  # noqa: E402
from conductor.tick import State, tick  # noqa: E402


def P(auto=False, soft=100, hard=200):
    return Project("P", "p", "g", auto_archive=auto, budget=Budget(soft, hard))


def T(id, **kw):
    return Task(id=id, title=f"task {id}", **kw)


def kinds(actions):
    return [(a.kind, a.task_id) for a in actions]


def test_ready_selection_respects_deps_and_slots():
    tasks = [T("a", status="done"), T("b", depends=["a"]), T("c", depends=["b"]), T("d"), T("e", status="doing")]
    assert kinds(tick(State(P(), tasks, max_parallel=2))) == [("start_fresh", "b")]  # e holds one slot
    assert kinds(tick(State(P(), tasks, max_parallel=3))) == [("start_fresh", "b"), ("start_fresh", "d")]


def test_reuse_below_60k_fresh_otherwise():
    tasks = [T("a", session_id="s1", context_tokens=59_999), T("b", session_id="s2", context_tokens=60_000),
             T("c", context_tokens=0)]
    p = P(soft=10**9, hard=10**9)
    acts = tick(State(p, tasks, max_parallel=5))
    assert kinds(acts) == [("start_reuse", "a"), ("start_fresh", "b"), ("start_fresh", "c")]
    assert acts[0].session_id == "s1" and acts[1].session_id is None


def test_archive_never_unless_auto_archive():
    tasks = [T("a", status="done", session_id="s1"), T("b", status="done"), T("c", status="doing", session_id="s3")]
    assert kinds(tick(State(P(auto=False), tasks))) == [("archive_candidate", "a")]
    assert kinds(tick(State(P(auto=True), tasks))) == [("archive", "a")]


def test_budget_boundaries_not_exceeded():
    tasks = [T("a", status="doing", context_tokens=100), T("b")]  # total == soft: not exceeded
    assert kinds(tick(State(P(), tasks, max_parallel=3))) == [("start_fresh", "b")]


def test_soft_stop_blocks_starts_only():
    tasks = [T("a", status="done", session_id="s", context_tokens=101), T("b")]
    acts = tick(State(P(auto=True), tasks))
    assert kinds(acts) == [("stop_soft", None), ("archive", "a")]


def test_hard_stop_blocks_starts():
    tasks = [T("a", status="doing", context_tokens=201), T("b")]
    acts = tick(State(P(), tasks))
    assert kinds(acts) == [("stop_hard", None)]
    assert "201" in acts[0].reason


def test_pure_same_input_same_output():
    s = State(P(), [T("a"), T("b", depends=["a"])])
    assert tick(s) == tick(s)
    assert s.tasks[0].status == "todo"


def test_total_budget_is_not_the_per_session_limit():
    tasks = [T("a", status="doing", session_id="s1", context_tokens=80_000),
             T("b", status="doing", session_id="s2", context_tokens=80_000)]
    p = Project("P", "p", "g")  # defaults: total 100k/150k, per-session 100k/150k
    p.budget = Budget(500_000, 800_000)
    assert kinds(tick(State(p, tasks))) == []
    assert [a.kind for a in tick(State(Project("P", "p", "g"), tasks))] == ["stop_hard"]  # total 160k > default total


def test_per_session_handoff_due_and_stop_session():
    p = Project("P", "p", "g", budget=Budget(10**9, 10**9))
    tasks = [T("a", status="doing", session_id="s1", context_tokens=100_000),
             T("b", status="pr", session_id="s2", context_tokens=100_001),
             T("c", status="review", session_id="s3", context_tokens=150_001),
             T("d", status="todo", session_id="s4", context_tokens=200_000),
             T("e", status="done", context_tokens=200_000),
             T("f", status="doing", context_tokens=200_000)]  # no session: untracked
    acts = [a for a in tick(State(p, tasks, max_parallel=0)) if a.kind in ("handoff_due", "stop_session")]
    assert kinds(acts) == [("handoff_due", "b"), ("stop_session", "c")]


def test_per_session_field_validated_and_optional():
    from conductor.plan import PlanError, project_from_dict
    base = {"name": "P", "slug": "p", "goal": "g"}
    assert project_from_dict(base).per_session == Budget(100_000, 150_000)
    assert project_from_dict({**base, "per_session": {"soft": 5, "hard": 9}}).per_session == Budget(5, 9)
    import pytest
    with pytest.raises(PlanError):
        project_from_dict({**base, "per_session": {"soft": 9, "hard": 5}})
