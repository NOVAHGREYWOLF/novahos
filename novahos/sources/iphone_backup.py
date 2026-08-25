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

The companion that fits this contract exactly is `ios-backup-core`
(github.com/charleswest775/ios-backup-core, MIT), whose
`LocalBackupAccessor.get_file(relative_path, domain=...)` takes the same (domain, relativePath)
pair KNOWN_FILES stores and returns a decrypted path. It sits on `iphone-backup-decrypt` →
`pycryptodome` for the keybag crypto. The OpenExtract desktop APP is built on that same library
but is NOT itself a usable companion: it is an Electron GUI whose only exports are rendered
txt/csv/html/pdf, and it never hands out the raw SQLite. See home-node/21-The-Phone.md.

Privacy: items are emitted with truthful `type`s (message/contact/call/event/note) AND stamped
`meta["privacy_tier"] = LOCAL_ONLY`. A phone backup is the contents of someone's pocket; under a
one-brain-many-nodes design where `private` replicates to every node INCLUDING a rented cloud one,
"private" is not a strong enough claim. LOCAL_ONLY is the tier that never leaves this machine.
The stamp is per ITEM rather than by source name because "contacts"/"calendar" are generic words
other connectors legitimately use — only the phone path should be pinned this tightly.
"""
from __future__ import annotations

import contextlib
import sqlite3
from datetime import datetime, timedelta, timezone

from ..privacy import LOCAL_ONLY
from .base import RawItem

# logical name -> (domain, relativePath) the companion extracts from the backup
KNOWN_FILES: dict[str, tuple[str, str]] = {
    "messages": ("HomeDomain", "Library/SMS/sms.db"),
    "contacts": ("HomeDomain", "Library/AddressBook/AddressBook.sqlitedb"),
    "calls": ("HomeDomain", "Library/CallHistoryDB/CallHistory.storedata"),
    "calendar": ("HomeDomain", "Library/Calendar/Calendar.sqlitedb"),
    "notes": ("AppDomainGroup-group.com.apple.notes", "NoteStore.sqlite"),
    # STILL commented, deliberately. healthdb_secure.sqlite keys every row to an INTEGER
    # `data_type` in SAMPLES/QUANTITY_SAMPLES whose meaning is an undocumented enum that Apple
    # renumbers across iOS versions. Guessing it yields rows that look right and mean something
    # else — a heart rate read as a step count. That is worse than no health ingest, so it waits
    # for a real backup to verify against.
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


def _columns(path: str, table: str) -> set[str]:
    """The columns a table ACTUALLY has. Apple renames columns across iOS versions (Notes is the
    worst offender: ZTITLE1 vs ZTITLE2 vs ZTITLE), so a hardcoded SELECT breaks on half the
    backups in existence. Probing lets one parser span versions and return [] rather than guess."""
    try:
        con = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
        try:
            return {r[1] for r in con.execute(f"PRAGMA table_info({table})")}
        finally:
            con.close()
    except Exception:
        return set()


def _first(available: set[str], *candidates: str) -> str | None:
    """First candidate column name that exists, else None."""
    return next((c for c in candidates if c in available), None)


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


def parse_notes(path: str) -> list[RawItem]:
    """Apple Notes — TITLES, PREVIEWS and DATES only. The note BODY is deliberately not read.

    NoteStore.sqlite (iOS 9+) splits a note in two:

      * ``ZICCLOUDSYNCINGOBJECT`` — a Core Data table holding the title, a plaintext preview
        (``ZSNIPPET``), the folder, and creation/modification dates. All ordinary SQLite columns.
      * ``ZICNOTEDATA.ZDATA``    — the note body, stored as a **gzipped protobuf**.

    We read the first and NOT the second. Un-gzipping ZDATA is trivial, but what comes out is a
    protobuf whose field numbering Apple has never published and does change between iOS
    releases. The usual workaround (decompress, then regex printable runs out of the bytes)
    recovers text that is *mostly* right and silently wrong at every attachment, table, checklist
    and formatting run — it drops content without saying so and interleaves struct bytes into
    prose. A parser that returns subtly wrong notes is worse than one that returns titles, so the
    body waits for a verified schema.

    Titles and snippets are worth having on their own: "Passport renewal", "Offer numbers for
    Tuesday" carry real signal, and ZSNIPPET is a genuine plaintext lead-in to the body.

    Column names are probed (see `_columns`) rather than assumed, so a version whose columns
    differ yields [] instead of an exception or a wrong read.
    """
    cols = _columns(path, "ZICCLOUDSYNCINGOBJECT")
    if not cols:
        return []
    # Apple's Core Data numbering suffix shifts with the model version.
    title_c = _first(cols, "ZTITLE1", "ZTITLE2", "ZTITLE")
    if not title_c:
        return []
    snip_c = _first(cols, "ZSNIPPET")
    made_c = _first(cols, "ZCREATIONDATE1", "ZCREATIONDATE", "ZCREATIONDATE2")
    edit_c = _first(cols, "ZMODIFICATIONDATE1", "ZMODIFICATIONDATE", "ZMODIFICATIONDATE2")
    del_c = _first(cols, "ZMARKEDFORDELETION")
    note_c = _first(cols, "ZNOTEDATA")

    sel = ["Z_PK AS pk", f"{title_c} AS title"]
    sel.append(f"{snip_c} AS snippet" if snip_c else "NULL AS snippet")
    sel.append(f"{made_c} AS made" if made_c else "NULL AS made")
    sel.append(f"{edit_c} AS edited" if edit_c else "NULL AS edited")
    # A note row has ZNOTEDATA set; folders/attachments live in the same table without it, so
    # this is what separates real notes from the rest of the Core Data soup.
    where = [f"{title_c} IS NOT NULL", f"length(trim({title_c})) > 0"]
    if del_c:
        where.append(f"({del_c} IS NULL OR {del_c} = 0)")
    if note_c:
        where.append(f"{note_c} IS NOT NULL")
    order = f"ORDER BY {edit_c} DESC" if edit_c else ""
    sql = (f"SELECT {', '.join(sel)} FROM ZICCLOUDSYNCINGOBJECT "
           f"WHERE {' AND '.join(where)} {order} LIMIT {MAX_PER_KIND}")

    out: list[RawItem] = []
    for r in _rows(path, sql):
        title = (r["title"] or "").strip()
        if not title:
            continue
        snippet = (r["snippet"] or "").strip() if r["snippet"] else ""
        ts = _apple_ts(r["edited"]) or _apple_ts(r["made"])
        out.append(RawItem(
            source="notes", type="note", title=title,
            content=(title + "\n" + snippet).strip() if snippet else title,
            ts=ts, domain="personal", dedup_key=f"note:{r['pk']}",
            # body_included=False is the honest signal to the app: this is a title/preview, not
            # the note. An app that later gets a real body parser can re-ingest on this flag.
            meta={"body_included": False, "created": _apple_ts(r["made"])},
        ))
    return out


_PARSERS = {
    "messages": parse_messages,
    "contacts": parse_contacts,
    "calls": parse_calls,
    "calendar": parse_calendar,
    "notes": parse_notes,
}


def parse_backup(extracted: dict[str, str]) -> list[RawItem]:
    """extracted: {logical_name: path_to_extracted_sqlite}. Returns all RawItems it can read.

    Every item is stamped ``meta["privacy_tier"] = LOCAL_ONLY`` before it is returned. This is
    done HERE, once, at the single exit of the module, rather than in each parser — a per-parser
    stamp is one `return` away from being forgotten by the next parser somebody adds, and the
    failure mode of forgetting is a person's messages replicating to a rented machine.
    """
    items: list[RawItem] = []
    for name, path in (extracted or {}).items():
        parser = _PARSERS.get(name)
        if parser and path:
            with contextlib.suppress(Exception):
                items.extend(parser(path))
    for it in items:
        it.meta["privacy_tier"] = LOCAL_ONLY
    return items
