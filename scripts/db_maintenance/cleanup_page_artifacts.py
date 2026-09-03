#!/usr/bin/env python3
"""
Cleanup: remove church records whose `name` field is clearly a page artifact
(news article titles, job postings, .html filenames, social pages, bare URLs)
rather than an actual religious site name.

Strategy:
  1. Identify garbage records by pattern-matching the `name` field.
  2. For .html records that have a clean duplicate (same name sans .html),
     delete only the .html copy.
  3. Delete remaining garbage records from all child tables, then from churches.
  4. Log every deletion in provenance_log.

Usage:  python scripts/db_maintenance/cleanup_page_artifacts.py
        python scripts/db_maintenance/cleanup_page_artifacts.py --dry-run   # preview only
"""
import sys
import os
import json
from datetime import datetime

# Ensure e:\grid is in sys.path for gw_db import
_grid_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _grid_root not in sys.path:
    sys.path.insert(0, _grid_root)

from gw_db import connect, log_change

DRY_RUN = "--dry-run" in sys.argv

# ──────────────────────────────────────────────────────────────
# 1.  Define garbage patterns (catholic_diocese_scrape source)
# ──────────────────────────────────────────────────────────────
CATHOLIC_PATTERNS = [
    # Maintenance / job postings
    "name LIKE '%MAINTENANCE%'",
    "name LIKE '%LITURGY AND MUSIC%'",
    "name LIKE '%LIMITED PART TIME%'",
    "name LIKE '%LAY ECCLESIAL%'",
    "name LIKE '% DIRECTOR %'",
    "name LIKE '% TECHNICIAN%'",
    "name LIKE '% ASSISTANT'",
    # .html filenames (article titles with .html extension)
    "name LIKE '%.html'",
    "name LIKE '%.HTM'",
    # Social/media page names
    "name LIKE '%PUBLIC PAGE%'",
    "name LIKE '%GROUP PAGE%'",
    "name LIKE '%MEMORIAL PAGE%'",
    # Media advisories / press releases
    "name LIKE 'MEDIA ADVISORY%'",
    "name LIKE 'MEDIA ALERT%'",
    # Event / bingo / announcement pages
    "name LIKE '%JACKPOT BINGO%'",
    "name LIKE '%ICE CREAM SOCIAL%'",
    "name LIKE 'MASS TIMES%'",
    "name LIKE 'LOCATOR%'",
    "name LIKE 'INSTITUTIONAL RECORDS%'",
    "name LIKE '%MARRIAGE PREPARATION%'",
    "name LIKE 'IDEAS GUIDELINES%'",
    # News article titles (identifiably not church names)
    "name LIKE 'POPE %'",
    "name LIKE 'CATHOLIC CHURCH %'",
    "name LIKE 'VATICAN %'",
    "name LIKE 'BISHOP %'",
    "name LIKE 'MAN CHARGED%'",
    "name LIKE 'MASSIVE TURNING%'",
    "name LIKE 'LEAKED EMAILS%'",
    "name LIKE 'IS THE CATHOLIC CHURCH%'",
    "name LIKE 'IS THIS%'",
    "name LIKE 'KENYAN%'",
    "name LIKE 'MADAGASCAR%'",
    "name LIKE 'KYIVS%'",
    "name LIKE 'IN METOO%'",
    "name LIKE 'IN THIS TIKTOK%'",
    "name LIKE 'JOINING CATHOLIC%'",
    "name LIKE 'IGNORING%'",
    "name LIKE 'IF YOURE%'",
    "name LIKE 'FEAST HIGHLIGHTS%'",
    "name LIKE 'ICYMI%'",
    "name LIKE 'ICONOSTASIS%'",
    "name LIKE 'PUERTO RICO%'",
    "name LIKE 'ONE YEAR OF%'",
    "name LIKE 'MUSLIM FATHER%'",
    "name LIKE 'NEW GLOBAL INITIATIVE%'",
    "name LIKE 'AFTER CANADA%'",
    "name LIKE 'INTERRELIGIOUS DIALOGUE%'",
    "name LIKE 'INSTALLATION OF FR%'",
    "name LIKE 'INDIANA INMATES%'",
    "name LIKE 'INDIAS SYRO%'",
    "name LIKE 'JEFF CAVINS%'",
    "name LIKE 'MARRYING IN%'",
    "name LIKE 'MARSHFIELD PARK RIDE%'",
    "name LIKE 'MEMPHIS CATHOLIC SCHOOLS%'",
    "name LIKE 'MEMPHIS JOY PROM%'",
    "name LIKE 'LENTEN PENANCE%'",
    "name LIKE 'LENTEN MISSION%'",
    "name LIKE 'LENTEN DISPLAY%'",
    "name LIKE 'KJZT%'",
    "name LIKE 'LETTER FROM%'",
    "name LIKE 'INDICATIONS OF%'",
    "name LIKE 'JUBILEE YEAR%'",
    "name LIKE 'IN CENTRAL AFRICA%'",
    "name LIKE 'MEDIA%'",
    "name LIKE 'LENTEN%'",
    # Random filenames / image names
    "name LIKE 'IMG%'",
    "name LIKE 'JPII GROUP%'",
    "name LIKE '%UNSPLASH%'",
    "name LIKE 'JEN COUSER%'",
    # "THE CATHOLIC CHURCH" used as a heading/article title (not church name)
    "name LIKE 'THE CATHOLIC CHURCH %'",
]

SOCIAL_PAGE_PATTERNS = [
    # Social/media page names from any source (not just catholic_diocese_scrape)
    "name LIKE '%PUBLIC PAGE%'",
    "name LIKE '%GROUP PAGE%'",
    "name LIKE '%MEMORIAL PAGE%'",
]

