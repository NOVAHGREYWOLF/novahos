"""novahos never reaches a model vendor directly — including with the host's key in hand.

This is the proof for the TRANSITIVE door. novahos is a library pinned into nine host
processes, and before this change it called litellm with no credential of its own. That is not
the same as having no credential: litellm resolves both the key and `api_base` from the AMBIENT
process environment and both chains end at the vendor, so the library spent whatever its host
was holding. A host that deleted its own ANTHROPIC_API_KEY and imported this library had not
closed its door — it had moved it one import deeper.

The load-bearing assertions here are the NEGATIVE ones: when the gateway is unconfigured,
nothing is sent. Not a call that fails, not a call to a vendor that succeeds — no call at all.
The fake below records every invocation precisely so that "no call happened" is an assertion
rather than an assumption. A regression that reintroduces a direct call shows up as a recorded
call with no `api_base`, not as a real request to anyone.

Skipped where the substrate extra is absent: `novahos.llm` imports litellm and
pydantic-settings at module scope, so there is nothing to test in a foundation-only install.
The refusals themselves are covered dependency-free in test_gateway_url.py, which always runs.
"""
from __future__ import annotations

import pytest

pytest.importorskip("litellm", reason="novahos[substrate] not installed")
pytest.importorskip("pydantic_settings", reason="novahos[substrate] not installed")

from novahos import llm  # noqa: E402
from novahos.gateway_url import (  # noqa: E402
    CANONICAL_TOKEN_ENV,
    CANONICAL_URL_ENV,
    GatewayMisconfigured,
    GatewayNotConfigured,
)

GATEWAY = "https://gateway.example/llm"
MESSAGES = "https://gateway.example/llm/v1/messages"
TOKEN = "lfgw_service_novahos_abc123"
# Shaped like the vendor key, and deliberately not one. The check under test is prefix-only.
VENDOR_KEY = "sk-ant-api03-EXAMPLE-NOT-A-REAL-KEY"


def _fake_response():
    """Just enough of a litellm response for reason()/classify() and the meter."""
    message = type("Message", (), {"content": "ok"})()
    choice = type("Choice", (), {"message": message})()
    return type("Response", (), {
        "choices": [choice],
        "usage": {"prompt_tokens": 11, "completion_tokens": 7},
        "model": "claude-opus-4-8",
    })()


class FakeLiteLLM:
    """Records every call instead of making one. A vendor call would be a recorded call."""

    def __init__(self) -> None:
        self.calls: list[dict] = []

    async def acompletion(self, **kwargs):
        self.calls.append(kwargs)
        return _fake_response()

    def completion_cost(self, **_kwargs):
        return 0.0


@pytest.fixture
def fake(monkeypatch):
    """A recording litellm, a cleared gateway config, and no shared ledger.

    Every gateway-related variable is deleted explicitly rather than assumed absent, so a
    developer who has a real gateway (or a real vendor key) in their own shell can never make a
    fail-closed test pass by accident."""
    f = FakeLiteLLM()
    monkeypatch.setattr(llm, "litellm", f)
    for var in (CANONICAL_URL_ENV, CANONICAL_TOKEN_ENV, "NOVAH_LLM_GATEWAY_URL",
                "NOVAH_LLM_GATEWAY_TOKEN", "ANTHROPIC_API_KEY", "ANTHROPIC_API_BASE",
                "ANTHROPIC_BASE_URL", "SHARED_DATABASE_URL"):
        monkeypatch.delenv(var, raising=False)
    llm._gateway_override.clear()
    llm.set_account(None)
    llm.set_trigger(None)
    monkeypatch.setattr(llm, "_warned_host_key", False)
    yield f
    llm._gateway_override.clear()
    llm.set_account(None)
    llm.set_trigger(None)


def configured(monkeypatch):
    monkeypatch.setenv(CANONICAL_URL_ENV, GATEWAY)
    monkeypatch.setenv(CANONICAL_TOKEN_ENV, TOKEN)


# ── unconfigured means no call at all ────────────────────────────────────────────────────

