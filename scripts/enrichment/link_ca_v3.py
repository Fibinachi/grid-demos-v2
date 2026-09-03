"""Link-back only — holy_sites already inserted."""
import sqlite3

DB = 'E:/grid/churches.db'
conn = sqlite3.connect(DB)
conn.execute("PRAGMA journal_mode=WAL")
conn.execute("PRAGMA busy_timeout=60000")
c = conn.cursor()

MARKER = "link_pgeocode_ca"

# Tag the newly inserted holy_sites
c.execute(f"UPDATE holy_sites SET source_secondary=? WHERE source_primary='pgeocode' AND source_secondary IS NULL", (MARKER,))
print(f"Tagged: {c.rowcount:,}")

# Temp table for fast link-back
c.execute(f"CREATE TEMP TABLE _bf AS SELECT site_id, ROUND(lat,6) rlat, ROUND(lon,6) rlon FROM holy_sites WHERE source_secondary='{MARKER}'")
c.execute("CREATE INDEX _bf_idx ON _bf(rlat, rlon)")

# Link
c.execute("""UPDATE churches SET holy_site_id = (
    SELECT b.site_id FROM _bf b WHERE b.rlat=ROUND(churches.latitude,6) AND b.rlon=ROUND(churches.longitude,6) LIMIT 1)
    WHERE holy_site_id IS NULL AND latitude IS NOT NULL AND geocode_source='pgeocode_ca'""")
print(f"Linked: {c.rowcount:,}")
conn.commit()

# Clean
c.execute(f"UPDATE holy_sites SET source_secondary=NULL WHERE source_secondary='{MARKER}'")
conn.commit()

c.execute("SELECT COUNT(*) FROM churches WHERE country='CA' AND holy_site_id IS NOT NULL")
print(f"\nCA linked: {c.fetchone()[0]:,}")

conn.close()
print("Done.")
