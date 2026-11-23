"""Hash-chained audit trail — append, integrity, tamper-detection, query, file round-trip."""
import dataclasses

import pytest

from novahos.audit_trail import (DIGEST_KEY_ENV, AuditEntry, AuditIntegrityError, AuditTrail,
                                 digest_payload)


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


def test_payload_is_digested_not_stored(monkeypatch):
    monkeypatch.delenv(DIGEST_KEY_ENV, raising=False)
    t = AuditTrail()
    e = t.record(trace_id="x", agent="A", action="a", action_class="c",
                 decision="APPROVE", payload={"secret": "hunter2"})
    # Labelled: the row says which guarantee it carries. Unkeyed is the plain hash.
    assert "hunter2" not in e.payload_digest
    assert e.payload_digest.startswith("sha256:") and len(e.payload_digest) == len("sha256:") + 64
    assert t.digest_keyed is False


def test_unkeyed_digest_confirms_a_guess_and_keyed_does_not(monkeypatch):
    # The C9-F1 finding: a plain SHA-256 of low-entropy tool args lets a reader of the trail
    # confirm a guess. With a key the same guess is worthless without the key.
    monkeypatch.delenv(DIGEST_KEY_ENV, raising=False)
    guess = {"email": "alice@example.com"}
    plain = AuditTrail().record(trace_id="x", agent="A", action="a", action_class="c",
                                decision="APPROVE", payload=guess)
    assert plain.payload_digest == digest_payload(guess)            # confirmable
    keyed_trail = AuditTrail(digest_key="k" * 32)
    keyed = keyed_trail.record(trace_id="x", agent="A", action="a", action_class="c",
                               decision="APPROVE", payload=guess)
    assert keyed_trail.digest_keyed is True
    assert keyed.payload_digest.startswith("hmac-sha256:")
    assert keyed.payload_digest != digest_payload(guess)            # not confirmable unkeyed
    assert keyed.payload_digest != digest_payload(guess, key="other-key")
    assert keyed.payload_digest == digest_payload(guess, key="k" * 32)  # the key holder can
    assert keyed_trail.verify_integrity()


def test_digest_key_read_from_env_at_construction(monkeypatch):
    monkeypatch.setenv(DIGEST_KEY_ENV, "env-key")
    t = AuditTrail()
    e = t.record(trace_id="x", agent="A", action="a", action_class="c",
                 decision="APPROVE", payload={"q": 1})
    assert t.digest_keyed and e.payload_digest == digest_payload({"q": 1}, key="env-key")
    # An explicit key wins over the environment; an empty key counts as no key.
    assert AuditTrail(digest_key="explicit").digest_keyed is True
    assert AuditTrail(digest_key="")._digest_key is None


def test_legacy_bare_hex_entries_still_verify(tmp_path, monkeypatch):
    # Entries written before the label existed carry a bare 64-hex digest. The chain hash
    # covers the stored string as-is, so an old file loads, verifies, and can be appended to.
    import hashlib, json
    monkeypatch.delenv(DIGEST_KEY_ENV, raising=False)
    p = tmp_path / "audit.jsonl"
    legacy_digest = hashlib.sha256(json.dumps({"x": 1}, sort_keys=True,
                                              separators=(",", ":")).encode()).hexdigest()
    legacy = AuditEntry(seq=0, timestamp="2026-01-01T00:00:00+00:00", trace_id="t", agent="A",
                        action="a", action_class="c", decision="APPROVE", reasons=[],
                        payload_digest=legacy_digest, metadata={}, prev_hash="0" * 64)
    legacy = dataclasses.replace(legacy, entry_hash=legacy.compute_hash())
    p.write_text(legacy.to_json() + "\n", encoding="utf-8")
    t = AuditTrail(p)
    assert len(t) == 1 and t.verify_integrity()
    new = _rec(t)
    assert new.prev_hash == legacy.entry_hash and new.payload_digest.startswith("sha256:")
    assert AuditTrail(p).verify_integrity()


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
