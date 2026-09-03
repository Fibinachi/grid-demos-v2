"""Backfill provenance_log and church_sources for 2026-06-17 operations."""
import sqlite3
from datetime import datetime

DB = "E:/grid/churches.db"
NOW = datetime.utcnow().isoformat()

db = sqlite3.connect(DB)

# ── Operations to log ──
ops = [
    # (source, script, churches_inserted, churches_updated, fields, notes)
    ("overture_full", "import_overture_full.py", 234646, 0,
     "name,address,city,state,zip,country,latitude,longitude",
     "Overture Maps full US church extraction — coordinates from Overture"),
    ("overture_canada", "import_overture_mx_ca.py", 3198, 0,
     "name,address,city,state,zip,country,latitude,longitude",
     "Overture Maps Canada church extraction"),
    ("overture_mexico", "import_overture_mx_ca.py", 2372, 0,
     "name,address,city,state,zip,country,latitude,longitude",
     "Overture Maps Mexico church extraction"),
    ("churchunion_scraper", "import_churchunion.py", 83247, 0,
     "name,address,city,state,county_name",
     "ChurchUnion.us directory — 165,064 scraped, 83,247 new after dedup"),
    ("census_batch", "geocode_cu_export.py", 0, 42731,
     "latitude,longitude,tract_fips,geocode_source,tract_geocode_source,tract_geocode_date",
     "Census batch geocoding of ChurchUnion rows — 500/batch, 74% hit rate"),
]

for source, script, inserted, updated, fields, notes in ops:
    # Check if already logged
    existing = db.execute(
        "SELECT id FROM provenance_log WHERE source=? AND script_name=?",
        (source, script)).fetchone()
    if existing:
        print(f"  SKIP {source} — already logged (id={existing[0]})")
        continue
    
    db.execute("""
        INSERT INTO provenance_log 
        (source, script_name, started_at, completed_at, churches_updated,
         churches_inserted, fields_populated, records_attempted, records_matched,
         status, notes)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'completed', ?)
    """, (source, script, NOW, NOW, updated, inserted, fields,
          inserted + updated, updated, notes))
    print(f"  LOGGED {source}: {inserted:,} ins, {updated:,} upd")

# ── Backfill church_sources for missing sources ──
print("\n=== church_sources backfill ===")
sources = [
    ("overture_full", "churchunion_scraper"),
    ("overture_canada", "import_overture_mx_ca.py"),
    ("overture_mexico", "import_overture_mx_ca.py"),
    ("churchunion_scraper", "import_churchunion.py"),
]

for church_source, source_name in sources:
    # Count missing
    missing = db.execute("""
        SELECT COUNT(1) FROM churches c
        WHERE c.source = ?
        AND c.id NOT IN (SELECT church_id FROM church_sources WHERE source_name = ?)
    """, (church_source, source_name)).fetchone()[0]
    
    if missing == 0:
        print(f"  {church_source}: already complete")
        continue
    
    print(f"  {church_source}: {missing:,} missing church_sources entries...", end=" ", flush=True)
    
    # Insert missing
    db.execute("""
        INSERT OR IGNORE INTO church_sources (church_id, source_name, source_url, notes)
        SELECT c.id, ?, '', ?
        FROM churches c
        WHERE c.source = ?
        AND c.id NOT IN (SELECT church_id FROM church_sources WHERE source_name = ?)
    """, (source_name, f"bulk import 2026-06-17", church_source, source_name))
    db.commit()
    print("done")

db.commit()
db.close()

# Verify
db = sqlite3.connect(DB)
total_prov = db.execute("SELECT COUNT(1) FROM provenance_log").fetchone()[0]
total_src = db.execute("SELECT COUNT(1) FROM church_sources").fetchone()[0]
db.close()
print(f"\nprovenance_log: {total_prov} entries (was 79)")
print(f"church_sources: {total_src:,} entries")
