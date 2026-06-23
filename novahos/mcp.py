"""MCP substrate + security BOUNDARY (Doc #26 §3). (Foundation; stdlib.)

Two layers:
  • Tool registry — every integration is a named Tool (JSON-schema input + callable); apps
    register tools and agents/connectors discover them uniformly.
  • MCPBoundary — the security gate Doc #26 §3 requires: only APPROVED servers connect, every
    call is logged to the immutable AuditTrail, credentials are stored ENCRYPTED, per-server
    rate limits stop runaway agents, and Tier-1 (PRIVATE) data NEVER routes to a cloud server.
    Custom one-off integrations are an anti-pattern; everything goes through this boundary.

The default ``KeystreamCredentialVault`` is stdlib (HMAC-SHA256 keystream in CTR with
encrypt-then-MAC — real encryption-at-rest with integrity). It is INJECTABLE: a production
deployment swaps in a vetted AEAD (AES-GCM via ``cryptography``, or a secrets manager) behind
the same ``CredentialVault`` protocol — keeping ``import novahos`` stdlib-clean.
"""
from __future__ import annotations

import base64
import hmac
import os
import threading
from collections import deque
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from enum import Enum
from hashlib import sha256
from typing import Any, Protocol, runtime_checkable

from novahos.audit_trail import AuditTrail
from novahos.warden_runtime.types import PrivacyTier


@dataclass
class Tool:
    name: str
    description: str
    input_schema: dict = field(default_factory=dict)
    handler: Callable | None = None
    consent_kind: str = "read"
    privacy_default: str = "semi"


class Registry:
    def __init__(self) -> None:
        self._tools: dict[str, Tool] = {}

    def register(self, tool: Tool) -> None:
        self._tools[tool.name] = tool

    def get(self, name: str) -> Tool | None:
        return self._tools.get(name)

    def list(self) -> list[Tool]:
        return list(self._tools.values())

    def manifest(self) -> list[dict]:
        return [
            {"name": t.name, "description": t.description, "input_schema": t.input_schema}
            for t in self._tools.values()
        ]


registry = Registry()


# ─────────────────────────── MCP security boundary (Doc #26 §3) ───────────────────────────


class MCPServerKind(Enum):
    LOCAL = "local"   # on-device / self-hosted — eligible to handle Tier 1 data
    CLOUD = "cloud"   # external — must never receive Tier 1 data


@dataclass(frozen=True)
class MCPServer:
    name: str
    kind: MCPServerKind
    rate_limit_per_hour: int = 300


# --- credential vault (injectable; default is stdlib) ---


@runtime_checkable
class CredentialVault(Protocol):
    def encrypt(self, plaintext: str) -> str: ...
    def decrypt(self, token: str) -> str: ...


class CredentialIntegrityError(Exception):
    """Raised when a stored credential's authentication tag fails to verify (tampering)."""


class KeystreamCredentialVault:
    """stdlib encrypt-then-MAC vault. Swap for a vetted AEAD (AES-GCM) in production."""

    def __init__(self, key: bytes) -> None:
        if len(key) < 16:
            raise ValueError("Vault key must be at least 16 bytes.")
        self._enc_key = hmac.new(key, b"novah-mcp-enc", sha256).digest()
        self._mac_key = hmac.new(key, b"novah-mcp-mac", sha256).digest()

    @classmethod
    def from_env(cls, var: str = "NOVAH_VAULT_KEY") -> "KeystreamCredentialVault":
        raw = os.environ.get(var)
        if not raw:
            raise ValueError(f"{var} is not set.")
        return cls(raw.encode("utf-8"))

    def _keystream(self, nonce: bytes, length: int) -> bytes:
        out = bytearray()
        counter = 0
        while len(out) < length:
            block = hmac.new(
                self._enc_key, nonce + counter.to_bytes(8, "big"), sha256
            ).digest()
            out.extend(block)
            counter += 1
        return bytes(out[:length])

    def encrypt(self, plaintext: str) -> str:
        nonce = os.urandom(16)
        data = plaintext.encode("utf-8")
        ct = bytes(b ^ k for b, k in zip(data, self._keystream(nonce, len(data)), strict=True))
        tag = hmac.new(self._mac_key, nonce + ct, sha256).digest()
        return base64.b64encode(nonce + ct + tag).decode("ascii")

    def decrypt(self, token: str) -> str:
        blob = base64.b64decode(token)
        nonce, ct, tag = blob[:16], blob[16:-32], blob[-32:]
        expected = hmac.new(self._mac_key, nonce + ct, sha256).digest()
        if not hmac.compare_digest(expected, tag):
            raise CredentialIntegrityError("MCP credential failed integrity check.")
        data = bytes(b ^ k for b, k in zip(ct, self._keystream(nonce, len(ct)), strict=True))
        return data.decode("utf-8")


