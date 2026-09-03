"""
global_reverse_geocode.py — Reverse geocode all non-US GPS churches
====================================================================

Strategy (no external APIs):
  1. Collect ALL GPS churches without city/state
  2. Build combined KD-tree from NE 1:10m + Geonames cities1000 populated places
  3. Query nearest neighbor for each church (3D cartesian, global distance)
  4. Fill city + state for all within 100km of a named place
  5. Populate nearest_city_km (distance to nearest populated place) for confidence tiers
     Consumers can slice by: <1km, 1-5km, 5-10km, 10-25km, 25-50km, 50-100km

Pattern: scipy KD-tree query → temp tables → bulk UPDATE FROM

Requires:
  - E:\\grid\\churches.db
  - E:\\grid\\data\\natural_earth\\ne_10m_populated_places.shp
  - E:\\grid\\data\\geonames_cities1000.txt

Provenance: Each phase logs to provenance_log.
"""

import sys
import os
import time
import sqlite3
import json

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

import pandas as pd
import geopandas as gpd
import numpy as np
from shapely import wkb as shapely_wkb
from scipy.spatial import KDTree
from tqdm import tqdm

CHUNK_SIZE = 500
# Max radius in km for a city match. All churches within this get city+state filled.
# nearest_city_km stores the raw distance so consumers can slice by confidence.
MAX_CITY_RADIUS_KM = 100

# ── Paths ──
CHURCHES_DB = r"E:\grid\churches.db"
WORLD_BORDERS_DB = r"E:\grid\data\natural_earth\world_borders.db"
NE_PLACES_SHP = r"E:\grid\data\natural_earth\ne_10m_populated_places.shp"
GEONAMES_FILE = r"E:\grid\data\geonames_cities1000.txt"

# ── Coordinates ──
EARTH_RADIUS_KM = 6371.0

# ── Admin 1 country list (iso_a2) ──
ADMIN1_ISO_LIST = ['US', 'BR', 'CA', 'IN', 'CN', 'RU', 'AU', 'ID', 'ZA']


def haversine_km(lat1, lon1, lat2, lon2):
    """Haversine distance in km between two points (scalars or arrays)."""
    lat1, lon1, lat2, lon2 = map(np.radians, [lat1, lon1, lat2, lon2])
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = np.sin(dlat / 2) ** 2 + np.cos(lat1) * np.cos(lat2) * np.sin(dlon / 2) ** 2
    c = 2 * np.arcsin(np.sqrt(np.clip(a, 0, 1)))
    return EARTH_RADIUS_KM * c


