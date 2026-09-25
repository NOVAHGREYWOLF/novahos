"""Strip secret-shaped values before anything writes them somewhere permanent.

WHY THIS IS IN THE KERNEL AND NOT IN A SERVICE
──────────────────────────────────────────────
`warden_audit.write` puts its `detail` dict, and `write_risk_score` its `inputs` dict,
straight into `warden_audit_trail` and `risk_scores`. That first table revokes UPDATE and
DELETE at the database layer — it is append-only on purpose, which is exactly what you
want from an audit trail and exactly what makes it the worst possible place to put a
token. A secret written there cannot be edited out afterwards. It can only be dropped with
the table.

Odyssey already had this function, as `_safe_payload_summary` in its private WARDEN fork,
and used it before writing its own audit entries. The kernel — which every arm depends on
— did not. So the protection existed in the one repository that had built its own way
around the kernel, and was missing from every service that used the kernel as intended.
That is the wrong way round, and porting it upward is the whole point of this module.

WHAT IT DOES DIFFERENTLY FROM ODYSSEY'S VERSION
───────────────────────────────────────────────
Odyssey's collapses any nested container to `<dict keys=3>` or `<list len=5>`. That is
safe — a secret two levels down is never written because nothing two levels down is ever
written — and it is right for its original job, summarising an arbitrary action payload
for a log line.

It is wrong for an audit trail. `detail` is the RECORD OF WHY A DECISION WENT THE WAY IT
DID, and an audit entry reading `{"violations": "<list len=3>"}` has kept the shape and
thrown away the finding. So this recurses instead, redacting at every level, which is
strictly safer than collapsing (no secret survives at any depth) while keeping the
structure an auditor actually needs.

Recursion is capped, because the input is untrusted: past `_MAX_DEPTH` a container is
collapsed the way odyssey's does it, and a self-referential dict therefore terminates
rather than hanging the writer that was trying to record a refusal.

NEVER RAISES. This sits in front of a write whose whole purpose is to leave a record. A
redactor that throws turns "we refused this action" into no entry at all, which is a worse
outcome than an unredacted one — so anything unexpected degrades to a type name.
"""
from __future__ import annotations

from typing import Any

#: Odyssey's list, byte for byte. This is the field-tested part and it is kept separate so
#: the provenance is checkable: a test asserts it still matches the fork's, because quietly
#: editing a security control's list is how two copies of it drift apart.
ODYSSEY_REDACT_KEYS: frozenset[str] = frozenset({
    "password", "passphrase", "passwd", "secret", "token", "api_key",
    "authorization", "cookie", "refresh_token", "access_token", "id_token",
    "session_token", "seed", "private_key",
})

#: Added here, and only ever ADDED — a denylist may be widened without weakening it.
#:
#: `credential` is not in odyssey's list, and it did not need to be: that version collapses
#: any nested dict to `<dict keys=N>`, so `{"credentials": {"value": "..."}}` was safe by
#: accident. This module recurses instead (see the module docstring on why), which is more
#: useful and removes that accident — so the key has to be named explicitly.
KERNEL_REDACT_KEYS: frozenset[str] = frozenset({"credential"})

REDACT_KEYS: frozenset[str] = ODYSSEY_REDACT_KEYS | KERNEL_REDACT_KEYS

#: Values that are credential-shaped whatever they are filed under. A key-only denylist
#: cannot catch `{"data": {"value": "sk-ant-..."}}`, and for a table with no UPDATE and no
#: DELETE, one cheap check on the value side is worth having. These are the prefixes
#: `gateway_url._VENDOR_KEY_PREFIXES` already names, plus the one header form that carries
#: a bearer token in the value rather than the key.
_SECRET_VALUE_PREFIXES = ("sk-ant-", "sk-proj-", "sk-or-", "sk-live-", "sk_live_",
                          "gsk_", "pa-", "ghp_", "gho_", "github_pat_", "bearer ",
                          "-----begin")

REDACTED = "[REDACTED]"

#: Long strings are truncated rather than dropped: an audit entry wants the shape of what
#: was said, not a transcript, and a 40 KB prompt in an append-only table is its own problem.
_MAX_STR = 200

#: Past this depth a container is collapsed instead of recursed. Untrusted input can be
#: deep or cyclic, and the writer must terminate.
_MAX_DEPTH = 6

#: Caps on how much of a container is kept, for the same reason.
_MAX_KEYS = 64
_MAX_ITEMS = 32


def safe_payload(payload: Any, *, _depth: int = 0) -> Any:
    """A copy of `payload` with every secret-shaped value replaced by ``[REDACTED]``.

    Safe to call on anything. Returns a plain JSON-serialisable structure, so the result
    can go straight into a JSONB column.
    """
    try:
        return _walk(payload, _depth)
    except Exception:  # noqa: BLE001 — see the module docstring: never break the record
        return f"<unredactable {type(payload).__name__}>"


def is_secret_key(key: Any) -> bool:
    """Would a value under this key be redacted? Exposed so a caller can check a single
    field without building a dict to pass through `safe_payload`.

    SEPARATORS ARE NORMALISED, and that is not cosmetic. The list spells `api_key` with an
    underscore while the wire spells it `X-API-Key` with a hyphen, so a plain substring
    test misses the single most common form of the most common secret header. Odyssey's
    version has the same blind spot. Normalising here fixes it without touching the list.
    """
    low = str(key).lower().replace("-", "_").replace(" ", "_")
    return any(s in low for s in REDACT_KEYS)


def is_secret_value(v: Any) -> bool:
    """Does this value announce itself as a credential regardless of its key?"""
    if not isinstance(v, str):
        return False
    low = v.lstrip().lower()
    return any(low.startswith(p) for p in _SECRET_VALUE_PREFIXES)


def _walk(v: Any, depth: int) -> Any:
    if v is None or isinstance(v, (int, float, bool)):
        return v
    if isinstance(v, str):
        if is_secret_value(v):
            return REDACTED
        return v if len(v) <= _MAX_STR else v[:_MAX_STR] + "…"
    if isinstance(v, dict):
        if depth >= _MAX_DEPTH:
            return f"<dict keys={len(v)}>"
        out: dict[str, Any] = {}
        for i, (k, val) in enumerate(v.items()):
            if i >= _MAX_KEYS:
                out["…"] = f"<{len(v) - _MAX_KEYS} more keys>"
                break
            # THE KEY DECIDES, NOT THE VALUE, and it decides before the recursion. A dict
            # sitting under `credentials` is redacted whole rather than walked into --
            # otherwise a secret stored under an innocuous inner key ({"credentials":
            # {"value": "..."}}) would be written out in full.
            out[str(k)] = REDACTED if is_secret_key(k) else _walk(val, depth + 1)
        return out
    if isinstance(v, (list, tuple, set)):
        if depth >= _MAX_DEPTH:
            return f"<{type(v).__name__} len={len(v)}>"
        items = list(v)[:_MAX_ITEMS]
        out_l = [_walk(i, depth + 1) for i in items]
        if len(v) > _MAX_ITEMS:
            out_l.append(f"<{len(v) - _MAX_ITEMS} more items>")
        return out_l
    # Anything else (a model object, a datetime, a file handle) is named, never rendered.
    # `str()` on an arbitrary object is how a connection string ends up in an audit row.
    return f"<{type(v).__name__}>"