URL_AS_NAME_PATTERNS = [
    # Names that are purely URLs with no descriptive text
    "name LIKE 'http://%'",
    "name LIKE 'https://%'",
    "name LIKE 'Https://%'",
    "name LIKE 'www.%'",
    "name LIKE '%goo.gl/maps%'",
]


def find_garbage_ids(c):
    """Return set of church IDs that match garbage patterns."""
    all_ids = set()

    # Catholic diocese scrape patterns (excluding .html dedup handling)
    catholic_where = " OR ".join(CATHOLIC_PATTERNS)
    c.execute(f"SELECT id, name FROM churches WHERE source = 'catholic_diocese_scrape' AND ({catholic_where})")
    for row in c.fetchall():
        all_ids.add(row[0])

    # Social pages from any source (excluding catholic_diocese_scrape already counted)
    social_where = " OR ".join(SOCIAL_PAGE_PATTERNS)
    c.execute(f"SELECT id, name FROM churches WHERE source != 'catholic_diocese_scrape' AND ({social_where})")
    for row in c.fetchall():
        all_ids.add(row[0])

    # Pure URL-as-name from any source
    url_where = " OR ".join(URL_AS_NAME_PATTERNS)
    c.execute(f"SELECT id, name FROM churches WHERE ({url_where})")
    for row in c.fetchall():
        all_ids.add(row[0])

    # Handle .html dedup: if a .html record has a clean duplicate, add ONLY the .html one
    c.execute("""
        SELECT c1.id, c1.name FROM churches c1
        WHERE (c1.name LIKE '%.html' OR c1.name LIKE '%.HTM')
          AND EXISTS (
              SELECT 1 FROM churches c2
              WHERE c2.name = SUBSTR(c1.name, 1, LENGTH(c1.name) - CASE
                  WHEN c1.name LIKE '%.html' THEN 5
                  WHEN c1.name LIKE '%.HTM' THEN 4
                  ELSE 0 END)
              AND c2.id != c1.id
          )
    """)
    for row in c.fetchall():
        all_ids.add(row[0])  # Only the .html duplicate gets deleted

    return all_ids


def find_child_tables(c):
    """Find all tables that reference churches(id)."""
    c.execute("SELECT name, sql FROM sqlite_master WHERE type='table' AND sql LIKE '%REFERENCES%churches%'")
    tables = []
    for name, sql in c.fetchall():
        if "REFERENCES churches(" in sql or "REFERENCES churches (" in sql:
            tables.append(name)
    return tables


def delete_garbage(db, ids, child_tables):
    """Delete records from all child tables + churches, with provenance."""
    c = db.cursor()
    total_deleted = {"churches": 0}
    id_list = list(ids)

    # Delete from child tables first
    for tbl in child_tables:
        c.execute(f"DELETE FROM {tbl} WHERE church_id IN ({','.join('?'*len(id_list))})", id_list)
        total_deleted[tbl] = c.rowcount
        print(f"  Deleted {c.rowcount} from {tbl}")

    # Delete from churches
    c.execute(f"DELETE FROM churches WHERE id IN ({','.join('?'*len(id_list))})", id_list)
    total_deleted["churches"] = c.rowcount
    print(f"  Deleted {c.rowcount} from churches")

    # Log provenance
    details = {
        "action": "cleanup_page_artifacts",
        "pattern_count": len(CATHOLIC_PATTERNS) + len(SOCIAL_PAGE_PATTERNS) + len(URL_AS_NAME_PATTERNS),
        "child_tables_cleaned": child_tables,
        "deleted_counts": total_deleted,
        "dry_run": DRY_RUN,
    }

    for church_id in id_list:
        log_change(
            db=db,
            church_id=church_id,
            source="cleanup_page_artifacts",
            action="deleted",
            details=json.dumps({"reason": "page_artifact_name", "deleted_counts": total_deleted}),
        )

    db.commit()
    return total_deleted


def main():
    print(f"{'DRY RUN — ' if DRY_RUN else ''}Page Artifact Cleanup")
    print(f"Started: {datetime.now()}")
    print()

    db = connect()
    c = db.cursor()

    # Find garbage
    print("Finding garbage records…")
    ids = find_garbage_ids(c)
    print(f"  Found {len(ids)} garbage records")

    if not ids:
        print("  Nothing to clean. Exiting.")
        db.close()
        return

    # Show sample
    c.execute(f"SELECT id, name, source FROM churches WHERE id IN ({','.join('?'*len(ids))}) LIMIT 20", list(ids))
    print("  Sample records:")
    for r in c.fetchall():
        print(f"    [{r[0]}] {r[2]!r}: {r[1][:100]}")

    # Find child tables
    child_tables = find_child_tables(c)
    print(f"\n  Child tables to clean: {child_tables}")

    # Also add known tables that might be missed
    extra_tables = [
        "church_contacts", "church_enrichment", "church_sources",
        "church_census_us", "church_fcc", "church_gnis", "church_nrhp",
        "church_rucc", "church_broadband", "church_metro_area",
        "church_postal_admin", "church_classification_meta",
        "provenance_log", "enrichment_change_log",
    ]
    for t in extra_tables:
        if t not in child_tables:
            child_tables.append(t)
    print(f"  Total tables to clean: {len(child_tables)}")

    if DRY_RUN:
        print("\n  DRY RUN — no changes made.")
        db.close()
        return

    # Confirm
    print(f"\n  Deleting {len(ids)} garbage records…")
    total = delete_garbage(db, ids, child_tables)
    print(f"\n  Done. Summary: {total}")
    db.close()


if __name__ == "__main__":
    main()
