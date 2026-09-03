"""
Quick TIGER reverse geocode to fix Amchitka placeholder cities.
Phase 1 only from us_census_geocode.py — runs without Phase 2.

Usage:
    python scripts/geodata/fix_amchitka_cities.py [--dry-run]
"""

import sqlite3
import sys
import time
import os
from datetime import datetime, timezone

import geopandas as gpd
import pandas as pd
from shapely.geometry import Point

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

DB_PATH = r'E:\grid\churches.db'
PLACES_SHP = r'E:\grid\data\census_tiger\cb_2024_us_place_500k.shp'
COUNTIES_SHP = r'E:\grid\data\census_tiger\cb_2024_us_county_500k.shp'
CHUNK_SIZE = 5000
DRY_RUN = '--dry-run' in sys.argv

def main():
    print(f'Fix Amchitka Cities — {"DRY RUN" if DRY_RUN else "LIVE"} — {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}')
    print('=' * 60)

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
    conn = sqlite3.connect(DB_PATH)
    conn.execute('PRAGMA journal_mode=WAL')
    wconn = sqlite3.connect(DB_PATH, timeout=30)
    wconn.execute('PRAGMA journal_mode=WAL')
    wconn.execute('PRAGMA busy_timeout=30000')
    wconn.isolation_level = None

    # Count targets
    total = conn.execute("""
        SELECT COUNT(*) FROM churches 
        WHERE latitude IS NOT NULL AND longitude IS NOT NULL
          AND country = 'US'
          AND (
              (city IS NULL OR city = '')
              OR (city = 'Amchitka' AND state != 'AK')
          )
    """).fetchone()[0]
    print(f'\nUS records needing reverse geocode: {total:,}')

    if total == 0:
        print('Nothing to do!')
        conn.close()
        return

    # Also count how many are Amchitka vs NULL/empty
    null_count = conn.execute("""
        SELECT COUNT(*) FROM churches 
        WHERE latitude IS NOT NULL AND longitude IS NOT NULL
          AND country = 'US' AND (city IS NULL OR city = '')
    """).fetchone()[0]
    amchitka_count = conn.execute("""
        SELECT COUNT(*) FROM churches 
        WHERE latitude IS NOT NULL AND longitude IS NOT NULL
          AND country = 'US' AND city = 'Amchitka' AND state != 'AK'
    """).fetchone()[0]
    print(f'  NULL/empty city: {null_count:,}')
    print(f'  Amchitka placeholder (non-AK): {amchitka_count:,}')

    # Load all rowids and coords into memory (161K records ≈ few MB)
    rows = conn.execute("""
        SELECT rowid AS lookup_id, id AS primary_id,
               latitude, longitude
        FROM churches
        WHERE latitude IS NOT NULL AND longitude IS NOT NULL
          AND country = 'US'
          AND (
              (city IS NULL OR city = '')
              OR (city = 'Amchitka' AND state != 'AK')
          )
        ORDER BY rowid
    """).fetchall()
    
    # Close read connection now to avoid lock contention
    conn.close()

    updated_total = 0
    no_match_total = 0
    place_hits = 0
    county_hits = 0
    chunk_num = 0
    
    # Process in chunks
    for i in range(0, len(rows), CHUNK_SIZE):
        chunk_rows = rows[i:i + CHUNK_SIZE]
        chunk = pd.DataFrame(chunk_rows, columns=['lookup_id', 'primary_id', 'latitude', 'longitude'])
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

        # County fallback for unmatched
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

            # Direct SQL updates (avoid set_components dependency on geocode_source)
            wc.execute('BEGIN TRANSACTION')
            
            # Update city on churches table
            for rid, city in city_updates:
                wc.execute("UPDATE churches SET city = ? WHERE rowid = ?", (city, rid))
                # Also update address_components if address_id exists
                addr_row = wc.execute(
                    "SELECT address_id FROM church_addresses WHERE church_rowid = ? AND address_type = 'primary'",
                    (rid,)
                ).fetchone()
                if addr_row:
                    addr_id = addr_row[0]
                    # Upsert city component
                    existing = wc.execute(
                        "SELECT component_id FROM address_components WHERE address_id = ? AND component_type = 'city'",
                        (addr_id,)
                    ).fetchone()
                    if existing:
                        wc.execute(
                            "UPDATE address_components SET component_value = ? WHERE component_id = ?",
                            (city, existing[0])
                        )
                    else:
                        wc.execute(
                            "INSERT INTO address_components (address_id, component_type, component_value, sort_order) VALUES (?, 'city', ?, 0)",
                            (addr_id, city)
                        )
            
            # Update county on churches table
            for rid, cname, cfips in county_updates:
                if cname:
                    wc.execute("UPDATE churches SET county = ? WHERE rowid = ?", (cname, rid))
                    # Also update address_components
                    addr_row = wc.execute(
                        "SELECT address_id FROM church_addresses WHERE church_rowid = ? AND address_type = 'primary'",
                        (rid,)
                    ).fetchone()
                    if addr_row:
                        addr_id = addr_row[0]
                        existing = wc.execute(
                            "SELECT component_id FROM address_components WHERE address_id = ? AND component_type = 'county'",
                            (addr_id,)
                        ).fetchone()
                        if existing:
                            wc.execute(
                                "UPDATE address_components SET component_value = ? WHERE component_id = ?",
                                (cname, existing[0])
                            )
                        else:
                            wc.execute(
                                "INSERT INTO address_components (address_id, component_type, component_value, sort_order) VALUES (?, 'county', ?, 1)",
                                (addr_id, cname)
                            )
                if cfips:
                    wc.execute("UPDATE churches SET county_fips_5 = ? WHERE rowid = ?", (cfips, rid))
                    # Also update address_components for county_fips_5
                    addr_row = wc.execute(
                        "SELECT address_id FROM church_addresses WHERE church_rowid = ? AND address_type = 'primary'",
                        (rid,)
                    ).fetchone()
                    if addr_row:
                        addr_id = addr_row[0]
                        existing = wc.execute(
                            "SELECT component_id FROM address_components WHERE address_id = ? AND component_type = 'county_fips_5'",
                            (addr_id,)
                        ).fetchone()
                        if existing:
                            wc.execute(
                                "UPDATE address_components SET component_value = ? WHERE component_id = ?",
                                (cfips, existing[0])
                            )
                        else:
                            wc.execute(
                                "INSERT INTO address_components (address_id, component_type, component_value, sort_order) VALUES (?, 'county_fips_5', ?, 2)",
                                (addr_id, cfips)
                            )
            
            wc.execute('COMMIT')

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

        place_hits += n_place
        county_hits += n_county
        updated_total += n_place + n_county
        no_match_total += n_none

        elapsed = time.time() - chunk_t0
        rate = n / elapsed if elapsed > 0 else 0
        done_pct = (updated_total + no_match_total) / total * 100

        print(f'  Chunk {chunk_num:>2d}: {n:>5d} recs ({done_pct:4.1f}%) — '
              f'{n_place:>5d} city, {n_county:>5d} county, {n_none:>5d} no match '
              f'[{elapsed:.2f}s @ {rate:.0f}/s]')

    # Log provenance
    if not DRY_RUN:
        timestamp = datetime.now(timezone.utc).isoformat()
        wconn.execute(
            """INSERT INTO provenance_log 
               (source, script_name, started_at, completed_at, 
                churches_updated, churches_inserted, fields_populated,
                records_attempted, records_matched, status, notes)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            ('census_tiger_amchitka_fix', 'fix_amchitka_cities.py', timestamp, timestamp,
             updated_total, 0,
             'city, county, county_fips_5, address_components',
             total, updated_total, 'completed',
             f'Amchitka fix: {amchitka_count} placeholder + {null_count} NULL/empty. '
             f'{place_hits} place matches, {county_hits} county fallback, {no_match_total} no match.')
        )

    print(f'\n{"=" * 60}')
    print(f'Complete!')
    print(f'  Total processed: {total:,}')
    print(f'  Place matches (city): {place_hits:,}')
    print(f'  County fallback: {county_hits:,}')
    print(f'  No match: {no_match_total:,}')
    print(f'  Time: {time.time()-t0:.0f}s')
    print(f'  Mode: {"DRY RUN" if DRY_RUN else "LIVE — DB updated"}')

    if DRY_RUN:
        print(f'\nRun without --dry-run to write to database.')

    wconn.close()

if __name__ == '__main__':
    main()
