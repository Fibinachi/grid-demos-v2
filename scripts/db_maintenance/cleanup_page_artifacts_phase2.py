#!/usr/bin/env python3
"""
Phase 2 cleanup: find and delete ALL remaining garbage records using
the original pattern logic from cleanup_page_artifacts.py.

Handles NULL-id records (from holy_sites_import/osm_import) separately.
"""
import sqlite3
from datetime import datetime, timezone

DB_PATH = r"E:\grid\churches.db"

CATHOLIC_PATTERNS = [
    ("name LIKE ?", "%MAINTENANCE%"),
    ("name LIKE ?", "%LITURGY AND MUSIC%"),
    ("name LIKE ?", "%LIMITED PART TIME%"),
    ("name LIKE ?", "%LAY ECCLESIAL%"),
    ("name LIKE ?", "% DIRECTOR %"),
    ("name LIKE ?", "% TECHNICIAN%"),
    ("name LIKE ?", "% ASSISTANT"),
    ("name LIKE ?", "%.html"),
    ("name LIKE ?", "%.HTM"),
    ("name LIKE ?", "%PUBLIC PAGE%"),
    ("name LIKE ?", "%GROUP PAGE%"),
    ("name LIKE ?", "%MEMORIAL PAGE%"),
    ("name LIKE ?", "MEDIA ADVISORY%"),
    ("name LIKE ?", "MEDIA ALERT%"),
    ("name LIKE ?", "%JACKPOT BINGO%"),
    ("name LIKE ?", "%ICE CREAM SOCIAL%"),
    ("name LIKE ?", "MASS TIMES%"),
    ("name LIKE ?", "LOCATOR%"),
    ("name LIKE ?", "INSTITUTIONAL RECORDS%"),
    ("name LIKE ?", "%MARRIAGE PREPARATION%"),
    ("name LIKE ?", "IDEAS GUIDELINES%"),
    ("name LIKE ?", "POPE %"),
    ("name LIKE ?", "CATHOLIC CHURCH %"),
    ("name LIKE ?", "VATICAN %"),
    ("name LIKE ?", "BISHOP %"),
    ("name LIKE ?", "MAN CHARGED%"),
    ("name LIKE ?", "MASSIVE TURNING%"),
    ("name LIKE ?", "LEAKED EMAILS%"),
    ("name LIKE ?", "IS THE CATHOLIC CHURCH%"),
    ("name LIKE ?", "IS THIS%"),
    ("name LIKE ?", "KENYAN%"),
    ("name LIKE ?", "MADAGASCAR%"),
    ("name LIKE ?", "KYIVS%"),
    ("name LIKE ?", "IN METOO%"),
    ("name LIKE ?", "IN THIS TIKTOK%"),
    ("name LIKE ?", "JOINING CATHOLIC%"),
    ("name LIKE ?", "IGNORING%"),
    ("name LIKE ?", "IF YOURE%"),
    ("name LIKE ?", "FEAST HIGHLIGHTS%"),
    ("name LIKE ?", "ICYMI%"),
    ("name LIKE ?", "ICONOSTASIS%"),
    ("name LIKE ?", "PUERTO RICO%"),
    ("name LIKE ?", "ONE YEAR OF%"),
    ("name LIKE ?", "MUSLIM FATHER%"),
    ("name LIKE ?", "NEW GLOBAL INITIATIVE%"),
    ("name LIKE ?", "AFTER CANADA%"),
    ("name LIKE ?", "INTERRELIGIOUS DIALOGUE%"),
    ("name LIKE ?", "INSTALLATION OF FR%"),
    ("name LIKE ?", "INDIANA INMATES%"),
    ("name LIKE ?", "INDIAS SYRO%"),
    ("name LIKE ?", "JEFF CAVINS%"),
    ("name LIKE ?", "MARRYING IN%"),
    ("name LIKE ?", "MARSHFIELD PARK RIDE%"),
    ("name LIKE ?", "MEMPHIS CATHOLIC SCHOOLS%"),
    ("name LIKE ?", "MEMPHIS JOY PROM%"),
    ("name LIKE ?", "LENTEN PENANCE%"),
    ("name LIKE ?", "LENTEN MISSION%"),
    ("name LIKE ?", "LENTEN DISPLAY%"),
    ("name LIKE ?", "KJZT%"),
    ("name LIKE ?", "LETTER FROM%"),
    ("name LIKE ?", "INDICATIONS OF%"),
    ("name LIKE ?", "JUBILEE YEAR%"),
    ("name LIKE ?", "IN CENTRAL AFRICA%"),
    ("name LIKE ?", "MEDIA%"),
    ("name LIKE ?", "LENTEN%"),
    ("name LIKE ?", "IMG%"),
    ("name LIKE ?", "JPII GROUP%"),
    ("name LIKE ?", "%UNSPLASH%"),
    ("name LIKE ?", "JEN COUSER%"),
    ("name LIKE ?", "THE CATHOLIC CHURCH %"),
    ("name LIKE ?", "% COORDINATOR%"),
    ("name LIKE ?", "YOUTH DIRECTOR%"),
    ("name LIKE ?", "PRESCHOOL DIRECTOR%"),
    ("name LIKE ?", "KITCHEN DIRECTOR%"),
    ("name LIKE ?", "PRINCIPAL %"),
]

SOCIAL_PAGE_PATTERNS = [
    ("name LIKE ?", "%PUBLIC PAGE%"),
    ("name LIKE ?", "%GROUP PAGE%"),
    ("name LIKE ?", "%MEMORIAL PAGE%"),
]

URL_AS_NAME_PATTERNS = [
    ("name LIKE ?", "http://%"),
    ("name LIKE ?", "https://%"),
    ("name LIKE ?", "Https://%"),
    ("name LIKE ?", "www.%"),
    ("name LIKE ?", "%goo.gl/maps%"),
]

