"""novahos.auth — tiered three-factor + continuous behavioral auth (Doc #26 §2.2).

Ported from NovahPrime/tests/compliance/test_authentication.py, adapted to the kernel
(the app-level config/auth_tiers.yaml mapping test is dropped — that lives in each app, not
the kernel). Proves: three distinct factor types, tier→factor-count mapping, passphrase
strength + salted-hash storage, catastrophic 3-factor + cooling delay, continuous behavioral
downgrade, recovery friction, and that AuthState satisfies the WARDEN AuthStateProvider protocol.
"""
from __future__ import annotations

from datetime import UTC, datetime, timedelta

from novahos.auth.continuous import ContinuousAuth
from novahos.auth.three_factor import (
    AuthAttempt,
    AuthSession,
    AuthState,
    CoolingDelay,
    FactorType,
    RecoveryProcess,
    ThreeFactorAuth,
    capability_tier,
)
from novahos.warden_runtime.types import ActionRequest, AuthTier


def _tfa() -> ThreeFactorAuth:
    tfa = ThreeFactorAuth(
        biometric_verifier=lambda s: s == "FACE",
        hardware_verifier=lambda a: a == "KEY",
    )
    tfa.register_passphrase("correct horse battery staple plus")
    tfa.register_recovery_seed("a b c d e f g h i j k l")
    return tfa


def test_three_distinct_factor_types_exist():
    assert {f for f in FactorType} == {
        FactorType.BIOMETRIC,
        FactorType.KNOWLEDGE,
        FactorType.HARDWARE_KEY,
    }


def test_tier_factor_counts():
    assert capability_tier(set()) is AuthTier.NONE
    assert capability_tier({FactorType.KNOWLEDGE}) is AuthTier.READ_ONLY
    assert capability_tier({FactorType.KNOWLEDGE, FactorType.BIOMETRIC}) is AuthTier.STANDARD
    three = {FactorType.KNOWLEDGE, FactorType.BIOMETRIC, FactorType.HARDWARE_KEY}
    assert capability_tier(three) is AuthTier.CATASTROPHIC


def test_passphrase_strength_enforced():
    tfa = ThreeFactorAuth()
    try:
        tfa.register_passphrase("too short")
        assert False, "weak passphrase should be rejected"
    except ValueError:
        pass


def test_secrets_are_never_stored_raw():
    tfa = _tfa()
    assert tfa.verify_passphrase("correct horse battery staple plus")
    assert not tfa.verify_passphrase("wrong wrong wrong wrong wrong")
    assert tfa._passphrase_hash.startswith("pbkdf2_sha256$")
    assert "correct horse" not in tfa._passphrase_hash


def test_catastrophic_requires_three_factors_plus_cooling():
    tfa = _tfa()
    factors = tfa.verify(AuthAttempt(passphrase="correct horse battery staple plus",
                                     biometric_sample="FACE", hardware_assertion="KEY"))
    assert capability_tier(factors) is AuthTier.CATASTROPHIC  # the 3-factor part

    cooling = CoolingDelay(delay=timedelta(hours=24))
    req = ActionRequest(agent="SENTINEL", action="wipe", action_class="irreversible")
    now = datetime.now(UTC)
    assert cooling.satisfied(req, now=now) is False                       # clock starts
    assert cooling.satisfied(req, now=now + timedelta(hours=23)) is False  # not yet
    assert cooling.satisfied(req, now=now + timedelta(hours=25)) is True   # elapsed


def test_continuous_authentication_active():
    ca = ContinuousAuth(threshold=0.7)
    ca.update_baseline({"typing_speed": 5.0, "dwell": 0.2})
    session = AuthSession()
    session.authenticate({FactorType.KNOWLEDGE, FactorType.BIOMETRIC})
    assert ca.evaluate({"typing_speed": 5.0, "dwell": 0.2}).ok
    # Anomalous behavior downgrades the session.
    result = ca.monitor(session, {"typing_speed": 0.05, "dwell": 9.0})
    assert not result.ok
    assert session.current_tier() is AuthTier.NONE


def test_session_expiry_drops_to_none():
    session = AuthSession(ttl=timedelta(hours=1))
    now = datetime.now(UTC)
    session.authenticate({FactorType.KNOWLEDGE, FactorType.BIOMETRIC}, now=now)
    assert session.current_tier(now=now) is AuthTier.STANDARD
    assert session.current_tier(now=now + timedelta(hours=2)) is AuthTier.NONE  # expired


def test_recovery_requires_identity_and_waiting_period():
    rp = RecoveryProcess(waiting_period=timedelta(hours=24))
    now = datetime.now(UTC)
    rp.initiate(now=now)
    assert not rp.can_recover(now=now)                          # no identity, no wait
    rp.verify_identity(True)
    assert not rp.can_recover(now=now + timedelta(hours=1))     # identity but not waited
    assert rp.can_recover(now=now + timedelta(hours=25))        # both satisfied


def test_authstate_satisfies_provider_protocol():
    """AuthState is a real, session-backed drop-in for StaticAuthStateProvider."""
    session = AuthSession()
    session.authenticate({FactorType.KNOWLEDGE})
    state = AuthState(session=session, required_map={"read_data": AuthTier.READ_ONLY})
    assert state.required_tier("read_data") is AuthTier.READ_ONLY
    assert state.required_tier("unmapped_action") is AuthTier.STANDARD  # default
    assert state.current_tier() is AuthTier.READ_ONLY
    # cooling_satisfied is part of the provider protocol the gate consumes.
    req = ActionRequest(agent="NOVAH", action="send", action_class="standard")
    assert state.cooling_satisfied(req) is False  # first sighting starts the clock
