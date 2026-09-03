"""
Batch reverse geocode US churches using Census TIGER/Line place boundaries.
Point-in-polygon spatial join — fills city, county, state, FIPS for records
that have lat/lon but no city.

Writes city/county data to:
  - church_addresses + address_components (normalized two-layer schema)
  - churches.city / churches.county / churches.county_fips_5 (legacy backward compat)
  - church_enrichment (enrichment layer, for records with non-NULL id)

Usage:
    python scripts/geodata/batch_census_reverse_geocode.py [--dry-run] [--chunk 5000]

Dependencies: geopandas, shapely, fiona (all in .venv)
Source: Census Bureau TIGER/Line GENZ2024 cartographic boundary files
"""

import sqlite3
import sys
import time
import os
import json
from datetime import datetime, timezone

import geopandas as gpd
import pandas as pd
from shapely.geometry import Point

# Import address helper for normalized schema writes
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
from scripts.grid_address import set_components

# ─── Config ────────────────────────────────────────────────────────────────
DB_PATH = r'E:\grid\churches.db'
PLACES_SHP = r'E:\grid\data\census_tiger\cb_2024_us_place_500k.shp'
COUNTIES_SHP = r'E:\grid\data\census_tiger\cb_2024_us_county_500k.shp'
CHUNK_SIZE = 5000
DRY_RUN = '--dry-run' in sys.argv

# ─── Step 1: Load Census boundaries ────────────────────────────────────────
print('Loading Census place boundaries...')
t0 = time.time()

places = gpd.read_file(PLACES_SHP)
# Keep only what we need — simplify columns
places = places[['STATEFP', 'PLACEFP', 'GEOID', 'NAME', 'geometry']].copy()
places.columns = ['state_fips', 'place_fips', 'geoid', 'place_name', 'geometry']
# "Washington city" → "Washington"
places['place_city'] = places['place_name'].str.replace(r'\s+(city|town|village|borough|CDP)$', '', regex=True)
# Also keep full legal name for logging
places = places.set_crs('EPSG:4269', allow_override=True)  # NAD83 — same as Census data

print(f'  {len(places):,} place polygons loaded in {time.time()-t0:.1f}s')

# Also load counties (for county-level fallback — covers all US territory)
print('Loading county boundaries...')
counties = gpd.read_file(COUNTIES_SHP)
counties = counties[['STATEFP', 'COUNTYFP', 'NAME', 'geometry']].copy()
counties.columns = ['state_fips', 'county_fips', 'county_name', 'geometry']
counties = counties.set_crs('EPSG:4269', allow_override=True)
print(f'  {len(counties):,} county polygons loaded')

# ─── Step 2: Connect to DB — separate read/write connections ──────────────
print(f'\nConnecting to DB ({"DRY RUN" if DRY_RUN else "LIVE"})...')
conn = sqlite3.connect(DB_PATH)       # read connection
conn.execute('PRAGMA journal_mode=WAL')
wconn = sqlite3.connect(DB_PATH)      # write connection (not WAL — explicit txns only)
wconn.execute('PRAGMA journal_mode=WAL')
wconn.isolation_level = None          # disable auto-txn — we manage BEGIN/COMMIT manually

# Get total count first
total = conn.execute("""
    SELECT COUNT(*) FROM churches 
    WHERE (city IS NULL OR city = '') 
      AND latitude IS NOT NULL AND longitude IS NOT NULL
      AND country = 'US'
""").fetchone()[0]
print(f'US records needing reverse geocode: {total:,}')

if total == 0:
    print('Nothing to do!')
    sys.exit(0)

# Stream in chunks to manage memory
# Use rowid (always assigned by SQLite) since 2.8M records have NULL id
churches_iter = pd.read_sql_query("""
    SELECT rowid AS lookup_id, id AS primary_id,
           latitude, longitude, name, source, denomination
    FROM churches
    WHERE (city IS NULL OR city = '') 
      AND latitude IS NOT NULL AND longitude IS NOT NULL
      AND country = 'US'
    ORDER BY rowid
""", conn, chunksize=CHUNK_SIZE)

updated_total = 0
no_match_total = 0
chunk_num = 0

