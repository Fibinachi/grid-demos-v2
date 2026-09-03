"""
Comprehensive US Census Geocoder — us_census_geocode.py
=========================================================
Two-phase geocoding for US records:

Phase 1 — TIGER Reverse Geocode (spatial join):
  Fixes city/county for records with coords but missing or placeholder city.
  Targets: city IS NULL, city = '', or city = 'Amchitka' (non-AK only).

Phase 2 — Forward Geocode (Census API):
  a) ZIP centroid lookup for records with ZIP but no coords
  b) Street-level Census API for records with full address but no coords

Usage:
    python scripts/geodata/us_census_geocode.py [--dry-run] [--chunk 5000]
"""

import sqlite3
import sys
import time
import os
import json
import urllib.request
import urllib.parse
import csv
from datetime import datetime, timezone
from concurrent.futures import ThreadPoolExecutor, as_completed

import geopandas as gpd
import pandas as pd
from shapely.geometry import Point

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
from scripts.grid_address import set_components

# ─── Config ────────────────────────────────────────────────────────────────
DB_PATH = r'E:\grid\churches.db'
PLACES_SHP = r'E:\grid\data\census_tiger\cb_2024_us_place_500k.shp'
COUNTIES_SHP = r'E:\grid\data\census_tiger\cb_2024_us_county_500k.shp'
ZCTA_PATH = r'E:\grid\data\Gaz_zcta_national.txt'
CHUNK_SIZE = 5000
DRY_RUN = '--dry-run' in sys.argv

# Census API
CENSUS_ADDRESS_URL = "https://geocoding.geo.census.gov/geocoder/locations/onelineaddress"
STREET_DELAY = 0.2       # 200ms between street-level calls
MAX_WORKERS = 5

# ─── Utility ───────────────────────────────────────────────────────────────
def progress_bar(current, total, label="", width=50):
    pct = current / total if total else 0
    filled = int(width * pct)
    bar = '█' * filled + '░' * (width - filled)
    return f'\r{label} [{bar}] {current:,}/{total:,} ({pct*100:.1f}%)'

def load_zcta():
    """Load ZIP → (lat, lng) from Census ZCTA gazetteer."""
    cache = {}
    if not os.path.exists(ZCTA_PATH):
        return cache
    with open(ZCTA_PATH, encoding="utf-8") as f:
        reader = csv.DictReader(f, delimiter="\t")
        reader.fieldnames = [n.strip() for n in reader.fieldnames]
        for row in reader:
            zip_code = row["GEOID"].strip().zfill(5)
            try:
                lat = float(row["INTPTLAT"].strip())
                lng = float(row["INTPTLONG"].strip())
                cache[zip_code] = (lat, lng)
            except (ValueError, KeyError):
                continue
    return cache


# ═══════════════════════════════════════════════════════════════════════════
# PHASE 1: TIGER Reverse Geocode (spatial join)
# ═══════════════════════════════════════════════════════════════════════════