async def test_reason_raises_and_sends_nothing_when_the_gateway_is_unset(fake):
    with pytest.raises(GatewayNotConfigured):
        await llm.reason("sys", "user")
    assert fake.calls == [], "a model call was attempted with no gateway configured"


async def test_classify_raises_and_sends_nothing_when_the_gateway_is_unset(fake):
    with pytest.raises(GatewayNotConfigured):
        await llm.classify("prompt")
    assert fake.calls == []


async def test_url_without_token_still_sends_nothing(fake, monkeypatch):
    monkeypatch.setenv(CANONICAL_URL_ENV, GATEWAY)
    with pytest.raises(GatewayNotConfigured):
        await llm.reason("sys", "user")
    assert fake.calls == []


async def test_token_without_url_still_sends_nothing(fake, monkeypatch):
    monkeypatch.setenv(CANONICAL_TOKEN_ENV, TOKEN)
    with pytest.raises(GatewayNotConfigured):
        await llm.reason("sys", "user")
    assert fake.calls == []


async def test_whitespace_is_not_configuration(fake, monkeypatch):
    """A Railway variable set to an empty-looking string is unset, not configured."""
    monkeypatch.setenv(CANONICAL_URL_ENV, "   ")
    monkeypatch.setenv(CANONICAL_TOKEN_ENV, "\t")
    with pytest.raises(GatewayNotConfigured):
        await llm.classify("prompt")
    assert fake.calls == []


async def test_the_hosts_vendor_key_does_not_enable_the_call(fake, monkeypatch):
    """THE TRANSITIVE-DOOR PROOF, and the reason this file exists.

    A host process still carrying ANTHROPIC_API_KEY is the situation every consumer is in
    until its own migration is deployed. Before this change litellm picked that key up out of
    the ambient environment and went straight to the vendor, and nothing in this repo mentioned
    the variable at all. The library has to refuse on its own account, not on its host's."""
    monkeypatch.setenv("ANTHROPIC_API_KEY", VENDOR_KEY)
    with pytest.raises(GatewayNotConfigured):
        await llm.reason("sys", "user")
    assert fake.calls == [], "the host's vendor key was enough to make a call happen"


async def test_a_host_base_url_env_var_does_not_enable_the_call(fake, monkeypatch):
    """The env vars litellm reads are the LAST fallback before the hardcoded vendor URL, so
    they are exactly what a well-meaning host would set and exactly what must not be trusted
    as configuration for this library."""
    monkeypatch.setenv("ANTHROPIC_API_KEY", VENDOR_KEY)
    monkeypatch.setenv("ANTHROPIC_BASE_URL", GATEWAY)
    with pytest.raises(GatewayNotConfigured):
        await llm.reason("sys", "user")
    assert fake.calls == []


async def test_a_gateway_url_pointing_at_the_vendor_sends_nothing(fake, monkeypatch):
    """The load-bearing misconfiguration: it LOOKS configured and it WORKS, unmetered."""
    monkeypatch.setenv(CANONICAL_URL_ENV, "https://api.anthropic.com")
    monkeypatch.setenv(CANONICAL_TOKEN_ENV, TOKEN)
    with pytest.raises(GatewayMisconfigured):
        await llm.reason("sys", "user")
    assert fake.calls == []


async def test_a_vendor_shaped_token_sends_nothing(fake, monkeypatch):
    monkeypatch.setenv(CANONICAL_URL_ENV, GATEWAY)
    monkeypatch.setenv(CANONICAL_TOKEN_ENV, VENDOR_KEY)
    with pytest.raises(GatewayMisconfigured):
        await llm.reason("sys", "user")
    assert fake.calls == []


async def test_the_deprecated_variable_name_alone_sends_nothing(fake, monkeypatch):
    """A rename that silently keeps working is a rename that never finishes."""
    monkeypatch.setenv("NOVAH_LLM_GATEWAY_URL", GATEWAY)
    monkeypatch.setenv(CANONICAL_TOKEN_ENV, TOKEN)
    with pytest.raises(GatewayNotConfigured):
        await llm.reason("sys", "user")
    assert fake.calls == []


# ── configured means every call is pinned, per call ──────────────────────────────────────

