"""
Fix country codes using spatial point-in-polygon against world borders.
Processes ALL entries with coordinates. Auto-fixes any mismatch where
the point falls unambiguously within exactly one country polygon.
Uses bounding-box pre-filter for performance (~4 min for 2.2M entries).

Root cause of bad country codes:
- contacts+holy_sites_enrichment: 6,884/6,885 entries have wrong country
  (missionary field country used instead of physical location)
- holy_sites_import: ~110/5,000 entries near borders misassigned
- Overall wrong-rate: ~3.1% (~69K entries)
"""
import sqlite3, time, csv, sys
from datetime import datetime, timezone
from shapely import wkb
from shapely.geometry import Point, box

CHURCHES_DB = 'churches.db'
GEO_DB = 'data/natural_earth/world_borders.db'
NOW = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
BATCH_SIZE = 5000
PROGRESS_EVERY = 100000

# ── Load country polygons with bounding boxes ──
print("Loading country polygons...", end=' ', flush=True)
gdb = sqlite3.connect(GEO_DB)
gc = gdb.cursor()
gc.execute("SELECT iso_a2, name, geometry_wkb FROM world_borders WHERE geometry_wkb IS NOT NULL")
countries = []
iso_lookup = {}
for iso, name, wkb_blob in gc.fetchall():
    try:
        geom = wkb.loads(wkb_blob)
        bbox = geom.bounds  # (minx, miny, maxx, maxy)
        countries.append({
            'iso': iso, 'name': name, 'geom': geom,
            'bbox': bbox,
            'bbox_geom': box(*bbox)
        })
        iso_lookup[iso] = name
    except:
        pass
gdb.close()
print(f"{len(countries)} countries")

# ── Open churches (read connection for cursor iteration) ──
db = sqlite3.connect(CHURCHES_DB)
db.execute("PRAGMA journal_mode=WAL")
db.execute("PRAGMA busy_timeout=30000")
c = db.cursor()

# Separate write connection (commits won't invalidate read cursor)
wdb = sqlite3.connect(CHURCHES_DB)
wdb.execute("PRAGMA journal_mode=WAL")
wdb.execute("PRAGMA busy_timeout=30000")
wc = wdb.cursor()

# Count total to process
c.execute("SELECT COUNT(*) FROM churches WHERE latitude IS NOT NULL AND longitude IS NOT NULL")
total = c.fetchone()[0]
print(f"Entries with coordinates: {total:,}")

# ── Process all entries ──
c.execute("""SELECT rowid, latitude, longitude, country, name, source 
FROM churches WHERE latitude IS NOT NULL AND longitude IS NOT NULL""")

fixed = 0
ocean = 0
already_correct = 0
mismatches = []  # for CSV export (sample only)
batch = []
start = time.time()
last_progress = start

# Build iso→country lookup for O(1) claimed-country check
iso_to_country = {}
for ctry in countries:
    iso_to_country[ctry['iso']] = ctry

for i, (rowid, lat, lon, current_country, name, source) in enumerate(c):
    if not lat or not lon:
        continue
    
    point = Point(lon, lat)
    actual_iso = None
    actual_name = None
    
    # Fast path: check claimed country first (97% correct → 1 check)
    ctry = iso_to_country.get(current_country)
    if ctry:
        minx, miny, maxx, maxy = ctry['bbox']
        if minx <= lon <= maxx and miny <= lat <= maxy:
            if ctry['geom'].contains(point):
                already_correct += 1
                continue  # Confirmed correct — done!
    
    # Slow path: search all countries (only ~3% of entries reach here)
    for ctry in countries:
        minx, miny, maxx, maxy = ctry['bbox']
        if lon < minx or lon > maxx or lat < miny or lat > maxy:
            continue
        if ctry['geom'].contains(point):
            actual_iso = ctry['iso']
            actual_name = ctry['name']
            break
    
    if actual_iso is None:
        ocean += 1
        continue
    
    if current_country == actual_iso:
        # Passed bbox but failed exact containment for claimed country,
        # but another country also claims it — border case, skip
        already_correct += 1
        continue
    
    # Mismatch — auto-fix
    batch.append((actual_iso, rowid))
    fixed += 1
    
    # Save first 5000 mismatches for review CSV
    if len(mismatches) < 5000:
        mismatches.append((rowid, name, current_country, actual_iso, actual_name, lat, lon, source))
    
    # Batch commit (on write connection, won't invalidate read cursor)
    if len(batch) >= BATCH_SIZE:
        for iso, rid in batch:
            wc.execute("UPDATE churches SET country=? WHERE rowid=?", (iso, rid))
        wdb.commit()
        batch = []
    
    # Progress
    if (i + 1) % PROGRESS_EVERY == 0:
        elapsed = time.time() - start
        rate = (i + 1) / elapsed
        eta = (total - i - 1) / rate
        pct = (i + 1) / total * 100
        print(f'  {i+1:,}/{total:,} ({pct:.1f}%) fixed={fixed:,} ocean={ocean:,} '
              f'rate={rate:,.0f}/s ETA={eta/60:.0f}m', flush=True)

# ── Final batch commit ──
if batch:
    for iso, rid in batch:
        wc.execute("UPDATE churches SET country=? WHERE rowid=?", (iso, rid))
    wdb.commit()

elapsed = time.time() - start

# ── Final stats ──
print(f"\n{'='*60}")
print(f"Completed in {elapsed/60:.1f} minutes")
print(f"  Processed:    {total:,}")
print(f"  Already OK:   {already_correct:,}")
print(f"  Auto-fixed:   {fixed:,} ({fixed/total*100:.2f}%)")
print(f"  In ocean:     {ocean:,} ({ocean/total*100:.2f}%)")
print(f"  Rate:         {total/elapsed:,.0f} entries/sec")

c.execute("SELECT COUNT(*) FROM churches WHERE country='ZZ' OR country IS NULL OR country=''")
remaining_zz = c.fetchone()[0]
print(f"  Still unknown:{remaining_zz:,}")

c.execute("SELECT country, COUNT(*) FROM churches WHERE country!='ZZ' AND country IS NOT NULL GROUP BY country ORDER BY COUNT(*) DESC LIMIT 10")
print("\nTop countries after fix:")
for r in c.fetchall():
    print(f'  {r[0]:4s}: {r[1]:>12,}')

# ── Save mismatch sample for review ──
if mismatches:
    with open('data/country_fixes.csv', 'w', newline='', encoding='utf-8') as f:
        w = csv.writer(f)
        w.writerow(['rowid', 'name', 'old_country', 'new_country', 'country_name', 'lat', 'lon', 'source'])
        for row in mismatches:
            w.writerow(row)
    print(f"\nSaved {len(mismatches):,} fix samples to data/country_fixes.csv")

# ── Provenance ──
wc.execute("""INSERT INTO provenance_log 
(source, script_name, started_at, completed_at, churches_updated, fields_populated, status, notes) 
VALUES (?,?,?,?,?,?,?,?)""",
    ('spatial_country_fix', 'fix_country_by_geometry.py', NOW,
     datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'),
     fixed, 'country', 'completed',
     f'Spatial point-in-polygon country fix. {fixed:,} corrected, {ocean:,} in ocean/no-border, '
     f'{already_correct:,} already correct. Bbox-optimized: {total/elapsed:,.0f}/sec.'))
wdb.commit()
db.close()
wdb.close()
print("Provenance logged. Done.")
