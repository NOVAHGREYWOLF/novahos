"""Channel registry + AgentContext: one PUBLISHER serving many channels. No network."""
import pytest

from novahos.channels import registry
from novahos.channels.base import AccountRef, MediaRef
from novahos.channels.instagram.assisted import InstagramAssisted
from novahos.channels.instagram.autonomous import InstagramAutonomous
from novahos.channels.instagram.official import InstagramOfficial
from novahos.channels.linkedin import LinkedInBackend
from novahos.context import AgentContext


class _Acc:
    def __init__(self, channel="instagram", mode="official"):
        self.id = "a1"; self.handle = "x"; self.channel = channel; self.compliance_mode = mode
        self.ig_user_id = None; self.auth = {}


def _ctx(channel="instagram", mode="official"):
    return AgentContext(app="instagram_presence", channel=channel, user_id="u1", account=_Acc(channel, mode))


def test_registry_resolves_instagram_modes():
    assert isinstance(registry.resolve(_ctx(mode="official")), InstagramOfficial)
    assert isinstance(registry.resolve(_ctx(mode="assisted")), InstagramAssisted)
    assert isinstance(registry.resolve(_ctx(mode="autonomous")), InstagramAutonomous)


def test_registry_resolves_other_channel():
    assert isinstance(registry.resolve(_ctx(channel="linkedin")), LinkedInBackend)


def test_context_exposes_compliance_mode():
    assert _ctx(mode="assisted").compliance_mode == "assisted"


def test_risk_floors_increase_with_mode():
    assert InstagramOfficial().risk_floor == 0
    assert InstagramAssisted().risk_floor == 30
    assert InstagramAutonomous().risk_floor == 70


def test_capabilities():
    off = InstagramOfficial()
    assert off.supports("publish_reel") and off.supports("read_insights")
    assert not off.supports("engage") and not off.supports("cold_dm")
    assert InstagramAssisted().supports("engage")


@pytest.mark.asyncio
async def test_official_publish_dry_run_without_credentials():
    res = await InstagramOfficial().publish(
        AccountRef(id="1", handle="x", channel="instagram", ig_user_id=None, auth={}),
        MediaRef(kind="reel", url="https://example.com/v.mp4"), "hi", kind="reel")
    assert res.status == "dry_run"


@pytest.mark.asyncio
async def test_autonomous_is_inert():
    res = await InstagramAutonomous().publish(
        AccountRef(id="1", handle="x", channel="instagram", ig_user_id="123", auth={}),
        MediaRef(kind="reel"), "hi", kind="reel")
    assert res.status == "failed" and any("AUTONOMOUS" in w for w in res.warnings)


@pytest.mark.asyncio
async def test_linkedin_stub_dry_run():
    res = await LinkedInBackend().publish(
        AccountRef(id="1", handle="x", channel="linkedin", auth={}), MediaRef(kind="post"), "hi", kind="post")
    assert res.status == "dry_run"
