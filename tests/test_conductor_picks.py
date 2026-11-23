import json
import sys
from pathlib import Path

import pytest

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


def _collision_fixture(tmp_path):
    """Desk 'a-b' + key 'c' and desk 'a' + key 'b-c' both sanitize to 'pick-a-b-c'; two long keys that share
    their first 80 characters both hit the 80-character cap at the same string."""
    pk, dk = tmp_path / "picks", tmp_path / "desks"
    rec = {"status": "todo", "owner": "claude"}
    long1, long2 = "k" * 80 + "-first-one", "k" * 80 + "-second-one"
    _w(dk, "a-b", {"desk": "a-b", "tasks": {"c": {"title": "From a-b", **rec}}})
    _w(dk, "a", {"desk": "a", "tasks": {"b-c": {"title": "From a", **rec}, long1: {"title": "Long 1", **rec},
                                         long2: {"title": "Long 2", **rec}}})
    _w(pk, "a-b~c", {"choice": "now", "rank": 1, "desk": "a-b", "tkey": "c"})
    _w(pk, "a~b-c", {"choice": "now", "rank": 2, "desk": "a", "tkey": "b-c"})
    _w(pk, "a~long1", {"choice": "now", "rank": 3, "desk": "a", "tkey": long1})
    _w(pk, "a~long2", {"choice": "now", "rank": 4, "desk": "a", "tkey": long2})
    return pk, dk, long1, long2


def test_in_batch_id_collision_is_reported_not_silent(tmp_path):
    pk, dk, long1, long2 = _collision_fixture(tmp_path)
    added, skipped = picks.write_tasks(picks.queued_tasks(pk, dk), tmp_path / "c")
    ids = [t.id for t in added]
    assert len(ids) == 2 and len(set(ids)) == 2 and "pick-a-b-c" in ids
    assert all(len(i) <= 80 for i in ids)
    assert [t.title for t in added] == ["From a-b", "Long 1"]  # the lower rank keeps the id
    assert [s["title"] for s in skipped] == ["From a", "Long 2"]
    assert "already taken by queued pick a-b/c" in skipped[0]["reason"]
    assert f"a/{long1}" in skipped[1]["reason"]
    assert json.loads((tmp_path / "c" / "picks-skipped.json").read_text()) == skipped


def test_collision_stays_listed_on_rerun_and_never_resets_the_winner(tmp_path):
    pk, dk, _, _ = _collision_fixture(tmp_path)
    c = tmp_path / "c"
    picks.write_tasks(picks.queued_tasks(pk, dk), c)
    ts = load_tasks(c / "tasks.json")
    ts[0].status = "done"
    save_tasks(ts, c / "tasks.json")
    added, skipped = picks.write_tasks(picks.queued_tasks(pk, dk), c)
    assert added == []  # both ids are planned already
    assert [s["title"] for s in skipped] == ["From a", "Long 2"]  # the collision is still visible
    assert load_tasks(c / "tasks.json")[0].status == "done"


def test_blocked_pick_does_not_claim_an_id(tmp_path):
    pk, dk = tmp_path / "picks", tmp_path / "desks"
    _w(dk, "a-b", {"desk": "a-b", "tasks": {"c": {"title": "Blocked", "status": "blocked", "owner": "claude"}}})
    _w(dk, "a", {"desk": "a", "tasks": {"b-c": {"title": "Fine", "status": "todo", "owner": "claude"}}})
    _w(pk, "a-b~c", {"choice": "now", "rank": 1, "desk": "a-b", "tkey": "c"})
    _w(pk, "a~b-c", {"choice": "now", "rank": 2, "desk": "a", "tkey": "b-c"})
    added, skipped = picks.write_tasks(picks.queued_tasks(pk, dk), tmp_path / "c")
    assert [t.title for t in added] == ["Fine"]
    assert [s["reason"] for s in skipped] == ["status is blocked"]


def test_malformed_export_names_the_file(tmp_path):
    pk, dk = _fixture(tmp_path)
    (pk / "alpha~t9.json").write_text("{not json", encoding="utf-8")
    with pytest.raises(ValueError, match=r"alpha~t9\.json"):
        picks.queued_tasks(pk, dk)


def test_non_utf8_export_names_the_file(tmp_path):
    pk, dk = _fixture(tmp_path)
    (dk / "beta.json").write_bytes(b"\xff\xfe\x00bad")
    with pytest.raises(ValueError, match=r"beta\.json"):
        picks.queued_tasks(pk, dk)


def test_cli_exits_1_and_names_the_file_on_malformed_export(tmp_path, capsys):
    pk, dk = _fixture(tmp_path)
    (dk / "broken.json").write_text("[1, 2", encoding="utf-8")
    out = tmp_path / "o"
    assert picks.main(["--picks", str(pk), "--desks", str(dk), "--out", str(out)]) == 1
    err = capsys.readouterr().err
    assert "broken.json" in err and "not valid JSON" in err
    assert not (out / "tasks.json").exists()  # nothing half-written


def test_missing_export_directory_is_an_error_not_an_empty_queue(tmp_path, capsys):
    pk, dk = _fixture(tmp_path)
    assert picks.main(["--picks", str(tmp_path / "nope"), "--desks", str(dk), "--out", str(tmp_path / "o")]) == 1
    assert "not a directory" in capsys.readouterr().err
    with pytest.raises(ValueError, match="not a directory"):
        picks.queued_tasks(pk, tmp_path / "nope")
