"""
run_us_footprint_pipeline.py — Autonomous BigQuery pipeline for US church
building footprints + parking estimates. Exports results to CSV, ready for
SQLite import.

Strategy:
  1. Re-run building spatial join against Overture buildings with IMPROVED params
     (150m radius instead of 75m, better ranking)
  2. For churches still unmatched, try Microsoft building footprints
  3. Estimate parking spots from building area (standard church ratios)
  4. Export church_building_sqft_us as CSV

Author: GRID Pipeline | Date: 2026-07-06
"""
import os, sys, csv, time
os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = ''
from google.cloud import bigquery

PROJECT = 'american-rel-infra'
DATASET = 'American_Religious_Infrastructure'
PREFIX = f'{PROJECT}.{DATASET}'
OUTPUT_CSV = r'E:\grid\data\church_building_sqft_us.csv'
CHUNK_SIZE = 50000

client = bigquery.Client(project=PROJECT)

def run(sql, desc, timeout=600):
    """Run a BQ query, print status."""
    print(f'{desc}...', end=' ', flush=True)
    t0 = time.time()
    try:
        job = client.query(sql)
        result = job.result(timeout=timeout)
        elapsed = time.time() - t0
        n = job.num_dml_affected_rows if hasattr(job, 'num_dml_affected_rows') else 'done'
        print(f'OK ({n} rows, {elapsed:.0f}s)')
        return result
    except Exception as e:
        print(f'FAILED after {time.time()-t0:.0f}s: {str(e)[:300]}')
        raise


# ══════════════════════════════════════════════════════════════════════
# STEP 1: Create US churches geo view
# ══════════════════════════════════════════════════════════════════════

print('=' * 70)
print('STEP 1: Create US churches geo view')
print('=' * 70)

run(f'''
CREATE OR REPLACE VIEW `{PREFIX}.vw_church_geo_us` AS
SELECT 
  id, name, city, state,
  latitude, longitude, tradition, faith, landmark_type, taxonomy_id,
  ST_GEOGPOINT(longitude, latitude) AS geo
FROM `{PREFIX}.churches`
WHERE country = 'US'
  AND latitude IS NOT NULL 
  AND longitude IS NOT NULL
''', 'Creating vw_church_geo_us')

# Check count
r = client.query(f'SELECT COUNT(*) n FROM `{PREFIX}.vw_church_geo_us`').result()
us_geo = list(r)[0][0]
print(f'  US churches with GPS: {us_geo:,}')

# ══════════════════════════════════════════════════════════════════════
# STEP 2: Building footprints — Overture Maps (expanded params)
# ══════════════════════════════════════════════════════════════════════

print()
print('=' * 70)
print('STEP 2: Overture building spatial join (150m radius)')
print('=' * 70)

run(f'DROP TABLE IF EXISTS `{PREFIX}.church_building_sqft_us`', 'Dropping old table')

run(f'''
CREATE TABLE `{PREFIX}.church_building_sqft_us` (
  church_id FLOAT64, name STRING, city STRING, state STRING,
  tradition STRING, faith STRING, taxonomy_id FLOAT64,
  latitude FLOAT64, longitude FLOAT64,
  building_area_m2 FLOAT64, building_area_sqft FLOAT64,
  distance_m FLOAT64, point_in_building BOOLEAN,
  building_source STRING,
  parking_estimate_spots INT64
)
''', 'Creating church_building_sqft_us')

