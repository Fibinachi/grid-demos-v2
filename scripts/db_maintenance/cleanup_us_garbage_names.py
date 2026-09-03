"""
US Data Cleanup — Phase 1: Garbage Names (conservative)

Removes or fixes US church records whose name field is clearly not a church:
- URLs appended to church names (e.g. "CARROLLTON FIRST CHRISTIAN HTTP://…")
- Social media channel names used as church names (e.g. "YFMC YOUTUBE CHANNEL")
- News article titles scraped as church names (e.g. "SAINT JOHN PAUL IIS WORLDVIEW…")
- Event/calendar page titles used as church names

NOT removed: "Old Calendar" churches (legitimate Old Calendarist Orthodox),
CCRA (Creation Calendar Research Association — legitimate ministry),
"Stream"-related names (legitimate churches with "stream" in their name).
"""
import sqlite3
import re
from datetime import datetime, timezone

DB = "churches.db"


def delete_records(c, rowids, reason):
    """Delete records by rowid from churches and child tables, log changes."""
    if not rowids:
        return 0

    rowid_list = list(rowids)
    ph = ",".join("?" * len(rowid_list))
    now = datetime.now(timezone.utc).isoformat()

    # Log to enrichment_change_log
    c.execute(
        f"INSERT INTO enrichment_change_log (church_id, field_name, old_value, new_value, change_source, changed_at) "
        f"SELECT id, 'deleted_by_cleanup', NULL, ?, 'us_garbage_cleanup', ? "
        f"FROM churches WHERE rowid IN ({ph}) AND id IS NOT NULL",
        [reason, now] + rowid_list,
    )

    # Child tables keyed by church_id
    id_list = [
        r[0]
        for r in c.execute(
            f"SELECT id FROM churches WHERE rowid IN ({ph}) AND id IS NOT NULL", rowid_list
        )
        if r[0] is not None
    ]
    if id_list:
        id_ph = ",".join("?" * len(id_list))
        for tbl in [
            "church_contacts",
            "church_sources",
            "church_enrichment",
            "church_classification_meta",
            "church_rucc",
            "church_broadband",
            "church_fcc",
            "church_gnis",
            "church_metro_area",
            "church_nrhp",
            "church_postal_admin",
            "church_broadcast",
            "church_operations",
            "church_vacancies",
            "church_staff",
            "attendance_history",
        ]:
            try:
                c.execute(f"DELETE FROM {tbl} WHERE church_id IN ({id_ph})", id_list)
            except sqlite3.OperationalError:
                pass
        for tbl in ["_attendance_results"]:
            try:
                c.execute(f'DELETE FROM "{tbl}" WHERE church_id IN ({id_ph})', id_list)
            except sqlite3.OperationalError:
                pass

    c.execute(f"DELETE FROM churches WHERE rowid IN ({ph})", rowid_list)
    return c.rowcount


def fix_name(c, rowid, new_name):
    """Fix a church's name, logging the change."""
    old = c.execute("SELECT name, id FROM churches WHERE rowid = ?", (rowid,)).fetchone()
    if not old:
        return
    old_name, church_id = old[0], old[1]
    c.execute("UPDATE churches SET name = ? WHERE rowid = ?", (new_name, rowid))
    if church_id is not None:
        c.execute(
            "INSERT INTO enrichment_change_log (church_id, field_name, old_value, new_value, change_source, changed_at) "
            "VALUES (?, 'name', ?, ?, 'us_name_cleanup', ?)",
            (church_id, old_name, new_name, datetime.now(timezone.utc).isoformat()),
        )