CHILD_TABLES = [
    "attendance_history", "broadcast_ministries",
    "church_census_us", "church_arda", "church_broadband", "church_broadcast",
    "church_classification_meta", "church_contacts", "church_enrichment",
    "church_fcc", "church_food_desert", "church_gnis",
    "church_metro_area", "church_nrhp", "church_operations",
    "church_postal_admin", "church_sources", "church_staff",
    "church_territories", "church_vacancies",
    "org_links", "org_officers",
]
# Tables with _ prefix need quotes
CHILD_TABLES_QUOTED = ["_attendance_results"]


def find_garbage_ids(c):
    """Returns set of ids with valid non-NULL ids."""
    ids = set()
    # Catholic patterns - only from catholic_diocese_scrape
    for clause, value in CATHOLIC_PATTERNS:
        c.execute(f"SELECT id FROM churches WHERE source = 'catholic_diocese_scrape' AND {clause}", (value,))
        for row in c.fetchall():
            if row[0] is not None:
                ids.add(row[0])

    # Social pages from non-catholic sources
    for clause, value in SOCIAL_PAGE_PATTERNS:
        c.execute(f"SELECT id FROM churches WHERE source != 'catholic_diocese_scrape' AND {clause}", (value,))
        for row in c.fetchall():
            if row[0] is not None:
                ids.add(row[0])

    # URL-as-name
    for clause, value in URL_AS_NAME_PATTERNS:
        c.execute(f"SELECT id FROM churches WHERE id IS NOT NULL AND {clause}", (value,))
        for row in c.fetchall():
            if row[0] is not None:
                ids.add(row[0])

    # .html dedup
    c.execute("""
        SELECT id FROM churches
        WHERE id IS NOT NULL AND (name LIKE '%.html' OR name LIKE '%.HTM')
          AND EXISTS (
              SELECT 1 FROM churches c2
              WHERE c2.name = SUBSTR(churches.name, 1, LENGTH(churches.name) - CASE
                  WHEN churches.name LIKE '%.html' THEN 5
                  WHEN churches.name LIKE '%.HTM' THEN 4
                  ELSE 0 END)
              AND c2.id != churches.id
          )
    """)
    for row in c.fetchall():
        if row[0] is not None:
            ids.add(row[0])
    return ids


def find_null_id_garbage(c):
    """Find garbage records with NULL id."""
    names = set()
    for clause, value in URL_AS_NAME_PATTERNS + SOCIAL_PAGE_PATTERNS:
        c.execute(f"SELECT name FROM churches WHERE id IS NULL AND {clause}", (value,))
        for row in c.fetchall():
            names.add(row[0])
    return sorted(names)


def main():
    print(f"Phase 2 — Remaining Garbage Cleanup  {datetime.now()}")
    db = sqlite3.connect(DB_PATH, timeout=60)
    db.execute("PRAGMA busy_timeout = 60000")
    db.execute("PRAGMA journal_mode = WAL")
    c = db.cursor()

    ids = find_garbage_ids(c)
    null_names = find_null_id_garbage(c)
    print(f"  Found {len(ids)} records with valid IDs, {len(null_names)} NULL-id records")

    # ---- Records with valid IDs ----
    if ids:
        c.execute(f"SELECT id, name, source FROM churches WHERE id IN ({','.join('?'*len(ids))}) ORDER BY source LIMIT 8", list(ids))
        print("  Sample:")
        for r in c.fetchall():
            print(f"    [{r[0]}] {r[2]!r}: {r[1][:80]}")

        placeholders = ",".join("?" * len(ids))
        id_list = list(ids)

        for tbl in CHILD_TABLES:
            try:
                c.execute(f"DELETE FROM {tbl} WHERE church_id IN ({placeholders})", id_list)
                if c.rowcount > 0:
                    print(f"  Deleted {c.rowcount} from {tbl}")
            except sqlite3.OperationalError as e:
                print(f"  SKIP {tbl}: {e}")

        for tbl in CHILD_TABLES_QUOTED:
            try:
                c.execute(f'DELETE FROM "{tbl}" WHERE church_id IN ({placeholders})', id_list)
                if c.rowcount > 0:
                    print(f"  Deleted {c.rowcount} from {tbl}")
            except sqlite3.OperationalError as e:
                print(f"  SKIP {tbl}: {e}")

        # Provenance
        print("  Logging provenance...")
        now = datetime.now(timezone.utc).isoformat()
        BATCH = 50
        for i in range(0, len(id_list), BATCH):
            batch = id_list[i:i+BATCH]
            placeholders_batch = ",".join("?" * len(batch))
            c.execute(
                f"INSERT INTO enrichment_change_log (church_id, field_name, old_value, new_value, change_source, enrichment_version, changed_at) "
                f"SELECT id, 'deleted_by_cleanup', NULL, 'page_artifact', 'cleanup_page_artifacts', NULL, ? FROM churches WHERE id IN ({placeholders_batch})",
                [now] + batch
            )
            print(f"    Provenance batch {i//BATCH+1}: {c.rowcount} entries")

        c.execute(f"DELETE FROM churches WHERE id IN ({placeholders})", id_list)
        print(f"  Deleted {c.rowcount} from churches")

    # ---- NULL-id records ----
    if null_names:
        print(f"  Deleting {len(null_names)} NULL-id records by name...")
        for name in null_names:
            c.execute("DELETE FROM churches WHERE id IS NULL AND name = ?", (name,))
            print(f"    Deleted {c.rowcount} row(s): {name[:60]}")

    db.commit()
    db.close()
    print(f"  Done! {datetime.now()}")


if __name__ == "__main__":
    main()
