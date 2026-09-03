#!/usr/bin/env python3
"""
Direct cleanup: delete page-artifact records.
Uses raw sqlite3 with long timeout. Handles only tables with church_id.
"""
import sqlite3
import json
from datetime import datetime, timezone

DB_PATH = r"E:\grid\churches.db"

GARBAGE_IDS = [
    296572, 296591, 387433, 326663, 326666, 326670, 326950, 327031, 327038,
    327055, 327082, 327083, 327086, 327090, 327104, 327405, 327408, 327467,
    327509, 327512, 327705, 327716, 327728, 327730, 327759, 327760, 327761,
    327762, 327766, 327770, 327771, 327785, 327786, 327788, 327801, 327802,
    327805, 327807, 327813, 327817, 327819, 327820, 327821, 327830, 327835,
    327837, 327963, 327969, 327971, 328039, 328040, 328041, 328044, 328048,
    328051, 328063, 328067, 328069, 328070, 328073, 328074, 328085, 328100,
    328105, 328113, 328120, 328134, 328137, 328192, 328215, 328218, 328223,
    328403, 328431, 328459, 328462, 328463, 328466, 328470, 328472, 328483,
    328484, 328564, 328569, 328572, 328573, 328575, 328576, 328578, 328579,
    328580, 328583, 328586, 328588, 328589, 328590, 328591, 328592, 328593,
    328597, 328599, 328602, 328764, 328765, 328769, 328774, 328779, 328793,
    328800, 328802, 328807, 328808, 328993, 329881, 329882, 329883, 329884,
    330058, 330066, 330074, 331351, 332228, 332229, 332230, 332231, 332236,
    332304, 332305, 332338, 332748, 332894, 332900, 332902, 332903, 332907,
    332910, 332912, 332913, 332914, 332916, 332917, 334378, 334416, 359429,
    441774, 447593, 508394, 517953, 545469, 586657, 593030, 627175, 675610,
    691118, 709693, 760379, 791965,
]

# Tables confirmed to have a church_id column
CHILD_TABLES = [
    "_attendance_results", "attendance_history",
    "broadcast_ministries", "church_census_us", "church_arda",
    "church_broadband", "church_broadcast", "church_classification_meta",
    "church_contacts", "church_enrichment", "church_fcc",
    "church_food_desert", "church_gnis", "church_metro_area",
    "church_nrhp", "church_operations", "church_postal_admin",
    "church_sources", "church_staff", "church_territories",
    "church_vacancies", "enrichment_change_log",
    "org_links", "org_officers",
]


def main():
    print(f"Page Artifact Cleanup — {datetime.now()}")
    print(f"  IDs to delete: {len(GARBAGE_IDS)}")
    print()

    db = sqlite3.connect(DB_PATH, timeout=60)
    db.execute("PRAGMA busy_timeout = 60000")
    db.execute("PRAGMA journal_mode = WAL")
    c = db.cursor()

    # Verify all IDs exist
    placeholders = ",".join("?" * len(GARBAGE_IDS))
    c.execute(f"SELECT id FROM churches WHERE id IN ({placeholders})", GARBAGE_IDS)
    existing = {r[0] for r in c.fetchall()}
    missing = set(GARBAGE_IDS) - existing
    if missing:
        print(f"  WARNING: {len(missing)} IDs not found — already deleted?")
        for m in sorted(missing):
            print(f"    {m}")
        to_delete = list(existing)
    else:
        to_delete = list(GARBAGE_IDS)

    print(f"  Deleting: {len(to_delete)} records")
    print()

    # Delete from child tables (one by one, skip if column missing)
    placeholders = ",".join("?" * len(to_delete))
    for tbl in CHILD_TABLES:
        try:
            c.execute(f"DELETE FROM {tbl} WHERE church_id IN ({placeholders})", to_delete)
            if c.rowcount > 0:
                print(f"  Deleted {c.rowcount} from {tbl}")
        except sqlite3.OperationalError as e:
            print(f"  SKIP {tbl}: {e}")

    # Log provenance (enrichment_change_log entries for each deletion)
    print(f"\n  Logging provenance...")
    now = datetime.now(timezone.utc).isoformat()
    changes = []
    for church_id in to_delete:
        changes.append((
            church_id, "deleted_by_cleanup", None, "page_artifact",
            "cleanup_page_artifacts", None, now
        ))
    c.executemany(
        "INSERT INTO enrichment_change_log (church_id, field_name, old_value, new_value, change_source, enrichment_version, changed_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
        changes
    )
    print(f"  Inserted {len(changes)} provenance entries")

    # Delete from churches
    c.execute(f"DELETE FROM churches WHERE id IN ({placeholders})", to_delete)
    print(f"  Deleted {c.rowcount} from churches")

    db.commit()
    db.close()
    print(f"\n  Done! {datetime.now()}")


if __name__ == "__main__":
    main()
