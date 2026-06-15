"""Hash-chained audit trail — append, integrity, tamper-detection, query, file round-trip."""
import dataclasses

import pytest

from novahos.audit_trail import AuditEntry, AuditIntegrityError, AuditTrail


def _rec(t: AuditTrail, action="post", decision="APPROVE", trace="t1", agent="CROESUS"):
    return t.record(trace_id=trace, agent=agent, action=action, action_class="read_data",
                    decision=decision, reasons=["ok"], payload={"x": 1})


def test_append_and_chain():
    t = AuditTrail()
    a, b = _rec(t), _rec(t, action="send")
    assert a.seq == 0 and b.seq == 1
    assert a.prev_hash == "0" * 64
    assert b.prev_hash == a.entry_hash      # chained
    assert len(t) == 2 and t.verify_integrity()


def test_payload_is_digested_not_stored():
    t = AuditTrail()
    e = t.record(trace_id="x", agent="A", action="a", action_class="c",
                 decision="APPROVE", payload={"secret": "hunter2"})
    assert "hunter2" not in e.payload_digest and len(e.payload_digest) == 64


def test_tamper_detected():
    t = AuditTrail()
    _rec(t); _rec(t, action="send")
    # Forge entry 0 (frozen dataclass → rebuild) and confirm the chain fails.
    t._entries[0] = dataclasses.replace(t._entries[0], action="MUTATED")
    assert t.verify_integrity() is False


def test_explain_and_query():
    t = AuditTrail()
    _rec(t, trace="alpha"); _rec(t, trace="alpha", action="send", decision="BLOCK")
    _rec(t, trace="beta", agent="MERCURY")
    assert len(t.explain("alpha")) == 2
    assert len(t.query(agent="MERCURY")) == 1
    assert len(t.query(decision="BLOCK")) == 1


def test_file_roundtrip_and_reload_verifies(tmp_path):
    p = tmp_path / "audit.jsonl"
    t = AuditTrail(p)
    _rec(t); _rec(t, action="send")
    # Reopen from disk → loads + verifies the chain.
    t2 = AuditTrail(p)
    assert len(t2) == 2 and t2.verify_integrity()
    assert t2.get(1).prev_hash == t2.get(0).entry_hash


def test_corrupt_file_raises(tmp_path):
    p = tmp_path / "audit.jsonl"
    t = AuditTrail(p)
    _rec(t); _rec(t, action="send")
    lines = p.read_text(encoding="utf-8").splitlines()
    bad = AuditEntry.from_json(lines[0])
    bad = dataclasses.replace(bad, action="MUTATED")  # edit but keep stale hash
    p.write_text(bad.to_json() + "\n" + lines[1] + "\n", encoding="utf-8")
    with pytest.raises(AuditIntegrityError):
        AuditTrail(p)
