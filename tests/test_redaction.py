"""Nothing secret reaches a table that cannot be edited afterwards.

WHY THIS MATTERS MORE THAN MOST REDACTION. `warden_audit_trail` revokes UPDATE and DELETE
at the database layer. That is correct for an audit trail and it is also what makes a
mistake here permanent: a token written into that table cannot be edited out, because the
statement that would do it does not exist for that table. It can only be dropped along with
the audit history it was hiding in.

So these tests are about a write that has no undo. `test_a_secret_is_never_written`
is the one that matters; the rest exist because the ways a secret sneaks past a redactor
are all boring and none of them are obvious:

  * under a compound key (`refresh_token`) that an exact-match list would miss
  * one level down, inside a dict the redactor recursed into
  * under an innocuous inner key, inside a dict whose OWN key was the secret one
  * stringified off a model object by a `str()` that was trying to be helpful

Runnable: pytest -q tests/test_redaction.py
"""
from __future__ import annotations

from novahos import redaction
from novahos.redaction import REDACTED, safe_payload


def _leaves(obj):
    """Every scalar in a nested structure, so a test can assert over all of them."""
    if isinstance(obj, dict):
        for v in obj.values():
            yield from _leaves(v)
    elif isinstance(obj, (list, tuple)):
        for v in obj:
            yield from _leaves(v)
    else:
        yield obj


# ── the assertion the module exists for ──────────────────────────────────────────────

def test_a_secret_is_never_written():
    """THE ONE THAT MATTERS. Every shape of secret-carrying key, at every depth, in one
    structure — and the literal must not survive anywhere in the output."""
    secret = "sk-ant-SUPER-SECRET-VALUE"
    payload = {
        "password": secret,
        "refresh_token": secret,
        "X-API-Key": secret,
        "Authorization": f"Bearer {secret}",
        "user_session_token": secret,
        "nested": {"private_key": secret, "deeper": {"access_token": secret}},
        "in_a_list": [{"cookie": secret}],
        "credentials": {"value": secret},
        "harmless": "fine",
    }
    out = safe_payload(payload)
    assert secret not in repr(out), "a secret survived redaction"
    assert out["harmless"] == "fine", "redaction ate a value it should have kept"


def test_compound_keys_are_caught_by_substring():
    """An exact-match list would miss every one of these, which is the whole reason the
    match is on substrings."""
    out = safe_payload({k: "x" for k in
                        ("refresh_token", "user_token", "x-api_key", "MY_PASSWORD",
                         "db_private_key", "Set-Cookie")})
    assert all(v == REDACTED for v in out.values())


def test_the_key_decides_before_the_recursion():
    """A dict under a secret-shaped key is redacted WHOLE rather than walked into.
    Otherwise `{"credentials": {"value": "..."}}` writes the secret out in full under an
    inner key that looks innocent."""
    out = safe_payload({"credentials": {"value": "hunter2", "note": "prod"}})
    assert out["credentials"] == REDACTED


def test_an_unknown_object_is_named_not_stringified():
    """`str()` on an arbitrary object is how a connection string ends up in an audit row —
    engines and sessions put their DSN in their repr."""
    class Engine:
        def __repr__(self):
            return "Engine(postgresql://user:hunter2@host/db)"

    out = safe_payload({"engine": Engine()})
    assert out["engine"] == "<Engine>"
    assert "hunter2" not in repr(out)


# ── keeping what an auditor actually needs ───────────────────────────────────────────

def test_structure_survives_instead_of_being_collapsed():
    """The deliberate difference from odyssey's `_safe_payload_summary`, which collapses
    any nested container. `detail` is the record of WHY a decision went the way it did,
    and `{"violations": "<list len=3>"}` has kept the shape and lost the finding."""
    out = safe_payload({"violations": ["no_consent", "over_budget", "rate_limited"],
                        "scores": {"risk": 71, "threshold": 30}})
    assert out["violations"] == ["no_consent", "over_budget", "rate_limited"]
    assert out["scores"] == {"risk": 71, "threshold": 30}


def test_scalars_pass_through_unchanged():
    payload = {"n": 71, "f": 1.5, "t": True, "f2": False, "none": None}
    assert safe_payload(payload) == payload