def phase1_tiger_reverse_geocode():
    """Fix city/county for US records with coords but bad/missing city."""
    print('=' * 70)
    print('PHASE 1: TIGER/Line Spatial Join — Reverse Geocode')
    print('=' * 70)

    # Load boundaries
    print('Loading Census place boundaries...')
    t0 = time.time()
    places = gpd.read_file(PLACES_SHP)
    places = places[['STATEFP', 'PLACEFP', 'GEOID', 'NAME', 'geometry']].copy()
    places.columns = ['state_fips', 'place_fips', 'geoid', 'place_name', 'geometry']
    places['place_city'] = places['place_name'].str.replace(
        r'\s+(city|town|village|borough|CDP)$', '', regex=True
    )
    places = places.set_crs('EPSG:4269', allow_override=True)
    print(f'  {len(places):,} place polygons loaded in {time.time()-t0:.1f}s')

    print('Loading county boundaries...')
    counties = gpd.read_file(COUNTIES_SHP)
    counties = counties[['STATEFP', 'COUNTYFP', 'NAME', 'geometry']].copy()
    counties.columns = ['state_fips', 'county_fips', 'county_name', 'geometry']
    counties = counties.set_crs('EPSG:4269', allow_override=True)
    print(f'  {len(counties):,} county polygons loaded')

    # Connect to DB
    print(f'\nConnecting to DB ({"DRY RUN" if DRY_RUN else "LIVE"})...')
    conn = sqlite3.connect(DB_PATH)
    conn.execute('PRAGMA journal_mode=WAL')
    wconn = sqlite3.connect(DB_PATH)
    wconn.execute('PRAGMA journal_mode=WAL')
    wconn.isolation_level = None

    # Count targets: ALL US records with GPS — normalize city/county against TIGER
    total = conn.execute("""
        SELECT COUNT(*) FROM churches 
        WHERE latitude IS NOT NULL AND longitude IS NOT NULL
          AND country = 'US'
    """).fetchone()[0]
    print(f'US records to normalize: {total:,}')

    if total == 0:
        print('Nothing to do!')
        return

    churches_iter = pd.read_sql_query("""
        SELECT rowid AS lookup_id, id AS primary_id,
               latitude, longitude, name, source, city AS old_city
        FROM churches
        WHERE latitude IS NOT NULL AND longitude IS NOT NULL
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

        geometry = [Point(x, y) for x, y in zip(chunk['longitude'], chunk['latitude'])]
        points_gdf = gpd.GeoDataFrame(
            {'lookup_id': chunk['lookup_id'], 'primary_id': chunk['primary_id'],
             'latitude': chunk['latitude'], 'longitude': chunk['longitude']},
            geometry=geometry, crs='EPSG:4269'
        )

        # Place-level join
        place_joined = gpd.sjoin(
            points_gdf,
            places[['place_name', 'place_city', 'state_fips', 'place_fips', 'geometry']],
            predicate='within', how='left'
        )
        matched_to_place = place_joined[place_joined['index_right'].notna()].copy()
        n_place = len(matched_to_place)

        # County fallback
        unmatched = place_joined[place_joined['index_right'].isna()].copy()
        county_joined = gpd.sjoin(
            unmatched[['lookup_id', 'primary_id', 'latitude', 'longitude', 'geometry']],
            counties[['state_fips', 'county_fips', 'county_name', 'geometry']],
            predicate='within', how='left'
        )
        matched_to_county = county_joined[county_joined['index_right'].notna()].copy()
        truly_unmatched = county_joined[county_joined['index_right'].isna()]
        n_county = len(matched_to_county)
        n_none = len(truly_unmatched)

        # Write to DB
        if not DRY_RUN:
            wc = wconn.cursor()
            timestamp = datetime.now(timezone.utc).isoformat()

            city_updates = []
            county_updates = []
            enrich_updates = []

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

            # Write using normalized address schema
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

            # church_enrichment for records with non-NULL id
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
                ('census_tiger_amchitka_fix', 'us_census_geocode.py', timestamp, timestamp,
                 len(city_updates) + len(county_updates), 0,
                 'city, county, county_fips_5, address_components',
                 n, len(city_updates) + len(county_updates), 'completed')
            )

        updated_total += n_place + n_county
        no_match_total += n_none

        elapsed = time.time() - chunk_t0
        rate = n / elapsed if elapsed > 0 else 0
        done_pct = (updated_total + no_match_total) / total * 100
        eta = (total - (updated_total + no_match_total)) / rate if rate > 0 else 0

        print(f'  Chunk {chunk_num:>2d}: {n:>5d} recs ({done_pct:4.1f}%) — '
              f'{n_place:>5d} city, {n_county:>5d} county, {n_none:>5d} no match '
              f'[{elapsed:.2f}s @ {rate:.0f}/s]')

    print(f'\nPhase 1 complete!')
    print(f'  Total processed: {updated_total + no_match_total:,}')
    print(f'  Matched (city/county filled): {updated_total:,}')
    print(f'  No match: {no_match_total:,}')


# ═══════════════════════════════════════════════════════════════════════════
# PHASE 2: Forward Geocode (ZIP centroid + Census street-level)
# ═══════════════════════════════════════════════════════════════════════════

def phase2_forward_geocode():
    """Geocode US records with addresses but no lat/lng."""
    print('\n' + '=' * 70)
    print('PHASE 2: Forward Geocode — Address → Lat/Lng')
    print('=' * 70)

    conn = sqlite3.connect(DB_PATH)
    conn.execute('PRAGMA journal_mode=WAL')
    c = conn.cursor()

    # Find records needing forward geocode
    c.execute("""
        SELECT rowid, address, city, state, zip, zip5, name
        FROM churches
        WHERE country = 'US'
          AND (latitude IS NULL OR longitude IS NULL)
          AND (address IS NOT NULL AND address != '' AND address != 'None')
        ORDER BY rowid
    """)
    rows = c.fetchall()
    total = len(rows)
    print(f'US records with address but no coords: {total:,}')

    if total == 0:
        print('Nothing to do!')
        return

    # Load ZCTA for ZIP centroid lookups
    zcta = load_zcta()
    print(f'ZCTA gazetteer loaded: {len(zcta):,} ZIP codes')

    wconn = sqlite3.connect(DB_PATH)
    wconn.execute('PRAGMA journal_mode=WAL')

    zip_hits = 0
    street_hits = 0
    no_match = 0
    t0 = time.time()

    for i, (rowid, addr, city, state, zip_code, zip5, name) in enumerate(rows):
        lat = lng = None
        geocode_source = None

        # ── Step 2a: Try ZIP centroid ──
        zip_val = (zip_code or '').strip().split('-')[0].zfill(5)
        if not zip_val or zip_val == '00000':
            zip_val = (zip5 or '').strip().zfill(5)

        if zip_val and zip_val != '00000' and zip_val in zcta:
            lat, lng = zcta[zip_val]
            geocode_source = 'census_zcta'
            zip_hits += 1

        # ── Step 2b: Try Census street-level if we have enough info ──
        if not lat and addr and state:
            clean_addr = f"{addr}, {city or ''}, {state} {zip_val if zip_val else ''}".strip(', ')
            clean_addr = ' '.join(clean_addr.split())  # normalize whitespace

            try:
                params = urllib.parse.urlencode({
                    "address": clean_addr,
                    "benchmark": "2020",
                    "format": "json",
                })
                url = f"{CENSUS_ADDRESS_URL}?{params}"
                req = urllib.request.Request(url, headers={"User-Agent": "GRID/1.0 (academic research)"})
                with urllib.request.urlopen(req, timeout=10) as resp:
                    data = json.loads(resp.read().decode("utf-8"))

                matches = data.get("result", {}).get("addressMatches", [])
                if matches:
                    coords = matches[0].get("coordinates", {})
                    lat = coords.get("y")
                    lng = coords.get("x")
                    geocode_source = 'census_street'
                    street_hits += 1
            except Exception:
                pass

            time.sleep(STREET_DELAY)

        # ── Write result ──
        if lat and lng and not DRY_RUN:
            wc = wconn.cursor()
            wc.execute('BEGIN TRANSACTION')
            wc.execute(
                "UPDATE churches SET latitude = ?, longitude = ? WHERE rowid = ?",
                (round(lat, 7), round(lng, 7), rowid)
            )
            # Also write to church_addresses
            wc.execute("""
                INSERT INTO church_addresses (church_rowid, address_type, latitude, longitude, 
                    country, geocode_source, is_current)
                VALUES (?, 'physical', ?, ?, 'US', ?, 1)
                ON CONFLICT(church_rowid, address_type) DO UPDATE SET
                    latitude = excluded.latitude,
                    longitude = excluded.longitude,
                    geocode_source = excluded.geocode_source
            """, (rowid, round(lat, 7), round(lng, 7), geocode_source))
            wc.execute('COMMIT')
        elif not lat:
            no_match += 1

        if (i + 1) % 100 == 0 or i == total - 1:
            elapsed = time.time() - t0
            rate = (i + 1) / elapsed if elapsed > 0 else 0
            eta = (total - i - 1) / rate if rate > 0 else 0
            print(progress_bar(i + 1, total, '  Forward geocode',
                   width=40), end='', flush=True)
            if i == total - 1:
                print()  # newline at end

    if not DRY_RUN and (zip_hits + street_hits) > 0:
        timestamp = datetime.now(timezone.utc).isoformat()
        wc = wconn.cursor()
        wc.execute(
            """INSERT INTO provenance_log 
               (source, script_name, started_at, completed_at, 
                churches_updated, fields_populated, status, notes)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            ('census_forward_geocode', 'us_census_geocode.py', timestamp, timestamp,
             zip_hits + street_hits, 'latitude, longitude, geocode_source', 'completed',
             f'ZIP centroid: {zip_hits}, street-level: {street_hits}, no match: {no_match}')
        )

    elapsed = time.time() - t0
    print(f'\nPhase 2 complete! ({elapsed:.0f}s)')
    print(f'  ZIP centroid hits: {zip_hits:,}')
    print(f'  Street-level hits: {street_hits:,}')
    print(f'  No match: {no_match:,}')
    print(f'  Mode: {"DRY RUN (no DB writes)" if DRY_RUN else "LIVE — DB updated"}')

    conn.close()


# ═══════════════════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════════════════

if __name__ == '__main__':
    overall_t0 = time.time()
    print(f'US Census Geocoder — {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}')
    print(f'Mode: {"DRY RUN (no DB writes)" if DRY_RUN else "LIVE"}')
    print()

    phase1_tiger_reverse_geocode()
    phase2_forward_geocode()

    print(f'\n{"=" * 70}')
    print(f'All done! Total time: {time.time() - overall_t0:.0f}s')
    if DRY_RUN:
        print(f'Run without --dry-run to write to database.')
