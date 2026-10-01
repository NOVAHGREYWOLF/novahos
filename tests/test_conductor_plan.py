import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))  # conductor/ is not an installed package

from conductor import plan  # noqa: E402
from conductor.plan import PlanError, Task  # noqa: E402


def T(id, **kw):
    return Task(id=id, title=kw.pop("title", f"task {id}"), **kw)


def test_valid_plan_loads(tmp_path):
    (tmp_path / "project.json").write_text(json.dumps({"name": "P", "slug": "p", "goal": "g"}))
    (tmp_path / "tasks.json").write_text(json.dumps([
        {"id": "a", "title": "A"},
        {"id": "b", "title": "B", "depends": ["a"], "effort": "high", "envelope": "critical"},
    ]))
    p = plan.load_project(tmp_path / "project.json")
    assert (p.auto_archive, p.budget.soft, p.budget.hard) == (False, 100_000, 150_000)
    tasks = plan.load_tasks(tmp_path / "tasks.json")
    assert [t.id for t in tasks] == ["a", "b"] and tasks[0].status == "todo"


@pytest.mark.parametrize("project", [
    {"slug": "p", "goal": "g"},
    {"name": "P", "slug": "p", "goal": "g", "auto_archive": "yes"},
    {"name": "P", "slug": "p", "goal": "g", "budget": {"soft": 200, "hard": 100}},
])
def test_invalid_project(project):
    with pytest.raises(PlanError):
        plan.project_from_dict(project)


def test_duplicate_ids():
    with pytest.raises(PlanError, match="duplicate task id 'a'"):
        plan.validate([T("a"), T("a")])


def test_unknown_dependency_and_self_dependency():
    with pytest.raises(PlanError, match="unknown task 'zz'"):
        plan.validate([T("a", depends=["zz"])])
    with pytest.raises(PlanError, match="depends on itself"):
        plan.validate([T("a", depends=["a"])])


@pytest.mark.parametrize("field,value", [("status", "weird"), ("effort", "huge"), ("envelope", "x")])
def test_invalid_enums(field, value):
    with pytest.raises(PlanError, match=f"invalid {field}"):
        plan.validate([T("a", **{field: value})])


def test_cycle_detected():
    with pytest.raises(PlanError, match="cycle: a -> c -> b -> a"):
        plan.validate([T("a", depends=["c"]), T("b", depends=["a"]), T("c", depends=["b"])])


def test_unknown_field_rejected():
    with pytest.raises(PlanError, match="unknown field"):
        plan.task_from_dict({"id": "a", "title": "A", "bogus": 1})


def test_ready_tasks_deps_status_order():
    tasks = [T("a", status="done"), T("b", depends=["a"]), T("c", depends=["b"]),
             T("d"), T("e", status="blocked"), T("f", depends=["a"])]
    assert [t.id for t in plan.ready_tasks(tasks, 10)] == ["b", "d", "f"]


def test_ready_tasks_max_parallel_counts_in_flight():
    tasks = [T("a", status="doing"), T("b"), T("c"), T("d")]
    assert [t.id for t in plan.ready_tasks(tasks, 2)] == ["b"]
    assert plan.ready_tasks(tasks, 1) == []
    assert [t.id for t in plan.ready_tasks([T("x"), T("y"), T("z")], 2)] == ["x", "y"]


def test_assign_models_keeps_pins_and_fills_rest():
    tasks = [
        T("a", title="fix typo in readme", effort="small"),
        T("b", title="build feature", effort="medium"),
        T("c", title="auth rewrite", effort="high"),
        T("d", title="build feature", model_pin="haiku"),
        T("e", title="build feature", model="custom-model"),
    ]
    plan.assign_models(tasks)
    assert [t.model for t in tasks] == ["haiku", "sonnet", "opus", "haiku", "custom-model"]


def test_assign_models_matches_router():
    t = T("a", title="auth rewrite", effort="high")
    plan.assign_models([t])
    assert t.model == plan._load_router().route({"title": t.title, "effort": "high"})["model"]


def test_save_load_round_trip(tmp_path):
    tasks = [T("a", cost_usd=1.5, context_tokens=42, pr=7), T("b", depends=["a"], model="m")]
    plan.save_tasks(tasks, tmp_path / "tasks.json")
    assert plan.load_tasks(tmp_path / "tasks.json") == tasks
    proj = plan.Project("P", "p", "g", True, plan.Budget(1, 2))
    plan.save_project(proj, tmp_path / "project.json")
    assert plan.load_project(tmp_path / "project.json") == proj


# ----------------------------------------------------------------------- lanes

