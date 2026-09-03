"""Fast link-back for backfilled holy_sites using temp table + index."""
import sqlite3
import time

DB = 'E:/grid/churches.db'
BACKFILL_TAG = "backfill_20260618"

conn = sqlite3.connect(DB)
conn.execute("PRAGMA journal_mode=WAL")
conn.execute("PRAGMA busy_timeout=60000")
c = conn.cursor()

t0 = time.time()

# Check how many are still unlinked
c.execute("SELECT COUNT(*) FROM churches WHERE holy_site_id IS NULL AND latitude IS NOT NULL")
unlinked = c.fetchone()[0]
print(f"Unlinked with coords: {unlinked:,}")

if unlinked == 0:
    print("All linked already!")
    conn.close()
    exit()

# Check how many backfill-tagged holy_sites exist
c.execute("SELECT COUNT(*) FROM holy_sites WHERE source_secondary = ?", (BACKFILL_TAG,))
tagged = c.fetchone()[0]
print(f"Backfill-tagged holy_sites: {tagged:,}")

# Create temp table with backfilled site_ids + coords + source
print("Building mapping table...")
c.execute("""
    CREATE TEMP TABLE _hs_backfill AS
    SELECT site_id, ROUND(lat,6) as rlat, ROUND(lon,6) as rlon, source_primary
    FROM holy_sites 
    WHERE source_secondary = ?
""", (BACKFILL_TAG,))
c.execute("CREATE INDEX _hs_bf_idx ON _hs_backfill(rlat, rlon, source_primary)")
print(f"  Mapping table built in {time.time()-t0:.1f}s")

# Update churches using the temp table
print("Updating churches.holy_site_id...")
c.execute("""
    UPDATE churches SET holy_site_id = (
        SELECT h.site_id FROM _hs_backfill h
        WHERE h.rlat = ROUND(churches.latitude, 6)
          AND h.rlon = ROUND(churches.longitude, 6)
          AND h.source_primary = churches.source
        LIMIT 1
    )
    WHERE holy_site_id IS NULL 
      AND latitude IS NOT NULL
""")
print(f"  Linked {c.rowcount:,} churches in {time.time()-t0:.1f}s")
conn.commit()

# Clean up markers
c.execute("UPDATE holy_sites SET source_secondary = NULL WHERE source_secondary = ?", (BACKFILL_TAG,))
conn.commit()

# Verify
c.execute("SELECT COUNT(*) FROM churches WHERE holy_site_id IS NULL")
still = c.fetchone()[0]
c.execute("SELECT COUNT(*) FROM holy_sites")
hs_total = c.fetchone()[0]
print(f"\nStill unlinked (no coords): {still:,}")
print(f"holy_sites total: {hs_total:,}")
print(f"Done in {time.time()-t0:.1f}s")

conn.close()
