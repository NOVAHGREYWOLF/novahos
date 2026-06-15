"""Hash-chained audit trail — immutable, complete, tamper-evident. (Foundation; stdlib.)

Every WARDEN decision creates one entry (the runtime gate's step 7). The trail is append-only
and **hash-chained**: each entry binds the hash of the previous one, so any insertion, deletion,
or edit of history is detectable via `verify_integrity()`. There are deliberately no update or
delete operations — that is what makes the guarantee hold.

This is the in-process / file-backed canonical audit (pure stdlib, no DB). The DB persistence in
`novahos.warden_audit` (substrate) is a downstream adapter for durable storage + querying; this
module is what proves the chain wasn't tampered with.

Payloads are stored as SHA-256 digests, not raw content, so the trail never becomes a second
copy of sensitive data while still proving exactly what was acted on.

Ported into the kernel from the NovahPrime foundation as part of the consolidation (Phase 1).
"""
from __future__ import annotations

import hashlib
import json
import threading
from collections.abc import Iterator
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

GENESIS_HASH = "0" * 64


def _utc_now_iso() -> str:
    return datetime.now(UTC).isoformat()


def digest_payload(payload: Any) -> str:
    """Deterministic SHA-256 digest of an arbitrary JSON-serializable payload."""
    canonical = json.dumps(payload, sort_keys=True, default=str, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class AuditEntry:
    """A single immutable audit record.

    `entry_hash` is the chained hash over all other fields plus `prev_hash`. Frozen so an
    in-memory entry cannot be mutated after creation.
    """

    seq: int
    timestamp: str
    trace_id: str
    agent: str
    action: str
    action_class: str
    decision: str
    reasons: list[str]
    payload_digest: str
    metadata: dict[str, Any]
    prev_hash: str
    entry_hash: str = ""

    def _content_for_hash(self) -> dict[str, Any]:
        d = asdict(self)
        d.pop("entry_hash", None)
        return d

    def compute_hash(self) -> str:
        canonical = json.dumps(self._content_for_hash(), sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    def to_json(self) -> str:
        return json.dumps(asdict(self), sort_keys=True, separators=(",", ":"))

    @classmethod
    def from_json(cls, line: str) -> AuditEntry:
        return cls(**json.loads(line))


class AuditIntegrityError(Exception):
    """Raised when the audit trail's hash chain fails verification (tampering)."""


class AuditTrail:
    """Append-only, hash-chained audit log.

    Pass a file path for durable storage (JSONL, one entry per line) or None for an in-memory
    trail (tests). On construction with an existing file, the chain is loaded and verified;
    a corrupt or tampered file raises AuditIntegrityError.
    """

    def __init__(self, path: str | Path | None = None) -> None:
        self._path = Path(path) if path is not None else None
        self._entries: list[AuditEntry] = []
        self._lock = threading.Lock()
        if self._path is not None and self._path.exists():
            self._load_and_verify()
        elif self._path is not None:
            self._path.parent.mkdir(parents=True, exist_ok=True)

    # --- writing (append-only; no update/delete by design) ---

    def record(
        self,
        *,
        trace_id: str,
        agent: str,
        action: str,
        action_class: str,
        decision: str,
        reasons: list[str] | None = None,
        payload: Any = None,
        metadata: dict[str, Any] | None = None,
    ) -> AuditEntry:
        """Append one entry to the trail and return it. Thread-safe."""
        with self._lock:
            prev_hash = self._entries[-1].entry_hash if self._entries else GENESIS_HASH
            seq = len(self._entries)
            entry = AuditEntry(
                seq=seq,
                timestamp=_utc_now_iso(),
                trace_id=trace_id,
                agent=agent,
                action=action,
                action_class=action_class,
                decision=decision,
                reasons=list(reasons or []),
                payload_digest=digest_payload(payload),
                metadata=dict(metadata or {}),
                prev_hash=prev_hash,
            )
            entry = AuditEntry(**{**asdict(entry), "entry_hash": entry.compute_hash()})
            self._entries.append(entry)
            if self._path is not None:
                with self._path.open("a", encoding="utf-8") as fh:
                    fh.write(entry.to_json() + "\n")
                    fh.flush()
            return entry

    # --- reading / querying ---

    def __len__(self) -> int:
        return len(self._entries)

    def __iter__(self) -> Iterator[AuditEntry]:
        return iter(self._entries)

    def get(self, seq: int) -> AuditEntry:
        return self._entries[seq]

    def all(self) -> list[AuditEntry]:
        return list(self._entries)

    def explain(self, trace_id: str) -> list[AuditEntry]:
        """Every entry for a trace_id — answers "why did you do this?"."""
        return [e for e in self._entries if e.trace_id == trace_id]

    def query(
        self,
        *,
        agent: str | None = None,
        action_class: str | None = None,
        decision: str | None = None,
    ) -> list[AuditEntry]:
        out = self._entries
        if agent is not None:
            out = [e for e in out if e.agent == agent]
        if action_class is not None:
            out = [e for e in out if e.action_class == action_class]
        if decision is not None:
            out = [e for e in out if e.decision == decision]
        return list(out)

    # --- integrity ---

    def verify_integrity(self) -> bool:
        """Recompute the chain and confirm no entry was inserted, removed, or edited.

        Verifies the in-memory chain and, if file-backed, that the file matches it exactly.
        """
        if not self._verify_chain(self._entries):
            return False
        if self._path is not None and self._path.exists():
            on_disk = self._read_entries(self._path)
            if len(on_disk) != len(self._entries):
                return False
            if not self._verify_chain(on_disk):
                return False
            for a, b in zip(on_disk, self._entries, strict=True):
                if a.entry_hash != b.entry_hash:
                    return False
        return True

    @staticmethod
    def _verify_chain(entries: list[AuditEntry]) -> bool:
        prev = GENESIS_HASH
        for i, e in enumerate(entries):
            if e.seq != i:
                return False
            if e.prev_hash != prev:
                return False
            if e.entry_hash != e.compute_hash():
                return False
            prev = e.entry_hash
        return True

    @staticmethod
    def _read_entries(path: Path) -> list[AuditEntry]:
        with path.open("r", encoding="utf-8") as fh:
            return [AuditEntry.from_json(line) for line in fh if line.strip()]

    def _load_and_verify(self) -> None:
        assert self._path is not None
        self._entries = self._read_entries(self._path)
        if not self._verify_chain(self._entries):
            raise AuditIntegrityError(
                f"Audit trail at {self._path} failed integrity verification (tampering detected)."
            )