ALL_LANES = ("ROUTER", "SENSORS", "DOORS", "INTELLIGENCE", "ARMS", "NODE", "SURFACE", "LAB", "MONEY", "VAULT",
             "SUITE", "ROUNDTRIP", "COMMS", "FIELD", "PRIVACY", "PRODUCT", "WATCH", "MARKET", "BRAIN", "WEBSITES")


def test_lane_set_is_the_owners_list():
    assert plan.LANES == ALL_LANES


@pytest.mark.parametrize("lane", ALL_LANES)
def test_valid_lane_on_task_and_project(lane):
    plan.validate([T("a", lane=lane)])
    assert plan.project_from_dict({"name": "P", "slug": "p", "goal": "g", "lane": lane}).lane == lane


@pytest.mark.parametrize("lane", ["router", "Router", "NOPE", "", " ROUTER", 7, ["ROUTER"], True])
def test_invalid_task_lane_is_rejected_with_a_clear_error(lane):
    with pytest.raises(PlanError, match=r"task 'a': invalid lane .* \(one of ROUTER, SENSORS, .*WEBSITES; upper-case\)"):
        plan.validate([T("a", lane=lane)])


@pytest.mark.parametrize("lane", ["router", "NOPE", "", 7])
def test_invalid_project_lane_is_rejected(lane):
    with pytest.raises(PlanError, match=r"project: invalid lane .* \(one of ROUTER, .*WEBSITES; upper-case\)"):
        plan.project_from_dict({"name": "P", "slug": "p", "goal": "g", "lane": lane})


def test_lane_defaults_to_none_and_other_unknown_fields_still_rejected():
    assert T("a").lane is None
    assert plan.project_from_dict({"name": "P", "slug": "p", "goal": "g"}).lane is None
    with pytest.raises(PlanError, match="unknown field"):
        plan.task_from_dict({"id": "a", "title": "A", "lanes": "ROUTER"})
    assert plan.task_from_dict({"id": "a", "title": "A", "lane": "MONEY"}).lane == "MONEY"


def test_invalid_lane_is_rejected_on_load_and_save(tmp_path):
    (tmp_path / "tasks.json").write_text(json.dumps([{"id": "a", "title": "A", "lane": "nope"}]))
    with pytest.raises(PlanError, match="invalid lane"):
        plan.load_tasks(tmp_path / "tasks.json")
    with pytest.raises(PlanError, match="invalid lane"):
        plan.save_tasks([T("a", lane="nope")], tmp_path / "out.json")


def test_project_default_lane_and_task_override():
    proj = plan.Project("P", "p", "g", lane="MONEY")
    assert plan.effective_lane(proj, T("a")) == "MONEY"
    assert plan.effective_lane(proj, T("b", lane="ROUTER")) == "ROUTER"
    assert plan.effective_lane(plan.Project("P", "p", "g"), T("c")) is None
    assert plan.effective_lane(plan.Project("P", "p", "g"), T("d", lane="LAB")) == "LAB"


def test_lane_round_trips_and_is_omitted_when_none(tmp_path):
    tasks = [T("a", lane="INTELLIGENCE"), T("b")]
    plan.save_tasks(tasks, tmp_path / "tasks.json")
    raw = json.loads((tmp_path / "tasks.json").read_text())
    assert raw[0]["lane"] == "INTELLIGENCE" and "lane" not in raw[1]
    assert plan.load_tasks(tmp_path / "tasks.json") == tasks
    with_lane = plan.Project("P", "p", "g", True, plan.Budget(1, 2), "MONEY")
    plan.save_project(with_lane, tmp_path / "project.json")
    assert json.loads((tmp_path / "project.json").read_text())["lane"] == "MONEY"
    assert plan.load_project(tmp_path / "project.json") == with_lane
    plain = plan.Project("P", "p", "g")
    plan.save_project(plain, tmp_path / "project2.json")
    assert "lane" not in json.loads((tmp_path / "project2.json").read_text())
    assert plan.load_project(tmp_path / "project2.json") == plain


def test_existing_files_without_lane_are_byte_stable(tmp_path):
    original = [{"id": "a", "title": "A", "effort": "medium", "envelope": "standard", "depends": [], "model": None,
                 "model_pin": None, "status": "todo", "session_id": None, "pr": None, "cost_usd": 0.0,
                 "context_tokens": 0}]
    path = tmp_path / "tasks.json"
    path.write_text(json.dumps(original, indent=2) + "\n")
    before = path.read_text()
    plan.save_tasks(plan.load_tasks(path), path)
    assert path.read_text() == before
