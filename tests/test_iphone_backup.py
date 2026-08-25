"""iPhone backup parser — synthetic SQLite fixtures matching the real domain schemas."""
import gzip
import sqlite3

from novahos import privacy
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
    assert ib.KNOWN_FILES["notes"] == (
        "AppDomainGroup-group.com.apple.notes", "NoteStore.sqlite")


def _notes(p, title_col="ZTITLE1"):
    """NoteStore.sqlite as iOS actually shapes it: Core Data metadata in
    ZICCLOUDSYNCINGOBJECT, and the note BODY as a gzipped blob in ZICNOTEDATA.ZDATA.
    The fixture includes a real gzip blob so a body-reading regression would have
    something to wrongly succeed against."""
    c = sqlite3.connect(p)
    c.executescript(f"""
        CREATE TABLE ZICCLOUDSYNCINGOBJECT (
            Z_PK INTEGER PRIMARY KEY, {title_col} TEXT, ZSNIPPET TEXT,
            ZCREATIONDATE1 REAL, ZMODIFICATIONDATE1 REAL,
            ZMARKEDFORDELETION INTEGER, ZNOTEDATA INTEGER, ZFOLDER INTEGER);
        CREATE TABLE ZICNOTEDATA (Z_PK INTEGER PRIMARY KEY, ZDATA BLOB);
    """)
    c.execute("INSERT INTO ZICNOTEDATA VALUES (1, ?)",
              (gzip.compress(b"PROTOBUF-STRUCT-BYTES the real body lives here"),))
    rows = [
        # pk, title, snippet, created, modified, deleted, notedata, folder
        (1, "Passport renewal", "appointment Tuesday 9am", 715000000, 715000900, 0, 1, 1),
        (2, "Book ideas", None, 715000100, 715000100, 0, 2, 1),
        (3, "Deleted thing", "gone", 715000200, 715000200, 1, 3, 1),   # trashed -> skipped
        (4, "   ", "blank title", 715000300, 715000300, 0, 4, 1),      # blank -> skipped
        (5, "A folder row", None, 715000400, 715000400, 0, None, 1),   # no ZNOTEDATA -> skipped
    ]
    c.executemany(
        f"INSERT INTO ZICCLOUDSYNCINGOBJECT (Z_PK,{title_col},ZSNIPPET,ZCREATIONDATE1,"
        "ZMODIFICATIONDATE1,ZMARKEDFORDELETION,ZNOTEDATA,ZFOLDER) VALUES (?,?,?,?,?,?,?,?)", rows)
    c.commit(); c.close()


def test_notes_titles_and_snippets(tmp_path):
    p = str(tmp_path / "NoteStore.sqlite"); _notes(p)
    items = ib.parse_notes(p)
    titles = [i.title for i in items]
    assert titles == ["Passport renewal", "Book ideas"]   # newest-modified first
    assert all(i.type == "note" and i.source == "notes" for i in items)
    # snippet is folded into content; a note without one keeps just its title
    assert items[0].content == "Passport renewal\nappointment Tuesday 9am"
    assert items[1].content == "Book ideas"
    assert items[0].ts and items[0].ts.startswith("2023")
    assert all(i.dedup_key for i in items)


def test_notes_body_is_never_read(tmp_path):
    """The gzipped protobuf body must NOT leak into content. This is the regression guard for
    'someone decompresses ZDATA and regexes strings out of it' — that returns text that is
    quietly wrong, so the parser must keep declaring body_included=False instead."""
    p = str(tmp_path / "NoteStore.sqlite"); _notes(p)
    items = ib.parse_notes(p)
    assert items, "fixture should yield notes"
    for i in items:
        assert "the real body lives here" not in i.content
        assert i.meta["body_included"] is False


def test_notes_survives_a_renamed_title_column(tmp_path):
    """Apple shifts the Core Data suffix across iOS versions; probing must span it."""
    p = str(tmp_path / "NoteStore.sqlite"); _notes(p, title_col="ZTITLE2")
    assert [i.title for i in ib.parse_notes(p)] == ["Passport renewal", "Book ideas"]


def test_notes_unknown_schema_returns_empty_not_wrong_data(tmp_path):
    p = str(tmp_path / "weird.sqlite")
    c = sqlite3.connect(p)
    c.execute("CREATE TABLE ZICCLOUDSYNCINGOBJECT (Z_PK INTEGER PRIMARY KEY, ZWHATEVER TEXT)")
    c.execute("INSERT INTO ZICCLOUDSYNCINGOBJECT VALUES (1,'x')")
    c.commit(); c.close()
    assert ib.parse_notes(p) == []          # no recognisable title column -> nothing, not a guess
    assert ib.parse_notes(str(tmp_path / "missing.sqlite")) == []


def test_every_item_is_stamped_local_only(tmp_path):
    """The whole point of the phone path: nothing it produces may travel to another node."""
    paths = {}
    for name, mk in [("messages", _sms), ("contacts", _contacts), ("calls", _calls),
                     ("calendar", _calendar), ("notes", _notes)]:
        p = str(tmp_path / f"{name}.db"); mk(p); paths[name] = p
    items = ib.parse_backup(paths)
    assert items
    assert all(i.meta.get("privacy_tier") == privacy.LOCAL_ONLY for i in items)
    # and that tier must actually refuse every route off the machine
    assert privacy.may_send_to_third_party(privacy.LOCAL_ONLY) is False
    assert privacy.may_use_cloud_model(privacy.LOCAL_ONLY) is False
    assert privacy.may_replicate_to_node(privacy.LOCAL_ONLY, node_is_local=False) is False
    assert privacy.may_replicate_to_node(privacy.LOCAL_ONLY, node_is_local=True) is True


def test_health_stays_unimplemented():
    """Guards the deliberate omission: if someone enables health, they must add a parser and a
    test proving the data_type enum was verified, not just uncomment a line."""
    assert "health" not in ib.KNOWN_FILES
    assert "health" not in ib._PARSERS

