"""The four-tier privacy ladder, and the reason LOCAL_ONLY had to exist.

The home-node design (§S14) makes replication an EGRESS decision: one logical brain replicates
to every node, and one of those nodes is rented. `private` replicating by default would put a
person's iMessages on someone else's computer. LOCAL_ONLY is the tier that never leaves.
"""
import pytest

from novahos import privacy
from novahos.warden_runtime.adapters import NovahosPrivacyClassifier
from novahos.warden_runtime.types import PrivacyTier


def test_ladder_is_ordered_strictest_first():
    assert privacy.TIERS == (privacy.LOCAL_ONLY, privacy.PRIVATE, privacy.SEMI, privacy.PUBLIC)


@pytest.mark.parametrize("source", ["imessage", "messages", "whatsapp", "signal", "sms"])
def test_intimate_comms_classify_local_only(source):
    assert privacy.classify(source) == privacy.LOCAL_ONLY


def test_existing_tiers_are_unchanged():
    """LOCAL_ONLY is additive: nothing that used to classify PRIVATE/SEMI/PUBLIC moved."""
    assert privacy.classify("plaid", "financial", "Whole Foods amount 42") == privacy.PRIVATE
    assert privacy.classify("applehealth") == privacy.PRIVATE
    assert privacy.classify("gmail", "email") == privacy.SEMI
    assert privacy.classify("blog", "published_post") == privacy.PUBLIC
    assert privacy.classify("notion", "note", "my ssn is 1234") == privacy.PRIVATE


def test_local_only_refuses_every_route_off_the_machine():
    t = privacy.LOCAL_ONLY
    assert privacy.may_send_to_third_party(t) is False
    assert privacy.may_use_cloud_model(t) is False
    assert privacy.may_leave_machine(t) is False
    assert privacy.may_replicate_to_node(t, node_is_local=False) is False
    assert privacy.may_replicate_to_node(t, node_is_local=True) is True


def test_private_may_still_replicate_to_a_local_node_but_not_a_remote_one():
    """The distinction that earns LOCAL_ONLY its keep: PRIVATE is 'no third party', which is not
    the same claim as 'never leaves this machine'."""
    assert privacy.may_leave_machine(privacy.PRIVATE) is True
    assert privacy.may_replicate_to_node(privacy.PRIVATE, node_is_local=True) is True
    assert privacy.may_replicate_to_node(privacy.PRIVATE, node_is_local=False) is True
    assert privacy.may_send_to_third_party(privacy.PRIVATE) is False


def test_gates_are_allowlists_so_an_unknown_tier_is_refused():
    """The regression this whole change exists to prevent. `tier != PRIVATE` passed anything it
    had not heard of, so adding a stricter tier would have silently ALLOWED it everywhere. Every
    gate must refuse a tier it does not recognise rather than wave it through."""
    for bogus in ("", "tier-4", "unknown", None):
        assert privacy.may_send_to_third_party(bogus) is False
        assert privacy.may_use_cloud_model(bogus) is False
        assert privacy.may_leave_machine(bogus) is False
        assert privacy.may_replicate_to_node(bogus, node_is_local=False) is False
        assert privacy.may_replicate_to_node(bogus, node_is_local=True) is False


def test_runtime_warden_maps_local_only_to_the_strictest_enum():
    assert NovahosPrivacyClassifier().classify("intimate") is PrivacyTier.TIER_1


def test_lean_warden_blocks_local_only_to_a_third_party():
    """`action.privacy_tier == PRIVATE` would NOT have matched local_only, so this send was
    allowed before the allowlist fix."""
    from novahos.warden import BLOCK, Action, evaluate

    d = evaluate(Action(kind="send_email", privacy_tier=privacy.LOCAL_ONLY,
                        destination="third_party", authed=True, approved=True))
    assert d.verdict == BLOCK
    assert "third party" in d.reason