def test_false_and_none_are_preserved_distinctly():
    """None is not False, and an audit entry that confuses them is recording a different
    decision from the one that was made."""
    out = safe_payload({"allowed": False, "checked": None})
    assert out["allowed"] is False
    assert out["checked"] is None


def test_a_long_string_is_truncated_not_dropped():
    """An audit entry wants the shape of what was said, not a transcript — and a 40 KB
    prompt in an append-only table is its own problem."""
    out = safe_payload({"prompt": "a" * 5000})
    assert out["prompt"].endswith("…")
    assert len(out["prompt"]) < 250


# ── untrusted input must terminate ───────────────────────────────────────────────────

def test_a_cyclic_structure_terminates():
    """A redactor that hangs turns "we refused this action" into no entry at all."""
    d: dict = {"name": "loop"}
    d["self"] = d
    out = safe_payload(d)
    assert "loop" in repr(out)


def test_deep_nesting_is_capped():
    d: dict = {"v": "bottom"}
    for _ in range(50):
        d = {"next": d}
    assert "dict keys=" in repr(safe_payload(d))


def test_a_huge_container_is_capped_and_says_so():
    """Truncation that leaves no trace reads as a complete record that happens to be
    short."""
    out = safe_payload({"items": list(range(500))})
    assert "more items" in repr(out["items"])
    out2 = safe_payload({f"k{i}": i for i in range(500)})
    assert "more keys" in repr(out2)


def test_it_never_raises():
    """This sits in front of a write whose purpose is to leave a record. Throwing would
    replace an unredacted entry with no entry, which is worse."""
    class Hostile:
        def __iter__(self):
            raise RuntimeError("no")

        def __repr__(self):
            raise RuntimeError("no")

    assert safe_payload({"x": Hostile()}) is not None
    assert safe_payload(None) is None


# ── the result has to survive a JSONB column ─────────────────────────────────────────

def test_output_is_json_serialisable():
    """Both call sites hand the result straight to a JSONB column."""
    import json
    from datetime import datetime

    payload = {"when": datetime.now(), "set": {1, 2, 3}, "tuple": (1, "a"),
               "token": "secret", "nested": {"list": [datetime.now()]}}
    json.dumps(safe_payload(payload))   # must not raise


def test_is_secret_key_is_usable_on_its_own():
    assert redaction.is_secret_key("Authorization") is True
    assert redaction.is_secret_key("user_id") is False


def test_odysseys_key_list_is_carried_over_byte_for_byte():
    """The field-tested part, kept checkable. Quietly editing a security control's list is
    how two copies of it drift apart."""
    assert redaction.ODYSSEY_REDACT_KEYS == frozenset({
        "password", "passphrase", "passwd", "secret", "token", "api_key",
        "authorization", "cookie", "refresh_token", "access_token", "id_token",
        "session_token", "seed", "private_key",
    })


def test_the_kernel_only_ever_widens_the_list():
    """A denylist may be widened without weakening it. This asserts the direction."""
    assert redaction.ODYSSEY_REDACT_KEYS <= redaction.REDACT_KEYS


def test_hyphenated_header_forms_are_caught():
    """The list spells `api_key`; the wire spells it `X-API-Key`. A plain substring test
    misses the most common form of the most common secret header, and odyssey's version
    has exactly that blind spot."""
    for k in ("X-API-Key", "Refresh-Token", "Private-Key", "Api Key"):
        assert redaction.is_secret_key(k), k


def test_a_credential_shaped_value_is_caught_under_any_key():
    """A key-only denylist cannot see `{"data": {"value": "sk-ant-..."}}`. For a table
    with no UPDATE and no DELETE, the value-side check earns its keep."""
    out = safe_payload({"data": {"value": "sk-ant-api03-xyz"},
                        "hdr": "Bearer eyJhbGciOi",
                        "pem": "-----BEGIN PRIVATE KEY-----"})
    assert out["data"]["value"] == REDACTED
    assert out["hdr"] == REDACTED
    assert out["pem"] == REDACTED


def test_an_ordinary_string_is_not_mistaken_for_a_credential():
    """A guard that redacts normal content is one people route around."""
    out = safe_payload({"note": "we decided to hold this post", "id": "user-42"})
    assert out["note"] == "we decided to hold this post"
    assert out["id"] == "user-42"
