"""SourceBackend — the inbound mirror of channels/. (Sources; extras: novahos[sources].)

`channels/` sends OUT (publish/DM/engage); `sources/` pulls IN. One interface, many inbound
systems (plaid, quickbooks, microsoft, google, …). A source knows *how to talk to* an external
system and returns `RawItem`s; the calling app owns *where the data lands* — it normalizes +
persists them (e.g. `app.ingest.sink` → its tenant store + Knowledge Center). So a connector is
written ONCE at the platform and every NOVAH app reuses it.

Within a source there may be sub-modes (an official API vs an export parser) — same idea as a
channel's compliance modes. Adding a source = a new `SourceBackend` subclass registered in
`registry.py`; apps don't change.

`RawItem` is the shared inbound contract (apps import it from here, not from their own code).
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass
class RawItem:
    """One unit pulled from a source; the app turns it into its own DataPoint."""
    source: str
    type: str
    content: str
    title: str | None = None
    dedup_key: str | None = None      # source-native id → idempotent sync
    ts: str | None = None
    domain: str = "personal"          # personal | business (the wall)
    meta: dict = field(default_factory=dict)


class NotSupported(RuntimeError):
    """Raised when a capability isn't available on the active source/mode."""


class SourceBackend(ABC):
    """Subclass per inbound source. `source` is the stable registry/connector key.

    `**cfg` is the per-connector config (the connector row's `meta`) — e.g. a Plaid
    `access_token`, a QuickBooks `realm_id`, or an ICS url. Token-based sources may also
    fetch credentials over the mesh (see `_identity.identity`).
    """
    source: str = "base"
    mode: str = "official-api"        # official-api | export | webhook
    capabilities: set[str] = {"pull"}
    privacy_floor: str = "semi"       # hint: pulled data is classified no looser than this

    def __init__(self, **cfg):
        self.cfg = cfg

    @abstractmethod
    async def pull(self, user_email: str, since: str | None = None) -> list[RawItem]:
        """Fetch new raw items from the source since `since` (cursor/timestamp). Read-only."""
        raise NotImplementedError


# Back-compat alias: apps that referenced the old `Connector` name keep working.
Connector = SourceBackend
