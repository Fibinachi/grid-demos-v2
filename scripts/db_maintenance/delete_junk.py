"""Delete junk rows: GPX headers, EVENTS, NULL-id Wikipedia, NULL-id NRHP."""
import sqlite3
from datetime import datetime

DB = "E:/grid/churches.db"
NOW = datetime.utcnow().isoformat()
TODAY = datetime.utcnow().strftime("%Y-%m-%d")

db = sqlite3.connect(DB)
db.execute("PRAGMA synchronous=OFF")

# Count before
before = db.execute("SELECT COUNT(1) FROM churches").fetchone()[0]

# 1. GPX headers (Wikipedia import artifacts)
gpx = db.execute("DELETE FROM churches WHERE name LIKE 'GPX (%'").rowcount
print(f"GPX headers deleted: {gpx}")

# 2. Seacoast EVENTS
evts = db.execute("DELETE FROM churches WHERE name='EVENTS' AND source='seacoast_scraper'").rowcount
print(f"Seacoast EVENTS deleted: {evts}")

# 3. Wikipedia NULL-id (all 364 — no addresses, no coords, no city)
wiki = db.execute("DELETE FROM churches WHERE source='wikipedia_list' AND id IS NULL").rowcount
print(f"Wikipedia NULL-id deleted: {wiki}")

# 4. NRHP NULL-id (8,612 — enrichment already on real churches via nrhp_ref)
# Verify enrichment is safe first
real_nrhp = db.execute("SELECT COUNT(1) FROM churches WHERE nrhp_ref IS NOT NULL AND nrhp_ref != '' AND id IS NOT NULL").fetchone()[0]
print(f"Real churches with nrhp_ref (safe): {real_nrhp:,}")

nrhp = db.execute("DELETE FROM churches WHERE source='nrhp' AND id IS NULL").rowcount
print(f"NRHP NULL-id deleted: {nrhp:,}")

total_deleted = gpx + evts + wiki + nrhp

# Clean up church_sources for deleted rows
db.execute("DELETE FROM church_sources WHERE church_id NOT IN (SELECT id FROM churches)")
src_cleaned = db.execute("SELECT CHANGES()").fetchone()[0]
print(f"church_sources cleaned: {src_cleaned:,}")

# Verify
after = db.execute("SELECT COUNT(1) FROM churches").fetchone()[0]
geo = db.execute("SELECT COUNT(1) FROM churches WHERE latitude IS NOT NULL AND latitude != 0").fetchone()[0]
remain = db.execute("SELECT COUNT(1) FROM churches WHERE latitude IS NULL OR latitude = 0").fetchone()[0]

# Provenance
db.execute("""
    INSERT INTO provenance_log 
    (source, script_name, started_at, completed_at, churches_updated,
     churches_inserted, fields_populated, records_attempted, records_matched, status, notes)
    VALUES (?, ?, ?, ?, 0, 0, '', ?, 0, 'completed', ?)
""", ("data_cleanup", "delete_junk_rows.py", TODAY, TODAY, total_deleted,
      f"Deleted {total_deleted:,} junk rows: {gpx} GPX headers, {evts} EVENTS, {wiki} Wikipedia NULL-id, {nrhp} NRHP NULL-id"))

db.commit()
db.close()

print(f"\nBefore: {before:,}")
print(f"Deleted: {total_deleted:,}")
print(f"After: {after:,}")
print(f"Geocoded: {geo:,} ({geo*100/after:.0f}%)")
print(f"Remain: {remain:,}")
