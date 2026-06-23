"""novahos.mcp — the MCP security boundary (Doc #26 §3).

Ported from NovahPrime/tests/compliance/test_mcp.py, adapted to the kernel. Proves: only
approved servers connect, every call (allow or deny) is logged to the immutable AuditTrail,
credentials are stored encrypted (round-trip + tamper detection), per-server rate limits are
enforced, and Tier-1 (PRIVATE) data is never sent to a cloud MCP server.
"""
from __future__ import annotations

from datetime import UTC, datetime

from novahos.audit_trail import AuditTrail
from novahos.mcp import (
    CredentialIntegrityError,
    KeystreamCredentialVault,
    MCPBoundary,
    MCPServer,
    MCPServerKind,
)
from novahos.warden_runtime.types import PrivacyTier


def _boundary() -> tuple[MCPBoundary, AuditTrail]:
    audit = AuditTrail()
    vault = KeystreamCredentialVault(b"unit-test-master-key-0123456789")
    mcp = MCPBoundary(audit_trail=audit, vault=vault)
    mcp.approve_server(MCPServer("gmail", MCPServerKind.CLOUD))
    mcp.approve_server(MCPServer("healthkit", MCPServerKind.LOCAL))
    return mcp, audit


def test_only_approved_servers_connect():
    mcp, _ = _boundary()
    assert mcp.is_approved("gmail")
    assert not mcp.is_approved("notion")
    result = mcp.guard_call("notion", agent="HERMES", operation="read")
    assert not result.allowed


def test_every_call_is_logged_and_immutable():
    mcp, audit = _boundary()
    mcp.guard_call("gmail", agent="IRIS", operation="list", data_tier=PrivacyTier.TIER_2)
    mcp.guard_call("notion", agent="HERMES", operation="read")  # blocked, still logged
    assert len(audit) == 2
    assert audit.verify_integrity()


def test_credentials_are_encrypted():
    mcp, _ = _boundary()
    mcp.store_credential("gmail", "oauth-secret-value")
    assert mcp._credentials["gmail"] != "oauth-secret-value"
    assert "oauth-secret-value" not in mcp._credentials["gmail"]
    assert mcp.get_credential("gmail") == "oauth-secret-value"


def test_credential_for_unapproved_server_refused():
    mcp, _ = _boundary()
    try:
        mcp.store_credential("notion", "x")
        assert False, "should refuse a credential for an unapproved server"
    except ValueError:
        pass


def test_credential_tampering_detected():
    vault = KeystreamCredentialVault(b"unit-test-master-key-0123456789")
    token = vault.encrypt("secret")
    tampered = token[:-6] + ("AAAAAA" if not token.endswith("AAAAAA") else "BBBBBB")
    try:
        vault.decrypt(tampered)
        assert False, "tampered credential should fail integrity check"
    except CredentialIntegrityError:
        pass


def test_rate_limits_enforced():
    audit = AuditTrail()
    vault = KeystreamCredentialVault(b"unit-test-master-key-0123456789")
    mcp = MCPBoundary(audit_trail=audit, vault=vault)
    mcp.approve_server(MCPServer("slow", MCPServerKind.LOCAL, rate_limit_per_hour=2))
    now = datetime.now(UTC)
    assert mcp.guard_call("slow", agent="A", operation="x", now=now).allowed
    assert mcp.guard_call("slow", agent="A", operation="x", now=now).allowed
    assert not mcp.guard_call("slow", agent="A", operation="x", now=now).allowed  # 3rd exceeds


def test_tier1_never_sent_to_cloud_server():
    mcp, _ = _boundary()
    blocked = mcp.guard_call("gmail", agent="HYGEIA", operation="upload", data_tier=PrivacyTier.TIER_1)
    assert not blocked.allowed
    allowed = mcp.guard_call("healthkit", agent="VITALS", operation="read", data_tier=PrivacyTier.TIER_1)
    assert allowed.allowed