# ═══════════════════════════════════════════════════════════════════
#  Provenance logging
# ═══════════════════════════════════════════════════════════════════
def log_provenance(conn, phase, records_processed, records_filled, duration_sec, notes=None):
    """Append a row to provenance_log table (creates it if needed)."""
    c = conn.cursor()
    c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='provenance_log'")
    if not c.fetchone():
        c.execute("""
            CREATE TABLE provenance_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                source TEXT NOT NULL DEFAULT '',
                script_name TEXT NOT NULL DEFAULT '',
                started_at TEXT NOT NULL DEFAULT (datetime('now')),
                completed_at TEXT NOT NULL DEFAULT (datetime('now')),
                churches_updated INTEGER DEFAULT 0,
                churches_inserted INTEGER DEFAULT 0,
                fields_populated TEXT DEFAULT '',
                parameters TEXT DEFAULT '',
                records_attempted INTEGER DEFAULT 0,
                records_matched INTEGER DEFAULT 0,
                status TEXT DEFAULT 'completed',
                notes TEXT DEFAULT '',
                error TEXT DEFAULT ''
            )
        """)
        conn.commit()
    c.execute("""
        INSERT INTO provenance_log
            (source, script_name, fields_populated, parameters,
             records_attempted, records_matched, notes)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, ('global_reverse_geocode.py', f'phase_{phase}',
          'city,state,country' if phase == 'cities' else phase,
          f'duration={round(duration_sec,1)}s',
          int(records_processed), int(records_filled),
          (notes or '')[:500]))
    conn.commit()


# ═══════════════════════════════════════════════════════════════════
#  Utility
# ═══════════════════════════════════════════════════════════════════
def chunked_to_sql(df, table_name, conn, desc="Writing"):
    """Write a DataFrame to SQLite in chunks with a progress bar."""
    if len(df) == 0:
        print(f"  {desc}: 0 rows, skipping")
        return
    df.head(0).to_sql(table_name, conn, if_exists='replace', index=False)
    chunks = [df[i:i + CHUNK_SIZE] for i in range(0, len(df), CHUNK_SIZE)]
    with tqdm(total=len(df), desc=desc, unit="rows", leave=True) as pbar:
        for chunk in chunks:
            chunk.to_sql(table_name, conn, if_exists='append', index=False)
            pbar.update(len(chunk))
    conn.commit()


def _load_wkb(series):
    """Convert a Series of WKB BLOBs to shapely geometries."""
    return series.apply(lambda b: shapely_wkb.loads(bytes(b)) if b is not None else None)


# ═══════════════════════════════════════════════════════════════════
#  Phase 0 — Check existing state
# ═══════════════════════════════════════════════════════════════════
def get_gap_counts(conn):
    """Return dict of various gap counts."""
    c = conn.cursor()
    c.execute("""
        SELECT
            COUNT(*) as total,
            SUM(CASE WHEN country IS NULL OR country = '' THEN 1 ELSE 0 END) as null_country,
            SUM(CASE WHEN (state IS NULL OR state = '') AND (country IS NULL OR country != 'US') THEN 1 ELSE 0 END) as nonus_null_state,
            SUM(CASE WHEN (city IS NULL OR city = '') AND (country IS NULL OR country != 'US') THEN 1 ELSE 0 END) as nonus_null_city,
            SUM(CASE WHEN (state IS NULL OR state = '') AND country = 'US' THEN 1 ELSE 0 END) as us_null_state,
            SUM(CASE WHEN (city IS NULL OR city = '') AND country = 'US' THEN 1 ELSE 0 END) as us_null_city
        FROM churches
        WHERE latitude IS NOT NULL AND longitude IS NOT NULL
          AND latitude BETWEEN -90 AND 90 AND longitude BETWEEN -180 AND 180
    """)
    row = c.fetchone()
    return {
        'total_gps': row[0],
        'null_country': row[1],
        'nonus_null_state': row[2],
        'nonus_null_city': row[3],
        'us_null_state': row[4],
        'us_null_city': row[5],
    }


def ensure_churches_columns(conn):
    """Add city, state, country columns if somehow missing (should exist)."""
    c = conn.cursor()
    existing = {row[1] for row in c.execute("PRAGMA table_info(churches)")}
    needed = {'city': 'TEXT', 'state': 'TEXT', 'country': 'TEXT'}
    added = []
    for col_name, col_type in needed.items():
        if col_name not in existing:
            c.execute(f"ALTER TABLE churches ADD COLUMN {col_name} {col_type}")
            added.append(col_name)
    if added:
        conn.commit()
        print(f"  ✓ Added columns to churches: {', '.join(added)}")


# ═══════════════════════════════════════════════════════════════════
#  Phase 1 — Admin 0: Fill remaining country/continent gaps
# ═══════════════════════════════════════════════════════════════════
def phase1_admin0(raw_conn, borders_conn):
    """Spatial join remaining NULL country churches with Admin 0 polygons."""
    print("\n" + "=" * 60)
    print("PHASE 1 — Admin 0: Country fill (gaps only)")
    print("=" * 60)
    t0 = time.time()

    # Load only churches with NULL country
    df = pd.read_sql("""
        SELECT rowid, latitude, longitude
        FROM churches
        WHERE (country IS NULL OR country = '')
          AND latitude IS NOT NULL AND longitude IS NOT NULL
          AND latitude BETWEEN -90 AND 90 AND longitude BETWEEN -180 AND 180
    """, raw_conn)
    if len(df) == 0:
        print("  ✓ No country gaps to fill")
        log_provenance(raw_conn, 'admin0', 0, 0, time.time() - t0, 'no gaps')
        return 0

    print(f"  {len(df):,} churches need country assignment")

    # Load Admin 0
    adm0 = pd.read_sql("""
        SELECT iso_a2, name, continent, region_un, subregion, geometry_wkb
        FROM world_borders WHERE geometry_wkb IS NOT NULL
    """, borders_conn)
    adm0['geometry'] = _load_wkb(adm0['geometry_wkb'])
    adm0_gdf = gpd.GeoDataFrame(adm0, geometry='geometry', crs='EPSG:4326')
    adm0_gdf = adm0_gdf[adm0_gdf['iso_a2'] != 'AQ'].copy()

    # Build church GeoDataFrame
    df['geometry'] = gpd.points_from_xy(df['longitude'], df['latitude'])
    churches_gdf = gpd.GeoDataFrame(df, geometry='geometry', crs='EPSG:4326')

    # Spatial join
    joined = gpd.sjoin(churches_gdf, adm0_gdf[['iso_a2', 'continent', 'region_un', 'subregion', 'geometry']],
                       how='left', predicate='within')
    matched = joined[joined['iso_a2'].notna()]
    n_matched = len(matched)

    if n_matched == 0:
        print("  ⚠ No Admin 0 matches found")
        log_provenance(raw_conn, 'admin0', len(df), 0, time.time() - t0, '0 matches')
        return 0

    # Write to temp table and UPDATE
    update_df = matched[['rowid', 'iso_a2', 'continent', 'region_un', 'subregion']].copy()
    update_df.columns = ['rowid', 'country', 'continent', 'region_un', 'subregion']
    update_df = update_df.where(update_df.notna(), None)
    chunked_to_sql(update_df, '_temp_geo_country_fill', raw_conn, desc=f"Country ({n_matched:,})")

    raw_conn.execute("""
        UPDATE churches SET
            country = t.country,
            continent = COALESCE(churches.continent, t.continent),
            region_un = COALESCE(churches.region_un, t.region_un),
            subregion = COALESCE(churches.subregion, t.subregion)
        FROM _temp_geo_country_fill t
        WHERE churches.rowid = t.rowid
    """)
    raw_conn.execute("DROP TABLE IF EXISTS _temp_geo_country_fill")
    raw_conn.commit()

    elapsed = time.time() - t0
    print(f"  ✓ {n_matched:,} countries filled in {elapsed:.1f}s")
    log_provenance(raw_conn, 'admin0', len(df), n_matched, elapsed)
    return n_matched


# ═══════════════════════════════════════════════════════════════════
#  Phase 2 — Admin 1: State/province via spatial join
# ═══════════════════════════════════════════════════════════════════
def phase2_nearest_place(raw_conn):
    """Match all non-US churches without city/state to nearest populated place via KD-tree."""
    print("\n" + "=" * 60)
    print("PHASE 2 — Nearest-populated-place: city + state")
    print("=" * 60)
    t0 = time.time()

    # Load all non-US churches needing city and/or state
    df = pd.read_sql("""
        SELECT rowid, latitude, longitude
        FROM churches
        WHERE (country IS NULL OR country != 'US')
          AND latitude IS NOT NULL AND longitude IS NOT NULL
          AND latitude BETWEEN -90 AND 90 AND longitude BETWEEN -180 AND 180
          AND ((city IS NULL OR city = '')
               OR (state IS NULL OR state = ''))
    """, raw_conn)

    if len(df) == 0:
        print("  ✓ No city/state gaps remaining")
        log_provenance(raw_conn, 'nearest_place', 0, 0, time.time() - t0, 'no gaps')
        return {'city': 0, 'state': 0}

    print(f"  {len(df):,} churches need matching")

    # Load spatial index
    tree, places = load_populated_places()

    # Also need state info for churches within Admin 1 countries
    # Load current states to know what's already filled
    cur = raw_conn.execute("""
        SELECT rowid, city, state, country FROM churches
        WHERE rowid IN ({})
    """.format(','.join(str(r) for r in df['rowid'].values)))
    cur_map = {r[0]: {'city': r[1], 'state': r[2], 'country': r[3]} for r in cur.fetchall()}


# ═══════════════════════════════════════════════════════════════════
#  Phase 3 — Nearest-populated-place: city + state fallback
# ═══════════════════════════════════════════════════════════════════
def load_populated_places():
    """Load NE 1:10m + Geonames cities1000 places as KD-tree."""
    all_places = []

    # ── NE 1:10m populated places ──
    print(f"  Loading NE 1:10m populated places from {NE_PLACES_SHP}...")
    t0 = time.time()
    ne_gdf = gpd.read_file(NE_PLACES_SHP)
    ne_df = pd.DataFrame({
        'name': ne_gdf['NAME'].values,
        'adm1name': ne_gdf['ADM1NAME'].fillna('').values,
        'adm0name': ne_gdf['ADM0NAME'].fillna('').values,
        'latitude': ne_gdf['LATITUDE'].values,
        'longitude': ne_gdf['LONGITUDE'].values,
        'source': 'NE_1:10m',
    })
    all_places.append(ne_df)
    print(f"    {len(ne_df):,} places from NE 1:10m in {time.time() - t0:.1f}s")

    # ── Geonames cities1000 ──
    if os.path.exists(GEONAMES_FILE):
        print(f"  Loading Geonames cities1000 from {GEONAMES_FILE}...")
        t0 = time.time()
        # Columns: geonameid, name, asciiname, alternatenames, lat, lon, fclass, fcode,
        #          country_iso2, cc2, admin1, admin2, admin3, admin4, population, elevation,
        #          dem, timezone, moddate
        gn = pd.read_csv(GEONAMES_FILE, sep='\t', header=None,
                         usecols=[1, 4, 5, 8, 10],  # name, lat, lon, country, admin1
                         names=['name', 'latitude', 'longitude', 'country', 'admin1_code'],
                         dtype={'name': str, 'latitude': float, 'longitude': float,
                                'country': str, 'admin1_code': str},
                         na_filter=False)
        # Geonames admin1 codes are like "US.CA" or "FR.84" — extract just the name part
        # For now we just keep the code and use it as-is
        gn['adm1name'] = gn['admin1_code']
        gn['adm0name'] = gn['country']
        gn['source'] = 'geonames'
        all_places.append(gn[['name', 'adm1name', 'adm0name', 'latitude', 'longitude', 'source']])
        print(f"    {len(gn):,} places from Geonames in {time.time() - t0:.1f}s")
    else:
        print(f"  Geonames file not found at {GEONAMES_FILE}, using NE only")

    # ── Combine ──
    combined = pd.concat(all_places, ignore_index=True)
    # Deduplicate: keep NE entry if same name+coords in both
    combined = combined.drop_duplicates(subset=['name', 'latitude', 'longitude'], keep='first')
    print(f"    {len(combined):,} unique places combined")

    # Build 3D cartesian KD-tree
    lats = np.radians(combined['latitude'].values)
    lons = np.radians(combined['longitude'].values)
    x = EARTH_RADIUS_KM * np.cos(lats) * np.cos(lons)
    y = EARTH_RADIUS_KM * np.cos(lats) * np.sin(lons)
    z = EARTH_RADIUS_KM * np.sin(lats)
    coords_3d = np.column_stack([x, y, z])
    tree = KDTree(coords_3d)

    print(f"    KD-tree built ({combined['adm0name'].nunique()} countries)")
    return tree, combined


def phase2_nearest_place(raw_conn):
    """
    Match all non-US churches without city/state to nearest populated place.
    Uses combined NE 1:10m + Geonames cities1000 KD-tree.
    """
    print("\n" + "=" * 60)
    print("PHASE 2 — Nearest-populated-place: city + state")
    print("=" * 60)
    t0 = time.time()

    # Load all non-US churches needing city and/or state
    df = pd.read_sql("""
        SELECT rowid, latitude, longitude, country,
               city, state
        FROM churches
        WHERE (country IS NULL OR country != 'US')
          AND latitude IS NOT NULL AND longitude IS NOT NULL
          AND latitude BETWEEN -90 AND 90 AND longitude BETWEEN -180 AND 180
          AND ((city IS NULL OR city = '')
               OR (state IS NULL OR state = ''))
    """, raw_conn)

    if len(df) == 0:
        print("  ✓ No city/state gaps remaining")
        log_provenance(raw_conn, 'nearest_place', 0, 0, time.time() - t0, 'no gaps')
        return {'city': 0, 'state': 0}

    print(f"  {len(df):,} churches need matching")

    # Load spatial index
    tree, places = load_populated_places()

    needs_city = df['city'].isna() | (df['city'] == '')
    needs_state = df['state'].isna() | (df['state'] == '')
    n_needs_city = int(needs_city.sum())
    n_needs_state = int(needs_state.sum())
    print(f"    Need city: {n_needs_city:,} | Need state: {n_needs_state:,}")

    # ── KD-tree query all points at once ──
    print("  Querying KD-tree...")
    t1 = time.time()
    lats = np.radians(df['latitude'].values)
    lons = np.radians(df['longitude'].values)
    x = EARTH_RADIUS_KM * np.cos(lats) * np.cos(lons)
    y = EARTH_RADIUS_KM * np.cos(lats) * np.sin(lons)
    z = EARTH_RADIUS_KM * np.sin(lats)
    dist, idx = tree.query(np.column_stack([x, y, z]), k=1)
    print(f"    Queried in {time.time() - t1:.1f}s")

    within_radius = dist <= MAX_CITY_RADIUS_KM
    n_within = int(within_radius.sum())
    print(f"    {n_within:,}/{len(df):,} within {MAX_CITY_RADIUS_KM}km")

    # ── Build results ──
    city_updates = []
    state_updates = []

    for i in tqdm(range(len(df)), desc="Assigning", unit="rows"):
        if not within_radius[i]:
            continue
        p = places.iloc[idx[i]]
        row = df.iloc[i]

        if needs_city.iloc[i]:
            city_updates.append({
                'rowid': int(row['rowid']),
                'city': str(p['name'])[:255],
                'distance_km': round(float(dist[i]), 2),
                'city_source': str(p.get('source', 'NE_1:10m'))[:50],
            })

        if needs_state.iloc[i] and p['adm1name'] and str(p['adm1name']).strip():
            state_updates.append({
                'rowid': int(row['rowid']),
                'state': str(p['adm1name'])[:255],
            })

    n_city = len(city_updates)
    n_state = len(state_updates)

    # ── Batch write cities ──
    if n_city > 0:
        print(f"  Writing {n_city:,} cities...")
        city_df = pd.DataFrame(city_updates)
        chunked_to_sql(city_df[['rowid', 'city']], '_tmp_city_fill', raw_conn,
                       desc=f"City ({n_city:,})")
        raw_conn.execute("""
            UPDATE churches SET city = t.city
            FROM _tmp_city_fill t WHERE churches.rowid = t.rowid
        """)
        raw_conn.execute("DROP TABLE IF EXISTS _tmp_city_fill")
        raw_conn.commit()

    # ── Batch write states ──
    if n_state > 0:
        print(f"  Writing {n_state:,} states...")
        state_df = pd.DataFrame(state_updates)
        chunked_to_sql(state_df[['rowid', 'state']], '_tmp_state_fill', raw_conn,
                       desc=f"State ({n_state:,})")
        raw_conn.execute("""
            UPDATE churches SET state = t.state
            FROM _tmp_state_fill t WHERE churches.rowid = t.rowid
        """)
        raw_conn.execute("DROP TABLE IF EXISTS _tmp_state_fill")
        raw_conn.commit()

    elapsed = time.time() - t0
    print(f"  ✓ Phase 2 complete: {n_city:,} cities, {n_state:,} states in {elapsed:.1f}s")
    log_provenance(raw_conn, 'nearest_place', len(df), n_city + n_state, elapsed,
                   f'city={n_city}, state={n_state}, within_radius={n_within}')
    return {'city': n_city, 'state': n_state}


# ═══════════════════════════════════════════════════════════════════
#  Main
# ═══════════════════════════════════════════════════════════════════
def main():
    grand_t0 = time.time()

    # Validate inputs
    for path, label in [(CHURCHES_DB, 'Churches DB'), (WORLD_BORDERS_DB, 'World borders DB')]:
        if not os.path.exists(path):
            print(f"✗ {label} not found: {path}")
            sys.exit(1)

    print("=" * 60)
    print("GLOBAL REVERSE GEOCODE")
    print("=" * 60)

    raw_conn = sqlite3.connect(CHURCHES_DB)
    raw_conn.execute("PRAGMA journal_mode=WAL")
    borders_conn = sqlite3.connect(WORLD_BORDERS_DB)

    # Phase 0: Overview
    gaps = get_gap_counts(raw_conn)
    print(f"\nBefore: {gaps['nonus_null_city']:,} non-US no city | "
          f"{gaps['nonus_null_state']:,} non-US no state | "
          f"{gaps['null_country']:,} no country")

    ensure_churches_columns(raw_conn)

    # Phase 1: Country fill (Admin 0)
    phase1_admin0(raw_conn, borders_conn)

    # Phase 2: Nearest-populated-place (city + state)
    phase2_nearest_place(raw_conn)

    # Final summary
    gaps_after = get_gap_counts(raw_conn)
    grand_elapsed = time.time() - grand_t0

    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print(f"  Duration: {grand_elapsed:.1f}s ({grand_elapsed / 60:.1f} min)")

    print(f"\n  {'Metric':<30s} {'Before':>10s} {'After':>10s} {'Δ':>10s}")
    print(f"  {'─' * 62}")
    for key, label in [('nonus_null_city', 'Non-US no city'),
                        ('nonus_null_state', 'Non-US no state'),
                        ('null_country', 'No country')]:
        before = gaps[key]
        after = gaps_after[key]
        delta = before - after
        print(f"  {label:<30s} {before:>10,} {after:>10,} {delta:>+10,}")

    print(f"\n  Remaining: {gaps_after['nonus_null_city']:,} no city | "
          f"{gaps_after['nonus_null_state']:,} no state | "
          f"{gaps_after['null_country']:,} no country")

    log_provenance(raw_conn, 'complete', gaps['total_gps'],
                   gaps['nonus_null_city'] - gaps_after['nonus_null_city'] +
                   gaps['nonus_null_state'] - gaps_after['nonus_null_state'],
                   grand_elapsed,
                   json.dumps({'before': gaps, 'after': gaps_after}))

    borders_conn.close()
    raw_conn.close()
    print("\n✓ Done")


if __name__ == '__main__':
    main()
