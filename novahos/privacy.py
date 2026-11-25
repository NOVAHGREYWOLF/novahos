"""Four-tier privacy — classify a data point at ingestion. (Foundation; stdlib.)

  LOCAL_ONLY 🔒  phone-backup comms and anything else that must never leave THIS machine:
                 not to a third party, not to a cloud model, and not to another NODE.
  PRIVATE    🔴  health, identity, credentials, finance — never third-party, never a cloud
                 model, but MAY replicate to another node the owner controls.
  SEMI       🟡  email, files, business comms — self-hosted; trusted model with consent.
  PUBLIC     🟢  published/marketing content — free to flow.

Deterministic heuristic over (source, type, content). Errs toward the STRICTER tier on
ambiguity.

Why LOCAL_ONLY exists (home-node §S14): the cloud is *a node*, not *the server*, and one
logical brain replicates to every node. `private` replicating by default would put a person's
iMessages on a rented machine. So replication is an EGRESS decision and needs a tier that is
closed by default rather than six flags that can each be flipped.

Every gate here is an ALLOWLIST (`tier in (...)`), never a denylist (`tier != PRIVATE`).
A denylist silently admits any tier added later, which is exactly how a new tier becomes a
leak: the check keeps passing and nothing fails loudly.
"""
from __future__ import annotations

LOCAL_ONLY = "local_only"
PRIVATE = "private"
SEMI = "semi"
PUBLIC = "public"

# Ordered strictest → loosest. Used for comparisons; do not reorder casually.
TIERS = (LOCAL_ONLY, PRIVATE, SEMI, PUBLIC)

# Intimate person-to-person comms. These are the contents of someone's phone: they stay on
# the machine the owner physically holds. Generic words ("contacts", "calendar") are NOT here
# because other connectors legitimately use them — the iPhone backup parser stamps its OWN
# items local-only per item instead, which scopes the decision to the phone path exactly.
_LOCAL_ONLY_SOURCES = {"imessage", "messages", "sms", "whatsapp", "signal", "iphone_backup"}
_LOCAL_ONLY_TYPES = {"intimate", "message_thread"}

_PRIVATE_SOURCES = {"applehealth", "health", "fitbit", "strava", "bank", "finance"}
_PRIVATE_TYPES = {"health", "vitals", "credential", "secret", "medical", "intimate", "financial"}
_PRIVATE_KEYWORDS = (
    "diagnos", "medication", "therapy", "depress", "anxiet", "ssn", "password", "account number",
    "routing number", "salary", "net worth", "intimate", "sexual", "suicid",
)
_PUBLIC_SOURCES = {"published", "blog", "marketing", "website"}
_PUBLIC_TYPES = {"published_post", "marketing", "press"}


def classify(source: str = "", type_: str = "", content: str | None = None) -> str:
    s, t = (source or "").lower(), (type_ or "").lower()
    if s in _LOCAL_ONLY_SOURCES or t in _LOCAL_ONLY_TYPES:
        return LOCAL_ONLY
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
    """Allowlist: only SEMI/PUBLIC may reach a third party. An unknown tier is refused."""
    return tier in (SEMI, PUBLIC)


def may_use_cloud_model(tier: str) -> bool:
    """Allowlist: only SEMI/PUBLIC may be sent to a model we do not host."""
    return tier in (SEMI, PUBLIC)


def may_leave_machine(tier: str) -> bool:
    """False for anything that must not cross the machine boundary by ANY route — third
    party, cloud model, or a replica on another node. LOCAL_ONLY is the tier that answers
    'may this travel at all', which the older three-tier model had no way to express."""
    return tier in (PRIVATE, SEMI, PUBLIC)


def may_replicate_to_node(tier: str, *, node_is_local: bool) -> bool:
    """The §S14 replication table, as one function rather than six flags.

    A LOCAL node (a machine the owner physically holds) may hold every tier. A REMOTE node —
    which includes the cloud node, because the cloud is a node and a rented machine is someone
    else's computer — may hold everything EXCEPT LOCAL_ONLY.

    Defaults closed: an unknown/None tier is treated as LOCAL_ONLY and refused.
    """
    if tier not in TIERS:
        return False
    if node_is_local:
        return True
    return may_leave_machine(tier)
