"""
Spatial diocese assignment: point-in-polygon using OSM diocese boundaries.
Loads WKB geometries from world_borders.db, tests each US Catholic entry's
lat/lon against all polygons. Logs provenance.
"""
import sqlite3, time
from datetime import datetime, timezone
from shapely import wkb
from shapely.geometry import Point

CHURCHES_DB = 'churches.db'
GEO_DB = 'data/natural_earth/world_borders.db'
NOW = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')

# Load diocese polygons
gdb = sqlite3.connect(GEO_DB)
gc = gdb.cursor()
gc.execute("SELECT diocese, name, country, geometry_wkb FROM diocese_boundaries WHERE geometry_wkb IS NOT NULL")
polygons = []
for diocese, name, country, wkb_blob in gc.fetchall():
    try:
        geom = wkb.loads(wkb_blob)
        polygons.append({
            'diocese': diocese or name,
            'name': name,
            'country': country,
            'geom': geom,
        })
    except Exception as e:
        print(f"  WARN: Failed to load {diocese or name}: {e}")
gdb.close()

print(f"Loaded {len(polygons)} diocese polygons")

# Count by country
from collections import Counter
country_counts = Counter(p['country'] for p in polygons if p['country'])
print(f"Countries: {dict(country_counts)}")
print(f"Diocese names: {[p['diocese'][:40] for p in polygons[:10]]}...")

# Open churches DB
db = sqlite3.connect(CHURCHES_DB)
db.execute("PRAGMA journal_mode=WAL")
c = db.cursor()

# US Catholic entries with coords but no diocese
CATH = "(LOWER(COALESCE(c.tradition,'')) LIKE '%cath%' OR LOWER(COALESCE(c.faith,'')) LIKE '%cath%' OR LOWER(COALESCE(c.denomination,'')) LIKE '%cath%')"
c.execute(f"""
SELECT c.rowid, c.latitude, c.longitude, c.name
FROM churches c
JOIN church_enrichment ce ON c.rowid = ce.church_id
WHERE c.country='US' AND {CATH}
  AND c.latitude IS NOT NULL AND c.longitude IS NOT NULL
  AND (ce.diocese IS NULL OR ce.diocese = '')
""")
entries = c.fetchall()
print(f"\nUS Catholic entries needing diocese: {len(entries):,}")

# For efficiency, pre-filter polygons by country
us_polygons = [p for p in polygons if not p['country'] or p['country'].upper() in ('US', 'USA', 'UNITED STATES', '')]
print(f"US-relevant polygons: {len(us_polygons)}")

if not us_polygons:
    print("No US diocese polygons available! Using all 69 globally.")
    us_polygons = polygons

# Assign
assigned = 0
no_match = 0
start = time.time()
batch = []
commit_every = 500

for i, (rowid, lat, lon, name) in enumerate(entries):
    if lat is None or lon is None:
        no_match += 1
        continue
    
    point = Point(lon, lat)
    found = None
    for p in us_polygons:
        if p['geom'].contains(point) or p['geom'].touches(point):
            found = p['diocese']
            break
    
    if found:
        batch.append((found, rowid))
        assigned += 1
    else:
        no_match += 1
    
    if len(batch) >= commit_every:
        for diocese, rid in batch:
            c.execute("UPDATE church_enrichment SET diocese=? WHERE church_id=?", (diocese, rid))
        db.commit()
        batch = []
    
    if (i + 1) % 5000 == 0:
        elapsed = time.time() - start
        rate = (i + 1) / elapsed
        eta = (len(entries) - i - 1) / rate
        print(f'  {i+1:,}/{len(entries):,} ({rate:.0f}/s) assigned={assigned} ETA={eta/60:.0f}min', flush=True)

# Final flush
if batch:
    for diocese, rid in batch:
        c.execute("UPDATE church_enrichment SET diocese=? WHERE church_id=?", (diocese, rid))
    db.commit()

elapsed = time.time() - start
print(f'\nDone in {elapsed:.0f}s: {assigned:,} assigned, {no_match:,} no match')

# Verify
c.execute(f"SELECT COUNT(*) FROM churches c JOIN church_enrichment ce ON c.rowid=ce.church_id WHERE c.country='US' AND {CATH} AND ce.diocese IS NOT NULL AND ce.diocese!=''")
final = c.fetchone()[0]
c.execute(f"SELECT COUNT(*) FROM churches c JOIN church_enrichment ce ON c.rowid=ce.church_id WHERE c.country='US' AND {CATH}")
total = c.fetchone()[0]
print(f"US Catholic with diocese: {final:,}/{total:,} ({final/total*100:.0f}%)")

# Top dioceses
c.execute(f"SELECT ce.diocese,COUNT(*) FROM churches c JOIN church_enrichment ce ON c.rowid=ce.church_id WHERE c.country='US' AND {CATH} AND ce.diocese IS NOT NULL GROUP BY ce.diocese ORDER BY COUNT(*) DESC LIMIT 10")
print("\nTop dioceses:")
for r in c.fetchall(): print(f'  {r[0]:40s}: {r[1]:>6d}')

# Provenance
c.execute("INSERT INTO provenance_log (source,script_name,started_at,completed_at,churches_updated,fields_populated,status,notes) VALUES (?,?,?,?,?,?,?,?)",
    ('osm_diocese_spatial','assign_diocese_spatial.py',NOW,datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'),
     assigned,'diocese','completed',
     f'Spatial point-in-polygon diocese assignment using {len(us_polygons)} OSM polygons. {assigned:,} assigned.'))
db.commit()
db.close()
print("Provenance logged. Done!")
