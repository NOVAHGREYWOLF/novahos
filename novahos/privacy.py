"""Three-tier privacy — classify a data point at ingestion. (Foundation; stdlib.)

  PRIVATE 🔴  health, identity, credentials, intimate comms — local-only, never third-party.
  SEMI    🟡  email, files, business comms — self-hosted; trusted model with consent.
  PUBLIC  🟢  published/marketing content — free to flow.

Deterministic heuristic over (source, type, content). Errs toward PRIVATE on ambiguity.
"""
from __future__ import annotations

PRIVATE = "private"
SEMI = "semi"
PUBLIC = "public"

_PRIVATE_SOURCES = {"applehealth", "health", "fitbit", "strava", "bank", "finance", "messages", "imessage", "whatsapp"}
_PRIVATE_TYPES = {"health", "vitals", "credential", "secret", "medical", "intimate", "financial"}
_PRIVATE_KEYWORDS = (
    "diagnos", "medication", "therapy", "depress", "anxiet", "ssn", "password", "account number",
    "routing number", "salary", "net worth", "intimate", "sexual", "suicid",
)
_PUBLIC_SOURCES = {"published", "blog", "marketing", "website"}
_PUBLIC_TYPES = {"published_post", "marketing", "press"}


def classify(source: str = "", type_: str = "", content: str | None = None) -> str:
    s, t = (source or "").lower(), (type_ or "").lower()
    if s in _PRIVATE_SOURCES or t in _PRIVATE_TYPES:
        return PRIVATE
    if content:
        c = content.lower()
        if any(k in c for k in _PRIVATE_KEYWORDS):
            return PRIVATE
    if s in _PUBLIC_SOURCES or t in _PUBLIC_TYPES:
        return PUBLIC
    return SEMI


def may_send_to_third_party(tier: str) -> bool:
    return tier != PRIVATE


def may_use_cloud_model(tier: str) -> bool:
    return tier in (SEMI, PUBLIC)
