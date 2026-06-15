"""Auto-discover which apps a user already uses, from inbound signals. (Sources; stdlib.)

Generic + app-agnostic: given signals (email sender domains, existing source keys, text snippets)
it maps them to connectable sources. An app gathers its own signals (e.g. from ingested
email/calendar) and calls `suggest()`. Pure suggestion, consent-first — nothing connects on its
own. Adding a detectable app = a line in SIGNATURES.
"""
from __future__ import annotations

# source key -> substrings that, if seen in a signal, imply the user uses it
SIGNATURES: dict[str, tuple[str, ...]] = {
    "quickbooks": ("intuit.com", "quickbooks", "qbo"),
    "microsoft": ("outlook.com", "office365", "microsoft.com", "live.com"),
    "google": ("gmail.com", "calendar.google", "googlemail"),
    "linkedin": ("linkedin.com",),
    "mobilo": ("mobilo", "mobilocard"),
    "plaid": ("plaid.com",),
    "apollo": ("apollo.io",),
    "slack": ("slack.com",),
    "github": ("github.com",),
    "stripe": ("stripe.com",),
}


def suggest(signals, already=()) -> list[dict]:
    """signals: iterable of strings (domains/sources/snippets). already: connected source keys.

    Returns [{"source", "signal"}] for apps detected but not yet connected.
    """
    al = {str(s).lower() for s in already}
    text = [str(s).lower() for s in signals if s]
    out: list[dict] = []
    for src, sigs in SIGNATURES.items():
        if src in al:
            continue
        hit = next((sig for sig in sigs if any(sig in s for s in text)), None)
        if hit:
            out.append({"source": src, "signal": hit})
    return out
