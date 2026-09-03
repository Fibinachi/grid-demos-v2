"""Link pgeocode_ca churches to holy_sites — clean run."""
import sqlite3, time

DB = 'E:/grid/churches.db'
t0 = time.time()

conn = sqlite3.connect(DB)
conn.execute("PRAGMA journal_mode=WAL")
conn.execute("PRAGMA busy_timeout=60000")
c = conn.cursor()

# Build grid from holy_sites  
print("Building grid...")
c.execute("CREATE TEMP TABLE IF NOT EXISTS _hsg (rlat REAL, rlon REAL, site_id INTEGER)")
c.execute("INSERT INTO _hsg SELECT ROUND(lat,5), ROUND(lon,5), site_id FROM holy_sites WHERE lat IS NOT NULL")
print(f"  Grid: {c.rowcount:,} rows in {time.time()-t0:.1f}s")
c.execute("CREATE INDEX IF NOT EXISTS _hsg_idx ON _hsg(rlat, rlon)")
print(f"  Index: {time.time()-t0:.1f}s")

# Verify grid has data
c.execute("SELECT COUNT(*) FROM _hsg")
print(f"  Grid verify: {c.fetchone()[0]:,} rows")

# Link
print("Linking...")
c.execute("""UPDATE churches SET holy_site_id = (
    SELECT g.site_id FROM _hsg g
    WHERE g.rlat = ROUND(churches.latitude,5) AND g.rlon = ROUND(churches.longitude,5) LIMIT 1)
    WHERE holy_site_id IS NULL AND latitude IS NOT NULL AND geocode_source='pgeocode_ca'""")
print(f"  Linked: {c.rowcount:,} in {time.time()-t0:.1f}s")
conn.commit()

# Verify
c.execute("SELECT COUNT(*) FROM churches WHERE country='CA' AND geocode_source='pgeocode_ca' AND holy_site_id IS NOT NULL")
print(f"\nCA pgeocode linked: {c.fetchone()[0]:,}")
c.execute("SELECT COUNT(*) FROM churches WHERE country='CA' AND holy_site_id IS NOT NULL")
print(f"CA total linked: {c.fetchone()[0]:,}")

# Create new holy_sites for unlinked
c.execute("SELECT COUNT(*) FROM churches WHERE holy_site_id IS NULL AND latitude IS NOT NULL AND geocode_source='pgeocode_ca'")
unlinked = c.fetchone()[0]
print(f"Still unlinked: {unlinked:,}")

if unlinked > 0:
    # Get existing grid
    c.execute("SELECT rlat, rlon FROM _hsg")
    grid = set(c.fetchall())
    
    c.execute("SELECT id, name, faith, country, latitude, longitude FROM churches WHERE holy_site_id IS NULL AND latitude IS NOT NULL AND geocode_source='pgeocode_ca'")
    new_hs = 0
    for ch_id, name, faith, country, lat, lon in c.fetchall():
        gl, gn = round(lat, 4), round(lon, 4)
        if (round(lat,5), round(lon,5)) not in {(r[0], r[1]) for r in list(grid)[:1]}:
            pass  # Skip grid check - just insert
        c.execute("INSERT INTO holy_sites(name,faith,country,lat,lon,source_primary,is_landmark,landmark_type,confidence_score) VALUES(?,?,?,?,?,?,?,?,?)",
                 ((name or '')[:500], faith, country, lat, lon, 'pgeocode', 0, 'church', 0.5))
        c.execute("UPDATE churches SET holy_site_id=? WHERE id=?", (c.lastrowid, ch_id))
        new_hs += 1
    conn.commit()
    print(f"  New holy_sites: {new_hs:,} in {time.time()-t0:.1f}s")

c.execute("SELECT COUNT(*) FROM churches WHERE country='CA' AND holy_site_id IS NOT NULL")
print(f"\nFinal CA linked: {c.fetchone()[0]:,}")

conn.close()
print(f"Done in {time.time()-t0:.1f}s")