async def test_reason_pins_api_base_and_api_key_on_the_call_itself(fake, monkeypatch):
    configured(monkeypatch)
    assert await llm.reason("sys", "user") == "ok"
    call = fake.calls[0]
    assert call["api_base"] == MESSAGES
    assert call["api_key"] == TOKEN


async def test_classify_pins_api_base_and_api_key_on_the_call_itself(fake, monkeypatch):
    configured(monkeypatch)
    assert await llm.classify("prompt") == "ok"
    call = fake.calls[0]
    assert call["api_base"] == MESSAGES
    assert call["api_key"] == TOKEN


async def test_the_full_messages_path_is_sent_not_the_bare_mount(fake, monkeypatch):
    """litellm 1.98 appends /v1/messages when it is missing, but the floor in pyproject.toml is
    1.40 and versions below 1.45 append nothing. The full path is the only value correct across
    the whole supported range, so this asserts the append happens HERE rather than downstream."""
    configured(monkeypatch)
    await llm.reason("sys", "user")
    assert fake.calls[0]["api_base"].endswith("/v1/messages")


async def test_an_old_form_url_is_trimmed_rather_than_doubled(fake, monkeypatch):
    """Pasting the full endpoint out of the gateway docs is the obvious mistake; it must not
    produce /llm/v1/messages/v1/messages."""
    monkeypatch.setenv(CANONICAL_URL_ENV, MESSAGES)
    monkeypatch.setenv(CANONICAL_TOKEN_ENV, TOKEN)
    await llm.reason("sys", "user")
    assert fake.calls[0]["api_base"] == MESSAGES


async def test_the_provider_prefix_is_forced_rather_than_inferred(fake, monkeypatch):
    """Pins provider resolution to the id we send instead of the installed version's model
    table. Both configured defaults resolve without it on litellm 1.98, but the ids are
    host-overridable via REASONING_MODEL and the supported floor is 1.40."""
    configured(monkeypatch)
    await llm.reason("sys", "user")
    assert fake.calls[0]["model"].startswith("anthropic/")


async def test_the_account_is_named_to_the_gateway_when_one_is_set(fake, monkeypatch):
    """So the hub's approval email says WHO wanted the spend, not merely that something did."""
    configured(monkeypatch)
    llm.set_account("Someone@Example.com")
    await llm.reason("sys", "user")
    assert fake.calls[0]["extra_headers"] == {"X-Acting-Email": "someone@example.com"}


async def test_no_acting_header_when_no_account_is_set(fake, monkeypatch):
    configured(monkeypatch)
    await llm.reason("sys", "user")
    assert "extra_headers" not in fake.calls[0]


async def test_the_trigger_is_named_to_the_gateway_when_one_is_set(fake, monkeypatch):
    """So the daily ceiling can refuse a cron sweep without ever refusing a person.

    Without X-Trigger every kernel call looks the same to the ceiling, and its only choices
    are to refuse both or neither. instagram-outreach has sent this since the door opened."""
    configured(monkeypatch)
    llm.set_trigger("cron")
    await llm.reason("sys", "user")
    assert fake.calls[0]["extra_headers"] == {"X-Trigger": "cron"}


async def test_the_account_and_the_trigger_are_sent_together(fake, monkeypatch):
    """WHO and WHAT-set-it-off are independent: neither may displace the other."""
    configured(monkeypatch)
    llm.set_account("Someone@Example.com")
    llm.set_trigger("cron")
    await llm.reason("sys", "user")
    assert fake.calls[0]["extra_headers"] == {"X-Acting-Email": "someone@example.com",
                                              "X-Trigger": "cron"}


async def test_no_trigger_header_when_none_is_set(fake, monkeypatch):
    """Unset stays unset: the gateway keeps its own default, so this is additive and can
    never turn into a new refusal for a caller that never set a trigger."""
    configured(monkeypatch)
    llm.set_account("someone@example.com")
    await llm.reason("sys", "user")
    assert "X-Trigger" not in fake.calls[0]["extra_headers"]


