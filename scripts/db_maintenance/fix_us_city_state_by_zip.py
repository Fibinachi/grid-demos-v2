"""
Fix ALL US city/state via ZIP5 lookup — the correct approach.
1. Extract ZIP5 from full ZIP column
2. Assign ZIP5 from nearest ZCTA centroid (GPS → ZIP)
3. Build ZIP5 → city, state lookup from clean records
4. Apply to fix all US records
"""
import sqlite3, sys, os, csv, numpy as np
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from gw_db import connect
from scipy.spatial import KDTree
from datetime import datetime

ZCTA_PATH = r'E:\grid\data\Gaz_zcta_national.txt'
db = connect()
cur = db.cursor()
now = datetime.now().isoformat()

print("=" * 60)
print("ZIP5-BASED US CITY/STATE NORMALIZATION")
print("=" * 60)

# ── Step 1: Extract ZIP5 from full ZIP ──
print("\n[1/4] Extracting ZIP5 from full ZIP codes...")
cur.execute("""
    UPDATE churches SET zip5 = substr(zip, 1, 5)
    WHERE country='US' AND (zip5 IS NULL OR zip5='')
      AND zip IS NOT NULL AND zip != '' AND length(zip) >= 5
""")
n1 = cur.rowcount
db.commit()
print(f"  {n1:,} zip5 extracted from full ZIP")

# ── Step 2: Assign ZIP5 via ZCTA nearest-neighbor ──
print("\n[2/4] Assigning ZIP5 via ZCTA gazetteer (GPS → ZIP)...")

# Load ZCTA centroids
zcta = {}
bad_zcta = 0
with open(ZCTA_PATH, encoding='utf-8') as f:
    reader = csv.DictReader(f, delimiter='\t')
    reader.fieldnames = [n.strip() for n in reader.fieldnames]
    for row in reader:
        try:
            lat = float(row['INTPTLAT'].strip())
            lon = float(row['INTPTLONG'].strip())
            if lat == 0 and lon == 0:
                bad_zcta += 1
                continue
            zcta[row['GEOID'].strip().zfill(5)] = (lat, lon)
        except (ValueError, KeyError):
            bad_zcta += 1
            continue
print(f"  {len(zcta):,} ZCTA centroids loaded ({bad_zcta} skipped)")

# Find records still without ZIP5
cur.execute("""
    SELECT id, latitude, longitude FROM churches
    WHERE country='US' AND (zip5 IS NULL OR zip5='')
      AND latitude IS NOT NULL AND latitude!=0
""")
needs_zip = cur.fetchall()
print(f"  {len(needs_zip):,} records need ZIP5 from GPS")

if needs_zip:
    zcta_zips = list(zcta.keys())
    zcta_coords = np.array([(zcta[z][0], zcta[z][1]) for z in zcta_zips], dtype=np.float64)
    tree = KDTree(zcta_coords)
    
    CHUNK = 1000
    fixed = 0
    for i in range(0, len(needs_zip), CHUNK):
        batch = needs_zip[i:i+CHUNK]
        for cid, lat, lon in batch:
            if lat is None or lon is None or lat == 0 or lon == 0:
                continue
            try:
                lat_f = float(lat)
                lon_f = float(lon)
                dist, idx = tree.query([lat_f, lon_f])
                nearest_zip = zcta_zips[int(idx)]
                cur.execute("UPDATE churches SET zip5=?, last_updated=? WHERE id=?", (nearest_zip, now, cid))
            except (ValueError, TypeError):
                pass
        db.commit()
        fixed += len(batch)
        if (i + CHUNK) % 10000 == 0:
            print(f"    {fixed:,} / {len(needs_zip):,}")
    
    print(f"  {fixed:,} assigned via ZCTA")

# ── Step 3: Build ZIP5 → city, state lookup ──
print("\n[3/4] Building ZIP5 → city, state lookup from clean records...")
from collections import Counter

cur.execute("""
    SELECT zip5, city, state, COUNT(*) as cnt
    FROM churches
    WHERE country='US' AND zip5 IS NOT NULL AND zip5!=''
      AND city IS NOT NULL AND city!=''
      AND city NOT GLOB '*[^ -~]*'
      AND state IS NOT NULL AND state!=''
    GROUP BY zip5, city, state
""")
zip_lookup = {}
for zip5, city, state, cnt in cur.fetchall():
    key = (zip5, city, state)
    if zip5 not in zip_lookup:
        zip_lookup[zip5] = Counter()
    zip_lookup[zip5][key] = cnt

# For each ZIP5, pick the most common (city, state)
zip_to_city_state = {}
for z, counter in zip_lookup.items():
    (_, city, state), _ = counter.most_common(1)[0]
    zip_to_city_state[z] = (city, state)

print(f"  {len(zip_to_city_state):,} ZIP5 → city,state mappings")

# ── Step 4: Apply city/state fixes ──
print("\n[4/4] Applying city/state fixes from ZIP5 lookup...")
fixed_city = 0
fixed_state = 0

# Fix records where city doesn't match ZIP5-derived city
cur.execute("""
    SELECT id, city, state, zip5 FROM churches
    WHERE country='US' AND zip5 IS NOT NULL AND zip5!=''
      AND (city IS NULL OR city='' OR city GLOB '*[^ -~]*'
           OR state IS NULL OR state='')
""")
to_fix = cur.fetchall()
print(f"  {len(to_fix):,} records to check")

for cid, old_city, old_state, zip5 in to_fix:
    if zip5 in zip_to_city_state:
        new_city, new_state = zip_to_city_state[zip5]
        if new_city and (old_city is None or old_city == '' or any(ord(c) > 127 for c in (old_city or ''))):
            cur.execute("UPDATE churches SET city=?, last_updated=? WHERE id=?", (new_city, now, cid))
            fixed_city += 1
        if new_state and (old_state is None or old_state == ''):
            cur.execute("UPDATE churches SET state=?, last_updated=? WHERE id=?", (new_state, now, cid))
            fixed_state += 1

db.commit()
print(f"  Cities fixed: {fixed_city:,}")
print(f"  States fixed: {fixed_state:,}")

# ── Final stats ──
cur.execute("SELECT COUNT(*) FROM churches WHERE country='US' AND (zip5 IS NULL OR zip5='')")
no_zip = cur.fetchone()[0]
cur.execute("SELECT COUNT(*) FROM churches WHERE country='US' AND city GLOB '*[^ -~]*'")
bad_city = cur.fetchone()[0]
cur.execute("SELECT COUNT(*) FROM churches WHERE country='US' AND (city IS NULL OR city='')")
null_city = cur.fetchone()[0]
cur.execute("SELECT COUNT(*) FROM churches WHERE country='US' AND (state IS NULL OR state='')")
null_state = cur.fetchone()[0]

print(f"\n{'='*60}")
print(f"FINAL STATE")
print(f"{'='*60}")
print(f"  No ZIP5:        {no_zip:>8,}")
print(f"  Non-ASCII city: {bad_city:>8,}")
print(f"  NULL city:      {null_city:>8,}")
print(f"  NULL state:     {null_state:>8,}")

db.close()
print("\nDone.")