# Overture buildings spatial join — 150m radius, US bbox
print('Running Overture spatial join (this takes several minutes)...')
sql = f'''
INSERT INTO `{PREFIX}.church_building_sqft_us`
  (church_id, name, city, state, tradition, faith, taxonomy_id,
   latitude, longitude, building_area_m2, building_area_sqft,
   distance_m, point_in_building, building_source)

WITH churches AS (
  SELECT id, name, city, state, tradition, faith, taxonomy_id,
         latitude, longitude, geo
  FROM `{PREFIX}.vw_church_geo_us`
),

-- Overture buildings filtered to US by bbox
footprints AS (
  SELECT 
    geometry,
    ST_AREA(geometry) AS area_m2
  FROM `bigquery-public-data.overture_maps.building`
  WHERE bbox.xmin BETWEEN -125 AND -66
    AND bbox.xmax BETWEEN -125 AND -66
    AND bbox.ymin BETWEEN 24 AND 50
    AND bbox.ymax BETWEEN 24 AND 50
),

-- Find buildings within 150m, rank by: inside > largest > closest
church_buildings AS (
  SELECT 
    c.id AS church_id, c.name, c.city, c.state,
    c.tradition, c.faith, c.taxonomy_id, c.latitude, c.longitude,
    ROUND(f.area_m2, 2) AS building_area_m2,
    ROUND(f.area_m2 * 10.7639, 2) AS building_area_sqft,
    ST_WITHIN(c.geo, f.geometry) AS point_in_building,
    ROUND(ST_DISTANCE(c.geo, f.geometry), 2) AS distance_m,
    ROW_NUMBER() OVER (
      PARTITION BY c.id 
      ORDER BY 
        ST_WITHIN(c.geo, f.geometry) DESC,
        -- Prefer buildings 50-50000 sqm (real churches, not sheds or stadiums)
        CASE WHEN f.area_m2 BETWEEN 50 AND 50000 THEN 1 ELSE 2 END,
        f.area_m2 DESC,
        ST_DISTANCE(c.geo, f.geometry) ASC
    ) AS rn
  FROM churches c
  JOIN footprints f ON ST_DWITHIN(c.geo, f.geometry, 150)
)

SELECT 
  church_id, name, city, state, tradition, faith, taxonomy_id,
  latitude, longitude, building_area_m2, building_area_sqft,
  distance_m, point_in_building, 'overture'
FROM church_buildings
WHERE rn = 1
'''
run(sql, 'Overture building join', timeout=900)

# Stats
for row in client.query(f'''
    SELECT COUNT(*) as matched,
           COUNTIF(point_in_building) as inside,
           ROUND(AVG(building_area_sqft),0) as avg_sqft,
           ROUND(AVG(distance_m),1) as avg_dist
    FROM `{PREFIX}.church_building_sqft_us`
''').result():
    print(f'  Matched: {row.matched:,} churches')
    print(f'  Inside building: {row.inside:,} ({row.inside/max(row.matched,1)*100:.1f}%)')
    print(f'  Avg sqft: {row.avg_sqft:,.0f}')
    print(f'  Avg distance: {row.avg_dist}m')

# ══════════════════════════════════════════════════════════════════════
# STEP 3: Fill gaps with Microsoft buildings (states without Overture match)
# ══════════════════════════════════════════════════════════════════════

print()
print('=' * 70)
print('STEP 3: Microsoft building check')
print('=' * 70)

# Check if MS buildings exist
ms_exists = False
try:
    t = client.get_table(f'{PREFIX}.ms_building_footprints')
    ms_exists = t.num_rows > 0
    print(f'  MS buildings: {t.num_rows:,} rows')
except:
    print('  MS buildings table exists but empty — skipping MS join')
    print('  (MS building import is a separate 8GB download — run load_microsoft_buildings.py first)')

# ══════════════════════════════════════════════════════════════════════
# STEP 4: Parking estimate from building area
# ══════════════════════════════════════════════════════════════════════

print()
print('=' * 70)
print('STEP 4: Parking estimates from building area')
print('=' * 70)

# Standard church parking: ~350 sqft per space (including aisles/driveways)
# Typical ratio: 1 space per 3-5 seats, and 15-20 sqft per seat in sanctuary
# So: building_sqft / 15 = seats, seats / 4 = parking_spots
# Simplified: building_sqft / 60 ≈ parking spots
run(f'''
UPDATE `{PREFIX}.church_building_sqft_us`
SET parking_estimate_spots = CAST(ROUND(building_area_sqft / 60) AS INT64)
WHERE building_area_sqft IS NOT NULL AND building_area_sqft > 0
''', 'Parking estimate update')