async def test_whitespace_is_not_a_trigger(fake, monkeypatch):
    """Mirrors the gateway config rule: a blank value is absence, not a value."""
    configured(monkeypatch)
    llm.set_trigger("   ")
    await llm.reason("sys", "user")
    assert "extra_headers" not in fake.calls[0]


async def test_the_trigger_does_not_unlock_an_unconfigured_gateway(fake):
    """Attribution is not authorisation — naming a cause must not open the door."""
    llm.set_trigger("cron")
    with pytest.raises(llm.GatewayNotConfigured):
        await llm.reason("sys", "user")
    assert fake.calls == []


async def test_the_gateway_token_is_never_smuggled_in_as_a_caller_header(fake, monkeypatch):
    """Caller headers win litellm's merge, so an x-api-key here would override the gateway
    token with whatever was passed — turning the door into a suggestion."""
    configured(monkeypatch)
    llm.set_account("someone@example.com")
    await llm.reason("sys", "user")
    headers = {k.lower() for k in fake.calls[0].get("extra_headers", {})}
    assert "x-api-key" not in headers and "authorization" not in headers


async def test_metering_still_records_the_configured_model_not_the_routed_id(fake, monkeypatch):
    """Ledger rows keep the shape every existing report and reconciliation already reads."""
    configured(monkeypatch)
    seen = {}

    async def _spy(resp, model, task):
        seen["model"] = model

    monkeypatch.setattr(llm, "_meter", _spy)
    await llm.reason("sys", "user")
    assert seen["model"] == llm.settings.reasoning_model
    assert not seen["model"].startswith("anthropic/")


# ── the host's own infra is never dragged through the door ───────────────────────────────

@pytest.mark.parametrize("model", ["ollama/llama3.1", "ollama_chat/llama3.1"])
async def test_a_self_hosted_model_needs_no_gateway_and_is_not_redirected(fake, monkeypatch, model):
    """A host may point REASONING_MODEL at its own box. Pinning that at the gateway would push
    text the host deliberately kept local out to a vendor — the inversion of why it chose a
    local model. Note the gateway is UNCONFIGURED here and the call still succeeds."""
    monkeypatch.setattr(llm.settings, "reasoning_model", model)
    assert await llm.reason("sys", "user") == "ok"
    call = fake.calls[0]
    assert call["model"] == model
    assert "api_base" not in call and "api_key" not in call


def test_an_unknown_model_prefix_is_treated_as_cloud_and_fails_closed():
    """Fail closed on the unknown: a provider prefix nobody has seen before is not assumed
    local, because assuming local is the assumption that transmits."""
    assert llm.is_self_hosted("ollama/llama3.1") is True
    assert llm.is_self_hosted("ollama_chat/llama3.1") is True
    assert llm.is_self_hosted("claude-opus-4-8") is False
    assert llm.is_self_hosted("some-new-provider/model") is False
    assert llm.is_self_hosted("") is False


# ── the in-process configuration seam is a convenience, never a bypass ───────────────────

async def test_configure_gateway_works_without_touching_the_environment(fake):
    llm.configure_gateway(url=GATEWAY, token=TOKEN)
    await llm.reason("sys", "user")
    assert fake.calls[0]["api_base"] == MESSAGES
    assert fake.calls[0]["api_key"] == TOKEN


async def test_configure_gateway_cannot_smuggle_in_a_vendor_url(fake):
    llm.configure_gateway(url="https://api.anthropic.com", token=TOKEN)
    with pytest.raises(GatewayMisconfigured):
        await llm.reason("sys", "user")
    assert fake.calls == []


async def test_configure_gateway_cannot_smuggle_in_a_vendor_key(fake):
    llm.configure_gateway(url=GATEWAY, token=VENDOR_KEY)
    with pytest.raises(GatewayMisconfigured):
        await llm.reason("sys", "user")
    assert fake.calls == []


async def test_clearing_an_override_falls_back_to_the_environment_not_to_a_vendor(fake):
    llm.configure_gateway(url=GATEWAY, token=TOKEN)
    llm.configure_gateway(url="", token="")
    with pytest.raises(GatewayNotConfigured):
        await llm.reason("sys", "user")
    assert fake.calls == []
