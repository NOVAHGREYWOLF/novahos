"""iPhone backup parser — normalize an iTunes/Apple-Devices backup into RawItems. (Sources; stdlib.)

The richest source of a person's real life: messages, contacts, calls, calendar (notes/health
refined later). The backup lives on the user's PC; **decryption + file extraction run in the
LOCAL companion** (a maintained lib like `iOSbackup` handles the encrypted-keybag crypto), which
then hands THIS parser the extracted SQLite files. This module is pure stdlib (sqlite3) and does
no crypto and no network — so it stays kernel-light and runs anywhere.

The companion locates files by (domain, relativePath) — see KNOWN_FILES — extracts them to temp
paths, then calls `parse_backup({name: path, ...})`. Each parser is defensive: a missing table or
a schema that shifted across iOS versions yields [] rather than raising, so a partial backup still
produces what it can.

Privacy: items are emitted with truthful `type`s (message/contact/call/event). How they're stored
(vectorized vs withheld, encrypted at rest) is the APP's ingest decision, not the parser's.
"""
from __future__ import annotations

import contextlib
import sqlite3
from datetime import datetime, timedelta, timezone

from .base import RawItem

# logical name -> (domain, relativePath) the companion extracts from the backup
KNOWN_FILES: dict[str, tuple[str, str]] = {
    "messages": ("HomeDomain", "Library/SMS/sms.db"),
    "contacts": ("HomeDomain", "Library/AddressBook/AddressBook.sqlitedb"),
    "calls": ("HomeDomain", "Library/CallHistoryDB/CallHistory.storedata"),
    "calendar": ("HomeDomain", "Library/Calendar/Calendar.sqlitedb"),
    # refined against a real backup later (protobuf / binary schemas):
    # "notes":  ("AppDomainGroup-group.com.apple.notes", "NoteStore.sqlite"),
    # "health": ("HealthDomain", "Health/healthdb_secure.sqlite"),
}

_COCOA_EPOCH = 978307200  # seconds between 1970-01-01 and 2001-01-01 (Apple's reference date)
MAX_PER_KIND = 5000       # cap so one backup can't flood ingest


def _apple_ts(val) -> str | None:
    """Apple 'Mac absolute time' → ISO8601. Seconds OR nanoseconds since 2001-01-01 UTC."""
    try:
        v = float(val)
    except (TypeError, ValueError):
        return None
    if v <= 0:
        return None
    if v > 1e11:          # nanoseconds (iOS 11+) → seconds
        v = v / 1e9
    try:
        return (datetime(2001, 1, 1, tzinfo=timezone.utc) + timedelta(seconds=v)).isoformat()
    except (OverflowError, OSError, ValueError):
        return None


def _rows(path: str, sql: str) -> list[sqlite3.Row]:
    """Run a read-only query; return [] on any error (missing table / shifted schema)."""
    try:
        con = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
        con.row_factory = sqlite3.Row
        try:
            return con.execute(sql).fetchall()
        finally:
            con.close()
    except Exception:
        return []


def parse_messages(path: str) -> list[RawItem]:
    sql = """
        SELECT m.ROWID AS rid, m.guid AS guid, m.text AS text, m.date AS date,
               m.is_from_me AS mine, h.id AS handle
        FROM message m LEFT JOIN handle h ON m.handle_id = h.ROWID
        WHERE m.text IS NOT NULL AND length(trim(m.text)) > 0
        ORDER BY m.date DESC LIMIT %d
    """ % MAX_PER_KIND
    out: list[RawItem] = []
    for r in _rows(path, sql):
        who = "Me" if r["mine"] else (r["handle"] or "Unknown")
        out.append(RawItem(
            source="imessage", type="message",
            title=f"with {r['handle'] or 'unknown'}",
            content=f"{who}: {r['text']}", ts=_apple_ts(r["date"]), domain="personal",
            dedup_key=f"imsg:{r['guid'] or r['rid']}",
            meta={"from_me": bool(r["mine"]), "handle": r["handle"]},
        ))
    return out


def parse_contacts(path: str) -> list[RawItem]:
    sql = """
        SELECT ROWID AS rid, First AS first, Last AS last, Organization AS org
        FROM ABPerson LIMIT %d
    """ % MAX_PER_KIND
    out: list[RawItem] = []
    for r in _rows(path, sql):
        name = " ".join(x for x in (r["first"], r["last"]) if x) or (r["org"] or "")
        if not name.strip():
            continue
        content = name + (f" ({r['org']})" if r["org"] and r["org"] != name else "")
        out.append(RawItem(source="contacts", type="contact", title=name, content=content,
                           domain="personal", dedup_key=f"contact:{r['rid']}"))
    return out


def parse_calls(path: str) -> list[RawItem]:
    # CallHistory.storedata is Core Data: ZCALLRECORD with Z* columns.
    sql = """
        SELECT Z_PK AS pk, ZADDRESS AS addr, ZDATE AS date, ZDURATION AS dur, ZORIGINATED AS out
        FROM ZCALLRECORD ORDER BY ZDATE DESC LIMIT %d
    """ % MAX_PER_KIND
    out: list[RawItem] = []
    for r in _rows(path, sql):
        addr = r["addr"]
        if isinstance(addr, (bytes, bytearray)):
            addr = addr.decode("utf-8", "ignore")
        direction = "outgoing" if r["out"] else "incoming"
        dur = int(r["dur"] or 0)
        # Core Data dates are seconds since 2001 (offset, not ns).
        ts = _apple_ts((r["date"] or 0) if (r["date"] or 0) > 1e8 else (r["date"] or 0) + 0)
        out.append(RawItem(source="calls", type="call",
                           title=f"{direction} call {addr or ''}".strip(),
                           content=f"{direction} call with {addr or 'unknown'}, {dur}s",
                           ts=ts, domain="personal", dedup_key=f"call:{r['pk']}",
                           meta={"direction": direction, "duration_s": dur}))
    return out


def parse_calendar(path: str) -> list[RawItem]:
    sql = """
        SELECT ROWID AS rid, summary, start_date, end_date
        FROM CalendarItem WHERE summary IS NOT NULL ORDER BY start_date DESC LIMIT %d
    """ % MAX_PER_KIND
    out: list[RawItem] = []
    for r in _rows(path, sql):
        ts = _apple_ts(r["start_date"])
        out.append(RawItem(source="calendar", type="event", title=r["summary"],
                           content=f"{r['summary']} ({ts or 'no date'})", ts=ts,
                           domain="personal", dedup_key=f"cal:{r['rid']}"))
    return out


_PARSERS = {
    "messages": parse_messages,
    "contacts": parse_contacts,
    "calls": parse_calls,
    "calendar": parse_calendar,
}


def parse_backup(extracted: dict[str, str]) -> list[RawItem]:
    """extracted: {logical_name: path_to_extracted_sqlite}. Returns all RawItems it can read."""
    items: list[RawItem] = []
    for name, path in (extracted or {}).items():
        parser = _PARSERS.get(name)
        if parser and path:
            with contextlib.suppress(Exception):
                items.extend(parser(path))
    return items
