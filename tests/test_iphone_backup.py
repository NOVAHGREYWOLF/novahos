"""iPhone backup parser — synthetic SQLite fixtures matching the real domain schemas."""
import sqlite3

from novahos.sources import iphone_backup as ib


def _sms(p):
    c = sqlite3.connect(p)
    c.executescript("""
        CREATE TABLE handle (ROWID INTEGER PRIMARY KEY, id TEXT);
        CREATE TABLE message (ROWID INTEGER PRIMARY KEY, guid TEXT, text TEXT, date INTEGER,
                              is_from_me INTEGER, handle_id INTEGER);
        INSERT INTO handle VALUES (1, '+15551234567');
        INSERT INTO message VALUES (1,'g1','Are we still on for Friday?',715000000000000000,0,1);
        INSERT INTO message VALUES (2,'g2','Yes! see you then',715000001000000000,1,1);
        INSERT INTO message VALUES (3,'g3','   ',715000002000000000,0,1);  -- blank, skipped
    """)
    c.commit(); c.close()


def _contacts(p):
    c = sqlite3.connect(p)
    c.executescript("""
        CREATE TABLE ABPerson (ROWID INTEGER PRIMARY KEY, First TEXT, Last TEXT, Organization TEXT);
        INSERT INTO ABPerson VALUES (1,'Ricardo','Vega','Acme');
        INSERT INTO ABPerson VALUES (2,NULL,NULL,NULL);  -- empty, skipped
    """)
    c.commit(); c.close()


def _calls(p):
    c = sqlite3.connect(p)
    c.executescript("""
        CREATE TABLE ZCALLRECORD (Z_PK INTEGER PRIMARY KEY, ZADDRESS TEXT, ZDATE REAL,
                                  ZDURATION REAL, ZORIGINATED INTEGER);
        INSERT INTO ZCALLRECORD VALUES (1,'+15559876543',715000000,120,1);
    """)
    c.commit(); c.close()


def _calendar(p):
    c = sqlite3.connect(p)
    c.executescript("""
        CREATE TABLE CalendarItem (ROWID INTEGER PRIMARY KEY, summary TEXT,
                                   start_date REAL, end_date REAL);
        INSERT INTO CalendarItem VALUES (1,'Dentist',715000000,715003600);
    """)
    c.commit(); c.close()


def test_parse_backup_all_kinds(tmp_path):
    paths = {}
    for name, mk in [("messages", _sms), ("contacts", _contacts),
                     ("calls", _calls), ("calendar", _calendar)]:
        p = str(tmp_path / f"{name}.db"); mk(p); paths[name] = p
    items = ib.parse_backup(paths)
    by = {}
    for it in items:
        by.setdefault(it.type, []).append(it)
    assert len(by["message"]) == 2          # blank one skipped
    assert by["message"][0].source == "imessage"
    assert by["message"][0].ts and by["message"][0].ts.startswith("2023")  # ns→2001+ ≈ 2023
    assert any("Me:" in m.content for m in by["message"])
    assert by["contact"][0].content.startswith("Ricardo Vega")
    assert len(by["contact"]) == 1          # empty contact skipped
    assert by["call"][0].meta["direction"] == "outgoing" and by["call"][0].meta["duration_s"] == 120
    assert by["event"][0].title == "Dentist"
    # every item has a dedup_key for idempotent re-sync
    assert all(it.dedup_key for it in items)


def test_missing_or_corrupt_file_is_graceful(tmp_path):
    bad = str(tmp_path / "nope.db")
    assert ib.parse_messages(bad) == []         # missing file → []
    assert ib.parse_backup({"messages": bad, "contacts": None}) == []


def test_known_files_map():
    assert ib.KNOWN_FILES["messages"] == ("HomeDomain", "Library/SMS/sms.db")
    assert "calendar" in ib.KNOWN_FILES