# --- rate limiting ---


@dataclass
class _MCPRateLimiter:
    _events: dict[str, deque] = field(default_factory=dict)
    _lock: threading.Lock = field(default_factory=threading.Lock)

    def check_and_record(self, server: str, limit: int, now: datetime) -> bool:
        with self._lock:
            ev = self._events.setdefault(server, deque())
            hour_ago = now - timedelta(hours=1)
            while ev and ev[0] < hour_ago:
                ev.popleft()
            if len(ev) >= limit:
                return False
            ev.append(now)
            return True


# --- the boundary ---


@dataclass(frozen=True)
class MCPCallResult:
    allowed: bool
    server: str
    reasons: tuple[str, ...] = ()


class MCPBoundary:
    """Gate for all MCP connections and calls. Logs every call to the audit trail."""

    def __init__(self, *, audit_trail: AuditTrail, vault: CredentialVault | None = None) -> None:
        self._audit = audit_trail
        self._vault = vault
        self._servers: dict[str, MCPServer] = {}
        self._credentials: dict[str, str] = {}  # server -> ciphertext
        self._rate = _MCPRateLimiter()

    # server allowlist

    def approve_server(self, server: MCPServer) -> None:
        self._servers[server.name] = server

    def is_approved(self, name: str) -> bool:
        return name in self._servers

    # credentials (stored encrypted only)

    def store_credential(self, server: str, secret: str) -> None:
        if self._vault is None:
            raise ValueError("No CredentialVault configured; cannot store credentials.")
        if not self.is_approved(server):
            raise ValueError(f"Cannot store credential for unapproved server '{server}'.")
        self._credentials[server] = self._vault.encrypt(secret)

    def get_credential(self, server: str) -> str:
        if self._vault is None:
            raise ValueError("No CredentialVault configured.")
        return self._vault.decrypt(self._credentials[server])

    # the gate

    def guard_call(
        self,
        server: str,
        *,
        agent: str,
        operation: str,
        data_tier: PrivacyTier | None = None,
        payload: Any = None,
        now: datetime | None = None,
    ) -> MCPCallResult:
        """Authorize one MCP call. Every call — allowed or denied — is audited."""
        now = now or datetime.now(UTC)
        reasons: list[str] = []
        allowed = True

        srv = self._servers.get(server)
        if srv is None:
            allowed = False
            reasons.append(f"MCP server '{server}' is not approved.")
        else:
            if data_tier is PrivacyTier.TIER_1 and srv.kind is MCPServerKind.CLOUD:
                allowed = False
                reasons.append("Tier 1 (PRIVATE) data may not be sent to a cloud MCP server.")
            # Only consume rate-limit quota for calls not already denied above.
            if allowed and not self._rate.check_and_record(server, srv.rate_limit_per_hour, now):
                allowed = False
                reasons.append(
                    f"MCP rate limit exceeded for '{server}' ({srv.rate_limit_per_hour}/hour)."
                )

        self._audit.record(
            trace_id=f"mcp:{server}:{operation}",
            agent=agent,
            action=f"mcp_call:{operation}",
            action_class="mcp_call",
            decision="APPROVE" if allowed else "BLOCK",
            reasons=reasons,
            payload=payload,
            metadata={
                "server": server,
                "operation": operation,
                "data_tier": data_tier.name if data_tier else None,
            },
        )
        return MCPCallResult(allowed=allowed, server=server, reasons=tuple(reasons))
