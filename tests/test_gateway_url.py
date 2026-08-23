"""The gateway URL resolver refuses everything that would silently reach a vendor.

These are the refusals, not the happy path. Every one of them describes a configuration that
OTHERWISE WORKS — a call that succeeds, returns a completion, and bills someone, having gone
nowhere near the spend approval, the daily ceiling or the metered row. That is why they are
raises and not warnings: a warning is a decision to continue.

Stdlib-only and dependency-free on purpose, mirroring the module under test. novahos is a
library and `novahos[substrate]` is an extra, so these assertions have to hold in a host that
never installed litellm or pydantic-settings — the half-installed environment is exactly where
a missing guard would be least noticed.
"""
from __future__ import annotations

import pytest

from novahos.gateway_url import (
    CANONICAL_TOKEN_ENV,
    CANONICAL_URL_ENV,
    DEPRECATED_TOKEN_ENVS,
    DEPRECATED_URL_ENVS,
    GatewayMisconfigured,
    GatewayNotConfigured,
    base_url,
    messages_url,
    token,
)

GOOD = "https://gateway.example/llm"
GOOD_TOKEN = "lfgw_service_novahos_abc123"


def env(url: str | None = None, tok: str | None = None, **extra: str) -> dict:
    """An explicit env mapping, so no test can depend on the ambient process environment."""
    e: dict[str, str] = dict(extra)
    if url is not None:
        e[CANONICAL_URL_ENV] = url
    if tok is not None:
        e[CANONICAL_TOKEN_ENV] = tok
    return e


# ── absence is never permission ──────────────────────────────────────────────────────────

def test_unset_url_raises_rather_than_defaulting_to_a_vendor():
    with pytest.raises(GatewayNotConfigured) as ei:
        base_url(env())
    assert CANONICAL_URL_ENV in str(ei.value)


def test_unset_token_raises_and_says_it_is_not_the_vendor_key():
    with pytest.raises(GatewayNotConfigured) as ei:
        token(env(GOOD))
    assert "ANTHROPIC_API_KEY" in str(ei.value)


def test_empty_and_whitespace_url_count_as_unset():
    for raw in ("", "   ", "\t\n"):
        with pytest.raises(GatewayNotConfigured):
            base_url(env(raw))


# ── a rename that silently keeps working is a rename that never finishes ─────────────────

def test_deprecated_url_name_alone_raises_and_names_both():
    dep = DEPRECATED_URL_ENVS[0]
    with pytest.raises(GatewayNotConfigured) as ei:
        base_url({dep: GOOD})
    msg = str(ei.value)
    assert dep in msg and CANONICAL_URL_ENV in msg


def test_deprecated_url_name_is_never_used_as_a_value():
    """The refusal must not be a disguised fallback."""
    dep = DEPRECATED_URL_ENVS[0]
    with pytest.raises(GatewayNotConfigured):
        base_url({dep: "https://gateway.example/llm"})


def test_deprecated_token_name_alone_raises_and_names_both():
    dep = DEPRECATED_TOKEN_ENVS[0]
    with pytest.raises(GatewayNotConfigured) as ei:
        token({CANONICAL_URL_ENV: GOOD, dep: GOOD_TOKEN})
    msg = str(ei.value)
    assert dep in msg and CANONICAL_TOKEN_ENV in msg


def test_canonical_name_wins_when_both_are_set():
    assert base_url(env(GOOD, **{DEPRECATED_URL_ENVS[0]: "https://wrong.example/llm"})) == GOOD


# ── the load-bearing one: a gateway URL pointing at the vendor ───────────────────────────

@pytest.mark.parametrize("host", [
    "api.anthropic.com", "api.openai.com", "api.voyageai.com", "generativelanguage.googleapis.com",
])
def test_vendor_host_is_refused(host):
    """This config LOOKS correct and works. Nothing downstream can tell it apart from the
    gateway, so it has to be caught at the only place that still knows the difference."""
    with pytest.raises(GatewayMisconfigured) as ei:
        base_url(env(f"https://{host}/v1/messages"))
    assert host in str(ei.value)


def test_vendor_host_refused_case_insensitively():
    with pytest.raises(GatewayMisconfigured):
        base_url(env("https://API.Anthropic.COM/v1/messages"))


def test_vendor_shaped_token_is_refused():
    """The single most likely wrong paste, and it succeeds: the vendor accepts the key."""
    with pytest.raises(GatewayMisconfigured) as ei:
        token(env(GOOD, "sk-ant-api03-REDACTED-EXAMPLE"))
    assert CANONICAL_TOKEN_ENV in str(ei.value)


@pytest.mark.parametrize("tok", [
    "sk-ant-example", "sk-proj-example", "sk-or-example", "gsk_example", "pa-example",
])
def test_every_vendor_key_prefix_is_refused(tok):
    with pytest.raises(GatewayMisconfigured):
        token(env(GOOD, tok))


# ── transport and shape ─────────────────────────────────────────────────────────────────

def test_plain_http_to_a_remote_host_is_refused():
    """The gateway token and the prompt both cross that hop."""
    with pytest.raises(GatewayMisconfigured):
        base_url(env("http://gateway.example/llm"))


@pytest.mark.parametrize("host", ["localhost", "127.0.0.1"])
def test_plain_http_to_loopback_is_allowed_for_local_work(host):
    assert base_url(env(f"http://{host}:8000/llm")) == f"http://{host}:8000/llm"


@pytest.mark.parametrize("raw", ["ftp://gateway.example/llm", "gateway.example/llm", "/llm"])
def test_non_http_or_hostless_is_refused(raw):
    with pytest.raises(GatewayMisconfigured):
        base_url(env(raw))


# ── accepting a pasted old-form value, without ever trimming to nothing ──────────────────

@pytest.mark.parametrize("raw", [
    "https://gateway.example/llm",
    "https://gateway.example/llm/",
    "https://gateway.example/llm/v1",
    "https://gateway.example/llm/v1/",
    "https://gateway.example/llm/v1/messages",
    "https://gateway.example/llm/v1/messages/",
])
def test_old_form_values_are_trimmed_to_the_canonical_form(raw):
    """Pasting the full endpoint out of the docs is the obvious mistake, and trimming a known
    suffix is exact. Deciding whether to APPEND one would require knowing the client."""
    assert base_url(env(raw)) == GOOD


def test_trimming_never_produces_an_empty_host():
    with pytest.raises(GatewayMisconfigured):
        base_url(env("https:///v1/messages"))


def test_messages_url_appends_the_path_exactly_once():
    for raw in (GOOD, GOOD + "/v1", GOOD + "/v1/messages"):
        assert messages_url(env(raw)) == "https://gateway.example/llm/v1/messages"


def test_messages_url_is_base_url_plus_the_path():
    e = env(GOOD)
    assert messages_url(e) == base_url(e) + "/v1/messages"


def test_a_valid_token_passes_through_stripped():
    assert token(env(GOOD, f"  {GOOD_TOKEN}  ")) == GOOD_TOKEN


def test_mount_is_preserved_and_not_flattened_to_the_origin():
    """origin+MOUNT. Dropping the mount would 404 against the hub, which is fine, but silently
    dropping it while still looking configured is the class of bug this module exists for."""
    assert base_url(env("https://gateway.example/some/deep/mount/v1/messages")) == (
        "https://gateway.example/some/deep/mount")