for chunk in churches_iter:
    chunk_num += 1
    chunk_t0 = time.time()
    n = len(chunk)
    
    # Convert chunk to GeoDataFrame (EPSG:4269 NAD83 to match Census boundaries)
    geometry = [Point(x, y) for x, y in zip(chunk['longitude'], chunk['latitude'])]
    points_gdf = gpd.GeoDataFrame(
        {'lookup_id': chunk['lookup_id'], 'primary_id': chunk['primary_id'],
         'latitude': chunk['latitude'], 'longitude': chunk['longitude']},
        geometry=geometry, crs='EPSG:4269'
    )
    
    # ── 3a: Place-level join (city/town boundaries) ──────────────
    place_joined = gpd.sjoin(
        points_gdf,
        places[['place_name', 'place_city', 'state_fips', 'place_fips', 'geometry']],
        predicate='within',
        how='left'
    )
    
    matched_to_place = place_joined[place_joined['index_right'].notna()].copy()
    n_place = len(matched_to_place)
    
    if chunk_num == 1:
        print('  Columns in place_joined:', list(place_joined.columns))
        print('  Sample lookup_ids:', matched_to_place['lookup_id'].head(3).tolist() if n_place > 0 else '(none)')
    
    # Build unmatched set for county fallback (covers all US territory)
    unmatched = place_joined[place_joined['index_right'].isna()].copy()
    
    county_joined = gpd.sjoin(
        unmatched[['lookup_id', 'primary_id', 'latitude', 'longitude', 'geometry']],
        counties[['state_fips', 'county_fips', 'county_name', 'geometry']],
        predicate='within',
        how='left'
    )
    matched_to_county = county_joined[county_joined['index_right'].notna()].copy()
    truly_unmatched = county_joined[county_joined['index_right'].isna()]
    
    n_county = len(matched_to_county)
    n_none = len(truly_unmatched)
    
    if chunk_num == 1:
        print('  Columns in county_joined:', list(county_joined.columns))
        print('  Sample county lookup_ids:', county_joined['lookup_id'].head(5).tolist())
    
    # ── 3c: Write to DB ───────────────────────────────────────────
    if not DRY_RUN:
        wc = wconn.cursor()
        timestamp = datetime.now(timezone.utc).isoformat()
        
        # Build updates
        city_updates = []
        county_updates = []
        enrich_updates = []  # church_enrichment — only for non-NULL primary_id
        
        for _, row in matched_to_place.iterrows():
            rid = row['lookup_id']
            if rid is None or (hasattr(rid, 'isna') and rid.isna()):
                continue
            city = row['place_city'] if pd.notna(row['place_city']) else row.get('place_name', None)
            if pd.notna(city):
                city_updates.append((int(rid), str(city)))
        
        for _, row in matched_to_county.iterrows():
            rid = row['lookup_id']
            if rid is None or (hasattr(rid, 'isna') and rid.isna()):
                continue
            pid = row.get('primary_id') if not pd.isna(row.get('primary_id', None)) else None
            county_name = str(row['county_name']) if pd.notna(row['county_name']) else None
            sfips = str(int(row['state_fips'])).zfill(2) if pd.notna(row['state_fips']) else None
            cfips = sfips + str(int(row['county_fips'])).zfill(3) if pd.notna(row['county_fips']) and sfips else None
            county_updates.append((int(rid), county_name, cfips))
            if pid is not None:
                enrich_updates.append((int(pid), cfips, county_name))
        
        # ── Write to normalized address schema + legacy columns ──
        wc.execute('BEGIN TRANSACTION')
        for rid, city in city_updates:
            set_components(wconn, rid, {'city': city}, update_legacy=True)
        for rid, cname, cfips in county_updates:
            comps = {}
            if cname:
                comps['county'] = cname
            if cfips:
                comps['county_fips_5'] = cfips
            if comps:
                set_components(wconn, rid, comps, update_legacy=True)
        wc.execute('COMMIT')
        
        # ── Write to church_enrichment (only for records with non-NULL primary id) ──
        if enrich_updates:
            wc.execute('BEGIN TRANSACTION')
            for church_id, cfips, cname in enrich_updates:
                if cfips:
                    wc.execute(
                        """INSERT INTO church_enrichment 
                           (church_id, county_fips_5, county_name)
                           VALUES (?, ?, ?)
                           ON CONFLICT(church_id) DO UPDATE SET
                               county_fips_5 = excluded.county_fips_5,
                               county_name = excluded.county_name""",
                        (church_id, cfips, cname)
                    )
            wc.execute('COMMIT')
        
        # Log provenance
        wc.execute(
            """INSERT INTO provenance_log 
               (source, script_name, started_at, completed_at, 
                churches_updated, churches_inserted, fields_populated,
                records_attempted, records_matched, status)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            ('census_tiger', 'batch_census_reverse_geocode.py', timestamp, timestamp,
             len(city_updates) + len(county_updates), 0,
             'city, county, county_fips_5, address_components',
             n, len(city_updates) + len(county_updates), 'completed')
        )
    
    updated_total += n_place + n_county
    no_match_total += n_none
    
    elapsed = time.time() - chunk_t0
    rate = n / elapsed
    done_pct = (updated_total + no_match_total) / total * 100
    eta = (total - (updated_total + no_match_total)) / rate if rate > 0 else 0
    
    print(f'  Chunk {chunk_num:>2d}: {n:>5d} recs ({done_pct:4.1f}%) — '
          f'{n_place:>5d} city, {n_county:>5d} county, {n_none:>5d} no match '
          f'[{elapsed:.2f}s @ {rate:.0f}/s]')

# ─── Step 4: Summary ─────────────────────────────────────────────────────
total_matched = updated_total  # cumulative city+county matches
print(f'\n══════════════════════════════════════════')
print(f'Batch complete!')
print(f'  Total processed: {total_matched + no_match_total:,}')
print(f'  Matched to named place (city filled): {total_matched:,}')
print(f'  No place or county match: {no_match_total:,}')
print(f'  Time: {time.time()-t0:.0f}s')
print(f'  Mode: {"DRY RUN (no DB writes)" if DRY_RUN else "LIVE — DB updated"}')

if DRY_RUN:
    print(f'\nRun without --dry-run to write to database.')
else:
    # Final counts
    c = conn.cursor()
    us_filled = c.execute("""
        SELECT COUNT(*) FROM churches 
        WHERE city IS NOT NULL AND city != ''
          AND country = 'US' AND source LIKE '%holy_sites%'
    """).fetchone()[0]
    county_enriched = c.execute("""
        SELECT COUNT(*) FROM church_enrichment 
        WHERE county_fips_5 IS NOT NULL
    """).fetchone()[0]
    print(f'\nPost-run stats:')
    print(f'  holy_sites US with city now: {us_filled:,}')
    print(f'  church_enrichment with county_fips_5: {county_enriched:,}')

conn.close()
