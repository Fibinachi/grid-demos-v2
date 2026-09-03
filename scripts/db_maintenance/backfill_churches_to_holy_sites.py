"""Backfill unlinked churches into holy_sites table.
Two-pass approach:
  1. Link churches to existing holy_sites by coordinate match
  2. Insert remaining as new holy_sites, then link back
"""
import sqlite3
from datetime import datetime, timezone

NOW = datetime.now(timezone.utc).isoformat()
DB = 'E:/grid/churches.db'

conn = sqlite3.connect(DB)
conn.execute("PRAGMA journal_mode=WAL")
conn.execute("PRAGMA busy_timeout=60000")
conn.execute("PRAGMA cache_size=-2000000")  # 2GB cache
c = conn.cursor()

# ── Stats ──
c.execute("SELECT COUNT(*) FROM churches WHERE holy_site_id IS NULL")
total_unlinked = c.fetchone()[0]
c.execute("SELECT COUNT(*) FROM churches WHERE holy_site_id IS NULL AND latitude IS NOT NULL")
with_coords = c.fetchone()[0]
print(f"Unlinked total: {total_unlinked:,}")
print(f"Unlinked with coords: {with_coords:,}")

# ── Pass 1: Link to existing holy_sites by exact coordinate match ──
print("\nPass 1: Linking to existing holy_sites by coordinate match...")

# Build lookup: (rounded_lat, rounded_lon) -> site_id
c.execute("SELECT site_id, ROUND(lat,5), ROUND(lon,5) FROM holy_sites WHERE lat IS NOT NULL")
hs_lookup = {}
for site_id, lat, lon in c.fetchall():
    hs_lookup[(lat, lon)] = site_id
print(f"  {len(hs_lookup):,} unique coordinate cells in holy_sites")

# Find matches
c.execute("""
    SELECT id, ROUND(latitude,5), ROUND(longitude,5) 
    FROM churches 
    WHERE holy_site_id IS NULL AND latitude IS NOT NULL
""")
matches = []
for church_id, lat, lon in c.fetchall():
    key = (lat, lon)
    if key in hs_lookup:
        matches.append((hs_lookup[key], church_id))

print(f"  Found {len(matches):,} coordinate matches")

if matches:
    # Batch update in chunks
    chunk = 10000
    for i in range(0, len(matches), chunk):
        batch = matches[i:i+chunk]
        c.executemany("UPDATE churches SET holy_site_id=? WHERE id=?", batch)
        if i % 50000 == 0:
            print(f"  Linked {min(i+chunk, len(matches)):,}/{len(matches):,}...")
    conn.commit()
    print(f"  Pass 1 done: {len(matches):,} linked to existing holy_sites")

# ── Pass 2: Insert remaining as new holy_sites ──
c.execute("SELECT COUNT(*) FROM churches WHERE holy_site_id IS NULL AND latitude IS NOT NULL")
remaining = c.fetchone()[0]
print(f"\nPass 2: {remaining:,} remaining to insert as new holy_sites")

BACKFILL_TAG = "backfill_20260618"

if remaining > 0:
    # Use a marker in source_secondary to identify backfilled rows
    print("  Inserting churches as new holy_sites...")
    
    c.execute("""
        INSERT INTO holy_sites 
        (name, faith, tradition, country, lat, lon, 
         source_primary, source_secondary, is_landmark, landmark_type,
         wikidata_qid, osm_id, confidence_score, denomination)
        SELECT 
            SUBSTR(COALESCE(c.name,''), 1, 500),
            c.faith,
            NULL,
            c.country,
            c.latitude,
            c.longitude,
            c.source,
            ?,
            0,
            CASE 
                WHEN c.landmark_type IS NOT NULL AND c.landmark_type != '' THEN c.landmark_type
                WHEN c.mosque_type IS NOT NULL AND c.mosque_type != '' THEN c.mosque_type
                ELSE 'church'
            END,
            c.wikidata_qid,
            c.osm_id,
            0.5,
            c.denomination
        FROM churches c
        WHERE c.holy_site_id IS NULL AND c.latitude IS NOT NULL
    """, (BACKFILL_TAG,))
    
    inserted = c.rowcount
    print(f"  Inserted {inserted:,} rows into holy_sites")
    conn.commit()
    
    # Link back: update churches.holy_site_id by joining on coordinates + source
    print("  Linking churches back to new holy_sites...")
    c.execute("""
        UPDATE churches SET holy_site_id = (
            SELECT h.site_id FROM holy_sites h
            WHERE h.source_secondary = ?
              AND ROUND(h.lat, 6) = ROUND(churches.latitude, 6)
              AND ROUND(h.lon, 6) = ROUND(churches.longitude, 6)
              AND h.source_primary = churches.source
            LIMIT 1
        )
        WHERE holy_site_id IS NULL 
          AND latitude IS NOT NULL
    """, (BACKFILL_TAG,))
    
    linked = c.rowcount
    print(f"  Linked {linked:,} churches")
    conn.commit()
    
    # Clean up the marker
    c.execute("UPDATE holy_sites SET source_secondary = NULL WHERE source_secondary = ?", (BACKFILL_TAG,))
    conn.commit()
    print("  Cleaned up markers")

# ── Verify ──
c.execute("SELECT COUNT(*) FROM churches WHERE holy_site_id IS NULL")
still_unlinked = c.fetchone()[0]
c.execute("SELECT COUNT(*) FROM holy_sites")
hs_total = c.fetchone()[0]
c.execute("SELECT COUNT(DISTINCT holy_site_id) FROM churches WHERE holy_site_id IS NOT NULL")
unique_links = c.fetchone()[0]

print(f"\n=== Results ===")
print(f"  Still unlinked (no coords): {still_unlinked:,}")
print(f"  holy_sites total: {hs_total:,}")
print(f"  Unique holy_site_ids used: {unique_links:,}")

# ── Provenance ──
c.execute("""
    INSERT INTO provenance_log 
    (source, script_name, started_at, completed_at, churches_inserted,
     fields_populated, records_attempted, records_matched, status, notes)
    VALUES(?,?,?,?,?,?,?,?,'completed',?)
""", (
    "manual",
    "backfill_churches_to_holy_sites.py",
    NOW, datetime.now(timezone.utc).isoformat(),
    0,
    "holy_site_id",
    with_coords,
    with_coords,
    f"Backfilled churches→holy_sites: {len(matches):,} linked to existing + {inserted:,} new holy_sites created"
))
conn.commit()
conn.close()
print("\nDone.")