def main():
    print(f"=== US Garbage Names Cleanup (conservative) === {datetime.now()}")
    db = sqlite3.connect(DB, timeout=60)
    db.execute("PRAGMA busy_timeout = 60000")
    db.execute("PRAGMA journal_mode = WAL")
    c = db.cursor()
    now = datetime.now(timezone.utc).isoformat()

    # ─────────────────────────────────────────────────────────
    # 1. Fix names FIRST (strip embedded URLs) — these records
    #    are legitimate but their name has URL clutter.
    # ─────────────────────────────────────────────────────────
    fix_records = []
    c.execute(
        "SELECT rowid, name, source FROM churches WHERE country='US' AND "
        "(name LIKE '% HTTP://%' COLLATE NOCASE OR name LIKE '% HTTPS://%' COLLATE NOCASE)"
    )
    for r in c.fetchall():
        fix_records.append((r[0], str(r[1]), r[2]))

    print(f"\nRecords to FIX (strip URL from name): {len(fix_records)}")
    fixed_count = 0
    fix_that_became_empty = set()
    for rowid, name_str, source in fix_records:
        cleaned = re.sub(r"\s+https?://[^\s]+$", "", name_str, flags=re.IGNORECASE).strip()
        cleaned = re.sub(r"\s+@\w+\s+https?://[^\s]+$", "", cleaned, flags=re.IGNORECASE).strip()
        cleaned = re.sub(r"\s+@\w+\s*$", "", cleaned, flags=re.IGNORECASE).strip()
        cleaned = re.sub(r"\s+", " ", cleaned).strip().rstrip("/,;:. \t-")

        if cleaned and cleaned != name_str:
            fix_name(c, rowid, cleaned)
            fixed_count += 1
            print(f"  FIXED rowid={rowid}: '{name_str[:50]}' -> '{cleaned[:50]}'")
        elif not cleaned:
            fix_that_became_empty.add(rowid)
            print(f"  EMPTY AFTER STRIP rowid={rowid}: '{name_str[:60]}' — will delete")

    # ─────────────────────────────────────────────────────────
    # 2. Delete clearly non-church records
    #    CONSERVATIVE: only targets things that are definitely
    #    not a church — social channels, article titles, events.
    # ─────────────────────────────────────────────────────────
    delete_patterns = [
        # Social media channel used as church name
        ("name LIKE '% YOUTUBE CHANNEL'", "social_channel_as_name"),
        ("name = 'SAINT PATRICK FACEBOOK'", "social_page_as_name"),
        # Pure event/calendar page titles
        ("name = 'UNITEDHEARTSDAYCALENDAR'", "calendar_event_as_name"),
        ("name = 'STREAMLIFE CHURCH EVENT CALENDAR'", "calendar_event_as_name"),
        # Specific news article — SAINT JOHN PAUL IIS (apostrophe-S)
        # The article title is "SAINT JOHN PAUL IIS WORLDVIEW…" — not a church.
        ("name = 'SAINT JOHN PAUL IIS WORLDVIEW SPREADS TO NEW GENERATIONS VIA CAMPING YOUTUBE TRAVEL'", "article_title_as_name"),
    ]

    all_delete_rowids = {}
    for clause, reason in delete_patterns:
        c.execute(f"SELECT rowid, name, source FROM churches WHERE country='US' AND {clause}")
        for r in c.fetchall():
            if r[0] not in all_delete_rowids:
                all_delete_rowids[r[0]] = (reason, str(r[1]), r[2])

    # Add records that became empty after URL stripping
    for rowid in fix_that_became_empty:
        if rowid not in all_delete_rowids:
            all_delete_rowids[rowid] = ("url_only_after_strip", "", "")

    print(f"\nRecords to DELETE: {len(all_delete_rowids)}")
    for rowid in sorted(all_delete_rowids):
        reason, name, src = all_delete_rowids[rowid]
        print(f"  DEL rowid={rowid} [{reason}] {str(name)[:70]:70s} src={src}")

    # ─────────────────────────────────────────────────────────
    # Execute
    # ─────────────────────────────────────────────────────────
    if all_delete_rowids:
        deleted = delete_records(c, list(all_delete_rowids.keys()), "page_artifact_garbage_name_us_cleanup")
        print(f"\nDeleted: {deleted} records")
    else:
        deleted = 0

    # Provenance log
    c.execute(
        "INSERT INTO provenance_log (source, script_name, started_at, completed_at, "
        "churches_updated, churches_inserted, status, notes) "
        "VALUES (?, ?, ?, ?, ?, 0, 'completed', ?)",
        (
            "us_garbage_cleanup",
            "cleanup_us_garbage_names.py",
            now,
            now,
            fixed_count,
            f"Deleted {deleted} records, fixed {fixed_count} names",
        ),
    )

    db.commit()
    db.close()
    print(f"\n=== SUMMARY ===")
    print(f"  Deleted: {deleted} records")
    print(f"  Fixed:   {fixed_count} records (URL stripped from name)")
    print(f"  Done! {datetime.now()}")


if __name__ == "__main__":
    main()
