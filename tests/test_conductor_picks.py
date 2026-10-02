import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))  # conductor/ is not an installed package

from conductor import picks  # noqa: E402
from conductor.plan import load_tasks, save_tasks  # noqa: E402


def _w(d: Path, name: str, obj) -> None:
    d.mkdir(parents=True, exist_ok=True)
    (d / f"{name}.json").write_text(json.dumps(obj))


def _fixture(tmp_path):
    pk, dk = tmp_path / "picks", tmp_path / "desks"
    tasks = {
        "t1": {"title": "Tidy widget docs", "status": "todo", "repo": "demo", "source": "note A",
               "basis": "unverified", "owner": "claude",
               "decision": {"text": "Go ahead", "conditions": ["no new deps"]}},
        "t2": {"title": "Second thing", "status": "todo", "source": "note B", "basis": "checked", "owner": "claude"},
        "t3": {"title": "Pay the invoice", "status": "todo", "owner": "owner"},
        "t4": {"title": "Blocked one", "status": "blocked", "owner": "claude"},
        "t5": {"title": "Wire x BLOCKED on y", "status": "todo", "owner": "claude"},
        "t6": {"title": "Later thing", "status": "todo", "owner": "claude"},
    }
    _w(dk, "alpha", {"id": "alpha", "data": {"desk": "alpha", "tasks": tasks}})  # wrapped shape
    _w(pk, "alpha~t2", {"id": "alpha~t2", "data": {"choice": "now", "rank": 1, "desk": "alpha", "tkey": "t2"}})
    _w(pk, "alpha~t1", {"choice": "now", "rank": 2, "desk": "alpha", "tkey": "t1"})  # bare shape
    for k, r in (("t3", 3), ("t4", 4), ("t5", 5)):
        _w(pk, f"alpha~{k}", {"choice": "now", "rank": r, "desk": "alpha", "tkey": k})
    _w(pk, "alpha~t6", {"choice": "later", "rank": 0, "desk": "alpha", "tkey": "t6"})
    return pk, dk


def test_queued_only_and_rank_order(tmp_path):
    pk, dk = _fixture(tmp_path)
    q = picks.queued_tasks(pk, dk)
    assert [e["tkey"] for e in q] == ["t2", "t1", "t3", "t4", "t5"]  # t6 (later) never queued


def test_skip_rules_listed_with_reason(tmp_path):
    pk, dk = _fixture(tmp_path)
    added, skipped = picks.write_tasks(picks.queued_tasks(pk, dk), tmp_path / ".conductor")
    assert [t.id for t in added] == ["pick-alpha-t2", "pick-alpha-t1"]
    assert {s["id"]: s["reason"] for s in skipped} == {
        "pick-alpha-t3": "owner-only task (only Novah can do it)",
        "pick-alpha-t4": "status is blocked",
        "pick-alpha-t5": "title says BLOCKED on",
    }
    assert json.loads((tmp_path / ".conductor" / "picks-skipped.json").read_text()) == skipped


def test_decision_and_unverified_in_brief(tmp_path):
    pk, dk = _fixture(tmp_path)
    picks.write_tasks(picks.queued_tasks(pk, dk), tmp_path / "c")
    by = {t.id: t for t in load_tasks(tmp_path / "c" / "tasks.json")}
    b1, b2 = by["pick-alpha-t1"].brief, by["pick-alpha-t2"].brief
    assert "Go ahead" in b1 and "no new deps" in b1 and "UNVERIFIED" in b1
    assert "UNVERIFIED" not in b2
    assert "DRAFT PR" in b1 and "do not merge" in b1.lower() and "odyssey" in b1
    t = by["pick-alpha-t1"]
    assert (t.status, t.envelope) == ("todo", "standard") and t.model


def test_existing_tasks_not_reset(tmp_path):
    pk, dk = _fixture(tmp_path)
    c = tmp_path / "c"
    picks.write_tasks(picks.queued_tasks(pk, dk), c)
    ts = load_tasks(c / "tasks.json")
    ts[0].status = "done"
    save_tasks(ts, c / "tasks.json")
    added, _ = picks.write_tasks(picks.queued_tasks(pk, dk), c)
    assert added == [] and load_tasks(c / "tasks.json")[0].status == "done"


def test_missing_task_record_skipped(tmp_path):
    pk, dk = _fixture(tmp_path)
    _w(pk, "alpha~gone", {"choice": "now", "rank": 9, "desk": "alpha", "tkey": "gone"})
    _, skipped = picks.write_tasks(picks.queued_tasks(pk, dk), tmp_path / "c")
    assert any("not found" in s["reason"] for s in skipped)


def test_cli(tmp_path, capsys):
    pk, dk = _fixture(tmp_path)
    assert picks.main(["--picks", str(pk), "--desks", str(dk), "--out", str(tmp_path / "o")]) == 0
    assert "queued 2 task(s)" in capsys.readouterr().out


def test_real_export_shapes(tmp_path):
    """Shapes seen in the real ArtifactData export: lower-case desk doc id, no `desk` field, upper-case desk in
    the pick, @ in file names, answer/note decisions, needs-owner status, free-text owner."""
    pk, dk = tmp_path / "picks", tmp_path / "desks"
    tasks = {
        "P7": {"title": "Reports 7", "status": "open", "owner": "session", "basis": "x", "key": "P7"},
        "P8": {"title": "Reports 8", "status": "open", "owner": "session", "basis": "x",
               "decision": {"answer": "Yes", "note": "mind the mailbox", "q": 23, "source": "Router desk page"}},
        "N1": {"title": "Needs him", "status": "needs-owner", "owner": "session"},
        "N2": {"title": "His own", "status": "open", "owner": "Novah"},
        "N3": {"title": "Mixed", "status": "open", "owner": "novah-then-session"},
        "N4": {"title": "Odd status", "status": "weird", "owner": "session"},
    }
    _w(dk, "watch", {"name": "WATCH", "tasks": tasks})
    for k in tasks:
        _w(pk, f"WATCH@{k}", {"choice": "now", "desk": "WATCH", "rank": 1, "tkey": k})
    _w(pk, "ROUTER@H", {"choice": None, "desk": "ROUTER", "rank": None, "tkey": "H"})
    added, skipped = picks.write_tasks(picks.queued_tasks(pk, dk), tmp_path / "c")
    assert sorted(t.id for t in added) == ["pick-WATCH-P7", "pick-WATCH-P8"]
    assert len(skipped) == 4 and not any("not found" in s["reason"] for s in skipped)
    b = {t.id: t for t in added}["pick-WATCH-P8"].brief
    assert "Owner decision: Yes" in b and "mind the mailbox" in b and "Router desk page" in b
