"""
Fix the Amchitka city bug: delete junk records + reset city for 151K records.
Run BEFORE reverse_geocode_nominatim_local.py --all

Step 1: Delete known junk OSM imports
Step 2: Set city=NULL for all records with city='Amchitka'
Step 3: Run: python scripts/enrichment/reverse_geocode_nominatim_local.py --all --limit=N
"""

import sqlite3, sys, os
from datetime import datetime, timezone

DB = 'E:/grid/churches.db'
SCRIPT = os.path.basename(__file__)
NOW = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')

# ── Junk records to delete ──
JUNK_IDS = [4936906, 4936907, 4947555]  # Gnome Log, Frog Pond, Old Mechanics Garage

db = sqlite3.connect(DB)
db.execute("PRAGMA journal_mode=WAL")

# ── Step 1: Verify junk records ──
print("=== Step 1: Deleting junk records ===")
deleted = 0
for jid in JUNK_IDS:
    row = db.execute("SELECT id, name, city, landmark_type, latitude, longitude, state FROM churches WHERE id=?", (jid,)).fetchone()
    if row:
        print(f"  DELETE id={row[0]} | '{row[1]}' | type={row[3]} | {row[4]},{row[5]} | {row[6]}")
        db.execute("DELETE FROM churches WHERE id=?", (jid,))
        deleted += 1
    else:
        print(f"  SKIP id={jid} — already deleted")

db.commit()
print(f"  Deleted: {deleted}")

# ── Step 2: Amchitka bug — set city=NULL ──
print("\n=== Step 2: Resetting city='Amchitka' → NULL ===")
count = db.execute("SELECT COUNT(*) FROM churches WHERE city='Amchitka'").fetchone()[0]
print(f"  Records with city='Amchitka': {count:,}")

if count > 0:
    db.execute("UPDATE churches SET city=NULL WHERE city='Amchitka'")
    db.commit()
    
    # Verify
    remaining = db.execute("SELECT COUNT(*) FROM churches WHERE city='Amchitka'").fetchone()[0]
    null_us = db.execute("SELECT COUNT(*) FROM churches WHERE country='US' AND city IS NULL AND latitude IS NOT NULL").fetchone()[0]
    print(f"  After reset: {remaining} remaining with city='Amchitka'")
    print(f"  US churches with city=NULL (ready for geocode): {null_us:,}")

# ── Provenance ──
db.execute("""INSERT INTO provenance_log (source, script_name, started_at, completed_at, status, notes)
              VALUES ('fix_amchitka',?,?,?,?,'completed',?)""",
           (SCRIPT, NOW, datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'),
            f"Deleted {deleted} junk OSM records + reset city=NULL for {count:,} Amchitka-mislabeled records"))
db.commit()

# ── Summary ──
print(f"\n=== DONE ===")
print(f"  Deleted: {deleted} junk records")
print(f"  City reset: {count:,} Amchitka → NULL")
print(f"\n  Next: python scripts/enrichment/reverse_geocode_nominatim_local.py --all")

db.close()
