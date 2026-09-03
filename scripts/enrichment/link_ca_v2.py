"""Insert + link CA pgeocode holy_sites."""
import sqlite3

DB = 'E:/grid/churches.db'
conn = sqlite3.connect(DB)
conn.execute("PRAGMA journal_mode=WAL")
conn.execute("PRAGMA busy_timeout=60000")
c = conn.cursor()

MARKER = "link_pgeocode_ca"

# Insert new holy_sites
c.execute("""INSERT INTO holy_sites (name, faith, country, lat, lon, source_primary, source_secondary, is_landmark, landmark_type, confidence_score)
    SELECT SUBSTR(COALESCE(c.name,''),1,500), c.faith, 'CA', c.latitude, c.longitude, 'pgeocode', ?, 0, 'church', 0.5
    FROM churches c WHERE c.holy_site_id IS NULL AND c.latitude IS NOT NULL AND c.geocode_source='pgeocode_ca'""", (MARKER,))
print(f"New holy_sites: {c.rowcount:,}")
conn.commit()

# Temp table for fast link-back
c.execute(f"CREATE TEMP TABLE _bf AS SELECT site_id, ROUND(lat,6) rlat, ROUND(lon,6) rlon FROM holy_sites WHERE source_secondary='{MARKER}'")
c.execute("CREATE INDEX _bf_idx ON _bf(rlat, rlon)")

c.execute("""UPDATE churches SET holy_site_id = (
    SELECT b.site_id FROM _bf b WHERE b.rlat=ROUND(churches.latitude,6) AND b.rlon=ROUND(churches.longitude,6) LIMIT 1)
    WHERE holy_site_id IS NULL AND latitude IS NOT NULL AND geocode_source='pgeocode_ca'""")
print(f"Linked back: {c.rowcount:,}")
conn.commit()

# Clean marker
c.execute(f"UPDATE holy_sites SET source_secondary=NULL WHERE source_secondary='{MARKER}'")
conn.commit()

c.execute("SELECT COUNT(*) FROM churches WHERE country='CA' AND holy_site_id IS NOT NULL")
print(f"\nCA linked: {c.fetchone()[0]:,}")
c.execute("SELECT COUNT(*) FROM churches WHERE country='CA'")
print(f"CA total: {c.fetchone()[0]:,}")

conn.close()
print("Done.")