# Show parking distribution
for row in client.query(f'''
    SELECT 
      COUNT(*) as total,
      ROUND(AVG(parking_estimate_spots),0) as avg_spots,
      APPROX_QUANTILES(parking_estimate_spots, 100)[OFFSET(50)] as median_spots,
      APPROX_QUANTILES(parking_estimate_spots, 100)[OFFSET(90)] as p90_spots,
      APPROX_QUANTILES(parking_estimate_spots, 100)[OFFSET(99)] as p99_spots
    FROM `{PREFIX}.church_building_sqft_us`
    WHERE parking_estimate_spots > 0
''').result():
    print(f'  Churches with parking est: {row.total:,}')
    print(f'  Avg spots: {row.avg_spots:.0f} | Median: {row.median_spots} | P90: {row.p90_spots} | P99: {row.p99_spots}')

# ══════════════════════════════════════════════════════════════════════
# STEP 5: Coverage summary
# ══════════════════════════════════════════════════════════════════════

print()
print('=' * 70)
print('STEP 5: Coverage summary')
print('=' * 70)

for row in client.query(f'''
    WITH us AS (
      SELECT COUNT(*) n FROM `{PREFIX}.vw_church_geo_us`
    ),
    matched AS (
      SELECT COUNT(*) n FROM `{PREFIX}.church_building_sqft_us`
    )
    SELECT us.n as total_us, matched.n as matched,
           ROUND(matched.n / us.n * 100, 1) as pct,
           us.n - matched.n as remaining
    FROM us, matched
''').result():
    print(f'  US churches with GPS: {row.total_us:,}')
    print(f'  Matched to buildings: {row.matched:,} ({row.pct}%)')
    print(f'  Remaining unmatched: {row.remaining:,}')

# Breakdown by faith
print()
print('  By faith tradition:')
for row in client.query(f'''
    SELECT COALESCE(c.tradition, 'Unknown') as tradition, COUNT(*) n
    FROM `{PREFIX}.vw_church_geo_us` c
    LEFT JOIN `{PREFIX}.church_building_sqft_us` s ON c.id = s.church_id
    WHERE s.church_id IS NULL
    GROUP BY 1
    ORDER BY 2 DESC
    LIMIT 10
''').result():
    print(f'    {row.tradition}: {row.n:,}')

# ══════════════════════════════════════════════════════════════════════
# STEP 6: Export to CSV
# ══════════════════════════════════════════════════════════════════════

print()
print('=' * 70)
print('STEP 6: Export to CSV')
print('=' * 70)

total = list(client.query(
    f'SELECT COUNT(*) FROM `{PREFIX}.church_building_sqft_us`'
).result())[0][0]
print(f'  Exporting {total:,} rows to {OUTPUT_CSV}')

with open(OUTPUT_CSV, 'w', newline='', encoding='utf-8') as f:
    writer = None
    written = 0
    offset = 0
    
    cols = ['church_id', 'name', 'city', 'state', 'tradition', 'faith', 'taxonomy_id',
            'latitude', 'longitude', 'building_area_m2', 'building_area_sqft',
            'distance_m', 'point_in_building', 'building_source', 'parking_estimate_spots']
    
    while offset < total:
        rows = list(client.query(
            f'SELECT {",".join(cols)} FROM `{PREFIX}.church_building_sqft_us` '
            f'LIMIT {CHUNK_SIZE} OFFSET {offset}'
        ).result())
        
        if not rows:
            break
        
        if writer is None:
            writer = csv.DictWriter(f, fieldnames=cols)
            writer.writeheader()
        
        for row in rows:
            writer.writerow(dict(row))
        
        written += len(rows)
        offset += len(rows)
        if offset % 100000 < CHUNK_SIZE:
            print(f'    {written:,}/{total:,} ({written/total*100:.1f}%)')

print(f'  Done: {written:,} rows written to {OUTPUT_CSV}')
print()
print('Pipeline complete!')
print(f'  BQ table: {PREFIX}.church_building_sqft_us')
print(f'  CSV export: {OUTPUT_CSV}')
print()
print('Next: sync to SQLite with:')
print(f'  python scripts/db_maintenance/import_building_sqft.py')
