"""Knowledge System client — every app reads + writes the ONE shared store at the hub.

Thin wrapper over ``service_client`` against the hub's knowledge endpoints. (Rails; stdlib.)
"""
from __future__ import annotations

from . import service_client as SC

KINDS = ("doc", "fact", "learning")
SCOPES = ("global", "icp")


def get_knowledge(email: str, *, scope: str | None = None, kind: str | None = None,
                  icp_id=None, limit: int = 500) -> dict:
    return SC.call("hub", "/api/knowledge",
                   params={"email": email, "scope": scope, "kind": kind,
                           "icp_id": icp_id, "limit": limit})


def add_knowledge(email: str, kind: str, text: str, *, scope: str = "global",
                  icp_id=None, source: str | None = None) -> dict:
    if kind not in KINDS:
        raise ValueError(f"kind must be one of {KINDS}")
    return SC.call("hub", "/api/knowledge", method="POST",
                   body={"email": email, "kind": kind, "text": text,
                         "scope": scope, "icp_id": icp_id, "source": source})


def add_document(email: str, name: str, *, content: str | None = None, url: str | None = None,
                 scope: str = "global", icp_id=None, source: str | None = None) -> dict:
    return SC.call("hub", "/api/documents", method="POST",
                   body={"email": email, "name": name, "content": content, "url": url,
                         "scope": scope, "icp_id": icp_id, "source": source})
