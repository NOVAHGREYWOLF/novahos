"""Sources layer + CROESUS — registry, graceful pulls, privacy posture, capability manifest."""
import asyncio

from novahos import privacy
from novahos.sources import RawItem, all_sources, resolve


def test_registry_has_finance_sources():
    keys = all_sources()
    assert "plaid" in keys and "quickbooks" in keys
    assert resolve("plaid") is not None
    assert resolve("nope") is None


def test_rawitem_shape():
    it = RawItem(source="plaid", type="financial", content="x")
    assert it.domain == "personal" and it.meta == {} and it.dedup_key is None


def test_plaid_pull_graceful_without_creds():
    # No access_token / env creds → empty list, never raises.
    items = asyncio.run(resolve("plaid")().pull("user@example.com"))
    assert items == []


def test_quickbooks_pull_graceful_without_identity():
    items = asyncio.run(resolve("quickbooks")(realm_id="123").pull("user@example.com"))
    assert items == []


def test_finance_data_is_private_tier():
    # Money data must classify PRIVATE → never pushed to third parties.
    assert privacy.classify("plaid", "financial", "Whole Foods amount 42") == privacy.PRIVATE
    assert privacy.may_send_to_third_party(privacy.classify("quickbooks", "financial")) is False


def test_source_privacy_floor():
    assert resolve("plaid").privacy_floor == "private"
    assert resolve("quickbooks").privacy_floor == "private"


def test_agent_registry_resolves_croesus():
    from novahos.agents import resolve as resolve_agent
    assert resolve_agent("croesus", "assess") is not None
    assert resolve_agent("nope", "x") is None


def test_croesus_empty_snapshot():
    from novahos.agents.croesus import assess
    assert asyncio.run(assess({})) == {}


def test_discovery_suggests_from_signals():
    from novahos.sources.discovery import suggest
    sugg = suggest(["noreply@intuit.com", "jobs@linkedin.com", "x@gmail.com"],
                   already={"google"})
    keys = {s["source"] for s in sugg}
    assert "quickbooks" in keys and "linkedin" in keys
    assert "google" not in keys  # already connected → excluded


def test_capability_manifest_lists_sources_and_agents():
    from novahos.capabilities import capabilities
    cap = capabilities()
    assert "plaid" in cap["sources"] and "quickbooks" in cap["sources"]
    assert "croesus" in cap["agents"] and "assess" in cap["agents"]["croesus"]
    assert "constitution" in cap["kernel"]
