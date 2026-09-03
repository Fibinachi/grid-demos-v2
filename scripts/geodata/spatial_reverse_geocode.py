"""
spatial_reverse_geocode.py — Assign country, state, continent from Natural Earth boundaries
==========================================================================================

Reverse-geocodes all churches with GPS coordinates using Natural Earth
Admin 0 (countries) and Admin 1 (states/provinces) boundary datasets.

Phases:
    0. Add continent/region/subregion columns to churches table if missing
    1. Admin 0 — assign country (58 gaps) + continent/region/subregion (3.3M GPS)
    2. Admin 1 — assign state/province for 9 countries with Admin 1 coverage
    3. US FIPS-derived state — fast fallback for US churches with county_fips_5

Pattern follows spatial_assign_us_county.py:
    GeoPandas sjoin → temp tables → bulk UPDATE FROM

Usage:
    python scripts/geodata/spatial_reverse_geocode.py

Requires:
    - E:\\grid\\churches.db (churches table with latitude/longitude)
    - E:\\grid\\data\\natural_earth\\world_borders.db (world_borders + state_borders tables)
"""

import sys
import os
import time
import sqlite3

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

import pandas as pd
import geopandas as gpd
from shapely import wkb as shapely_wkb
from tqdm import tqdm


CHUNK_SIZE = 500  # rows per batch for write operations


def chunked_to_sql(df, table_name, conn, desc="Writing"):
    """Write a DataFrame to SQLite in chunks with a progress bar.

    Avoids silent multi-million-row to_sql calls. Chunks are written
    individually so the progress bar updates visibly.
    """
    if len(df) == 0:
        print(f"  {desc}: 0 rows, skipping")
        return

    # Write schema first (empty df with if_exists='replace')
    df.head(0).to_sql(table_name, conn, if_exists='replace', index=False)

    # Then chunk the data
    chunks = [df[i:i + CHUNK_SIZE] for i in range(0, len(df), CHUNK_SIZE)]
    with tqdm(total=len(df), desc=desc, unit="rows", leave=True) as pbar:
        for chunk in chunks:
            chunk.to_sql(table_name, conn, if_exists='append', index=False)
            pbar.update(len(chunk))

    conn.commit()

# ── Paths ──
CHURCHES_DB = r"E:\grid\churches.db"
WORLD_BORDERS_DB = r"E:\grid\data\natural_earth\world_borders.db"

# ── Admin 1 country list (iso_a2) ──
ADMIN1_ISO_LIST = ['US', 'BR', 'CA', 'IN', 'CN', 'RU', 'AU', 'ID', 'ZA']

# ── US State FIPS mapping ──
US_STATE_FIPS = {
    '01': 'AL', '02': 'AK', '04': 'AZ', '05': 'AR', '06': 'CA',
    '08': 'CO', '09': 'CT', '10': 'DE', '11': 'DC', '12': 'FL',
    '13': 'GA', '15': 'HI', '16': 'ID', '17': 'IL', '18': 'IN',
    '19': 'IA', '20': 'KS', '21': 'KY', '22': 'LA', '23': 'ME',
    '24': 'MD', '25': 'MA', '26': 'MI', '27': 'MN', '28': 'MS',
    '29': 'MO', '30': 'MT', '31': 'NE', '32': 'NV', '33': 'NH',
    '34': 'NJ', '35': 'NM', '36': 'NY', '37': 'NC', '38': 'ND',
    '39': 'OH', '40': 'OK', '41': 'OR', '42': 'PA', '44': 'RI',
    '45': 'SC', '46': 'SD', '47': 'TN', '48': 'TX', '49': 'UT',
    '50': 'VT', '51': 'VA', '53': 'WA', '54': 'WV', '55': 'WI',
    '56': 'WY', '60': 'AS', '66': 'GU', '69': 'MP', '72': 'PR',
    '78': 'VI',
}


# ═══════════════════════════════════════════════════════════════════
#  Phase 0 — Schema Setup
# ═══════════════════════════════════════════════════════════════════
def ensure_geo_columns(conn):
    """Add continent/region/subregion columns to churches table if missing."""
    c = conn.cursor()
    existing = {row[1] for row in c.execute("PRAGMA table_info(churches)")}
    new_cols = {
        'continent': 'TEXT',
        'region_un': 'TEXT',
        'subregion': 'TEXT',
    }
    added = []
    for col_name, col_type in new_cols.items():
        if col_name not in existing:
            c.execute(f"ALTER TABLE churches ADD COLUMN {col_name} {col_type}")
            added.append(col_name)
    if added:
        conn.commit()
        print(f"  ✓ Added columns: {', '.join(added)}")
    else:
        print("  ✓ All geo columns already exist")
    return added


# ═══════════════════════════════════════════════════════════════════
#  Phase 1 — Admin 0: Country + Continent/Region/Subregion
# ═══════════════════════════════════════════════════════════════════
def _load_wkb(series):
    """Convert a Series of WKB BLOBs to shapely geometries."""
    return series.apply(lambda b: shapely_wkb.loads(bytes(b)) if b is not None else None)


def load_admin0(borders_conn):
    """Load Admin 0 polygons as GeoDataFrame."""
    print("  Loading Admin 0 boundaries...")
    df = pd.read_sql("""
        SELECT iso_a2, name, continent, region_un, subregion, geometry_wkb
        FROM world_borders
        WHERE geometry_wkb IS NOT NULL
    """, borders_conn)
    print(f"    {len(df)} country polygons loaded")
    df['geometry'] = _load_wkb(df['geometry_wkb'])
    gdf = gpd.GeoDataFrame(df, geometry='geometry', crs='EPSG:4326')
    # Drop Antarctica
    gdf = gdf[gdf['iso_a2'] != 'AQ'].copy()
    print(f"    {len(gdf)} polygons after removing Antarctica")
    return gdf


def load_churches_with_gps(raw_conn):
    """Load churches with GPS coordinates as GeoDataFrame."""
    print("  Loading churches with GPS coordinates...")
    df = pd.read_sql("""
        SELECT rowid, latitude, longitude, country, continent, region_un, subregion
        FROM churches
        WHERE latitude IS NOT NULL AND longitude IS NOT NULL
          AND latitude BETWEEN -90 AND 90 AND longitude BETWEEN -180 AND 180
    """, raw_conn)
    print(f"    {len(df):,} churches loaded")
    df['geometry'] = gpd.points_from_xy(df['longitude'], df['latitude'])
    return gpd.GeoDataFrame(df, geometry='geometry', crs='EPSG:4326')


def phase1_admin0(raw_conn, borders_conn):
    """
    Spatial join all GPS churches with Admin 0 polygons.
    Writes: country (fills 58 gaps), continent/region_un/subregion (fills all 3.3M)
    """
    print("\n" + "=" * 65)
    print("PHASE 1 — Admin 0: Country + Continent/Region")
    print("=" * 65)

    t0 = time.time()

    admin0_gdf = load_admin0(borders_conn)
    churches_gdf = load_churches_with_gps(raw_conn)
    n_total = len(churches_gdf)

    # Spatial join
    print("  Performing spatial join (point-in-polygon)...")
    t1 = time.time()
    joined = gpd.sjoin(
        churches_gdf,
        admin0_gdf[['iso_a2', 'continent', 'region_un', 'subregion', 'geometry']],
        how='left', predicate='within'
    )
    join_time = time.time() - t1
    matched = int(joined['iso_a2'].notna().sum())
    print(f"    {matched:,}/{n_total:,} points matched ({matched / n_total * 100:.1f}%) in {join_time:.1f}s")

    # Determine what needs updating
    # After sjoin, overlapping columns get _left/_right suffixes
    needs_country = joined['country'].isna() & joined['iso_a2'].notna()
    n_country = int(needs_country.sum())

    needs_continent = joined['continent_left'].isna() & joined['continent_right'].notna()
    n_continent = int(needs_continent.sum())

    print(f"    Country fills needed: {n_country:,}")
    print(f"    Continent fills needed: {n_continent:,}")

    # ── Batch write: country ──
    if n_country > 0:
        print(f"  Writing {n_country:,} country assignments...")
        t2 = time.time()
        country_df = joined.loc[needs_country, ['rowid', 'iso_a2']].copy()
        country_df.columns = ['rowid', 'country']
        chunked_to_sql(country_df, '_temp_geo_country', raw_conn,
                       desc=f"Country ({n_country:,})")
        raw_conn.execute("""
            UPDATE churches SET country = t.country
            FROM _temp_geo_country t
            WHERE churches.rowid = t.rowid
        """)
        raw_conn.execute("DROP TABLE IF EXISTS _temp_geo_country")
        raw_conn.commit()
        print(f"    ✓ Country written in {time.time() - t2:.1f}s")

    # ── Batch write: continent/region/subregion ──
    if n_continent > 0:
        print(f"  Writing {n_continent:,} continent/region assignments...")
        t2 = time.time()
        # continent_left is NULL (just-added column), continent_right has admin0 data
        geo_df = joined.loc[needs_continent, ['rowid', 'continent_right', 'region_un_right', 'subregion_right']].copy()
        geo_df.columns = ['rowid', 'continent', 'region_un', 'subregion']
        # Handle NaN → None for SQLite
        geo_df = geo_df.where(geo_df.notna(), None)
        chunked_to_sql(geo_df, '_temp_geo_continent', raw_conn,
                       desc=f"Continent/Region ({n_continent:,})")
        raw_conn.execute("""
            UPDATE churches SET
                continent = t.continent,
                region_un = t.region_un,
                subregion = t.subregion
            FROM _temp_geo_continent t
            WHERE churches.rowid = t.rowid
        """)
        raw_conn.execute("DROP TABLE IF EXISTS _temp_geo_continent")
        raw_conn.commit()
        print(f"    ✓ Continent/region written in {time.time() - t2:.1f}s")

    total_time = time.time() - t0
    print(f"  Phase 1 complete in {total_time:.1f}s")

    return {
        'phase': 'admin0',
        'churches_total': int(n_total),
        'churches_matched': int(matched),
        'country_filled': n_country,
        'continent_filled': n_continent,
        'duration_seconds': round(total_time, 1),
    }


# ═══════════════════════════════════════════════════════════════════
#  Phase 2 — Admin 1: State/Province
# ═══════════════════════════════════════════════════════════════════
def load_admin1(borders_conn):
    """Load Admin 1 state polygons as GeoDataFrame."""
    print("  Loading Admin 1 boundaries...")
    df = pd.read_sql("""
        SELECT iso_a2, name_en, type_en, geometry_wkb
        FROM state_borders
        WHERE geometry_wkb IS NOT NULL
    """, borders_conn)
    df['geometry'] = _load_wkb(df['geometry_wkb'])
    gdf = gpd.GeoDataFrame(df, geometry='geometry', crs='EPSG:4326')
    print(f"    {len(gdf)} state/province polygons from {gdf['iso_a2'].nunique()} countries")
    return gdf


def phase2_admin1(raw_conn, borders_conn):
    """
    Spatial join churches in Admin 1 countries with state/province boundaries.
    Writes: state on churches table.
    """
    print("\n" + "=" * 65)
    print("PHASE 2 — Admin 1: State/Province")
    print("=" * 65)

    t0 = time.time()
    admin1_gdf = load_admin1(borders_conn)

    # Process all Admin 1 countries at once for efficiency
    placeholders = ','.join(['?'] * len(ADMIN1_ISO_LIST))
    print(f"  Loading churches in Admin 1 countries ({', '.join(ADMIN1_ISO_LIST)}) without state...")
    df_churches = pd.read_sql(f"""
        SELECT rowid, latitude, longitude, country
        FROM churches
        WHERE country IN ({placeholders})
          AND latitude IS NOT NULL AND longitude IS NOT NULL
          AND latitude BETWEEN -90 AND 90 AND longitude BETWEEN -180 AND 180
          AND (state IS NULL OR state = '')
    """, raw_conn, params=tuple(ADMIN1_ISO_LIST))
    print(f"    {len(df_churches):,} churches need state assignment")

    if len(df_churches) == 0:
        print("  ✓ No churches need state assignment in Admin 1 countries")
        return None

    # Build point GeoDataFrame
    df_churches['geometry'] = gpd.points_from_xy(df_churches['longitude'], df_churches['latitude'])
    churches_gdf = gpd.GeoDataFrame(df_churches, geometry='geometry', crs='EPSG:4326')

    # Spatial join
    print(f"  Performing spatial join ({len(admin1_gdf)} state polygons)...")
    t1 = time.time()
    joined = gpd.sjoin(
        churches_gdf,
        admin1_gdf[['name_en', 'iso_a2', 'geometry']],
        how='left', predicate='within'
    )
    join_time = time.time() - t1
    matched = int(joined['name_en'].notna().sum())
    print(f"    {matched:,}/{len(churches_gdf):,} matched ({matched / len(churches_gdf) * 100:.1f}%) in {join_time:.1f}s")

    if matched == 0:
        print("  ⚠ No Admin 1 matches found — possible CRS/geometry issue")
        return None

    # Write state via temp table
    print(f"  Writing {matched:,} state assignments...")
    t2 = time.time()

    state_df = joined.loc[joined['name_en'].notna(), ['rowid', 'name_en']].copy()
    state_df.columns = ['rowid', 'state']
    total_filled = len(state_df)
    chunked_to_sql(state_df, '_temp_geo_state', raw_conn,
                   desc=f"State ({total_filled:,})")
    raw_conn.execute("""
        UPDATE churches SET state = t.state
        FROM _temp_geo_state t
        WHERE churches.rowid = t.rowid
    """)
    raw_conn.execute("DROP TABLE IF EXISTS _temp_geo_state")
    raw_conn.commit()
    print(f"    ✓ State written for {total_filled:,} churches in {time.time() - t2:.1f}s")

    # Per-country breakdown
    joined_matched = joined[joined['name_en'].notna()]
    country_results = []
    for iso in ADMIN1_ISO_LIST:
        cnt = int((joined_matched['country'] == iso).sum())
        country_results.append({'country': iso, 'states_filled': cnt})
        if cnt > 0:
            print(f"      {iso}: {cnt:,}")

    total_time = time.time() - t0
    print(f"  Phase 2 complete in {total_time:.1f}s")

    return {
        'phase': 'admin1',
        'churches_processed': int(len(churches_gdf)),
        'states_filled': total_filled,
        'per_country': country_results,
        'duration_seconds': round(total_time, 1),
    }


# ═══════════════════════════════════════════════════════════════════
#  Phase 3 — US FIPS-derived State
# ═══════════════════════════════════════════════════════════════════
def phase3_us_fips(raw_conn):
    """
    Derive US state from county_fips_5 (first 2 digits → state code).
    Fast pass — no spatial join needed.
    """
    print("\n" + "=" * 65)
    print("PHASE 3 — US FIPS-derived State")
    print("=" * 65)

    c = raw_conn.cursor()

    # Check how many would be affected
    c.execute("""
        SELECT COUNT(*) FROM churches
        WHERE country='US' AND (state IS NULL OR state = '')
          AND county_fips_5 IS NOT NULL AND county_fips_5 != ''
    """)
    eligible = c.fetchone()[0]
    print(f"  US churches with county_fips_5 but no state: {eligible:,}")

    if eligible == 0:
        print("  ✓ No eligible US churches for FIPS-derived state")
        return None

    # Build CASE expression from US_STATE_FIPS
    fips_in = ','.join([f"'{k}'" for k in US_STATE_FIPS.keys()])
    case_when = ' '.join([f"WHEN '{fips}' THEN '{abbr}'" for fips, abbr in US_STATE_FIPS.items()])
    sql = f"""
        UPDATE churches
        SET state = CASE SUBSTR(county_fips_5, 1, 2)
            {case_when}
            ELSE state
        END
        WHERE country='US' AND (state IS NULL OR state = '')
          AND county_fips_5 IS NOT NULL AND county_fips_5 != ''
          AND SUBSTR(county_fips_5, 1, 2) IN ({fips_in})
    """

    t0 = time.time()
    c.execute(sql)
    filled = c.rowcount
    raw_conn.commit()
    duration = time.time() - t0
    print(f"  ✓ {filled:,} states filled via FIPS in {duration:.1f}s")

    return {
        'phase': 'us_fips',
        'states_filled_fips': int(filled),
        'duration_seconds': round(duration, 1),
    }


# ═══════════════════════════════════════════════════════════════════
#  Main
# ═══════════════════════════════════════════════════════════════════
def main():
    print("=" * 65)
    print("  Natural Earth Reverse Geocoding Pipeline")
    print("=" * 65)
    print()

    overall_t0 = time.time()

    from gw_db import connect as gw_connect, Provenance

    # raw sqlite3 for pandas/SQL operations (gw_db wrapper not compatible with pandas)
    raw_sqlite = sqlite3.connect(CHURCHES_DB)
    raw_sqlite.execute("PRAGMA journal_mode=WAL")
    raw_sqlite.execute("PRAGMA busy_timeout=30000")
    raw_sqlite.execute("PRAGMA synchronous=OFF")
    raw_sqlite.execute("PRAGMA cache_size=-8000000")
    raw_sqlite.execute("PRAGMA temp_store=MEMORY")

    # gw_db wrapper for provenance logging
    gw_conn = gw_connect(CHURCHES_DB)

    # Read-only for world_borders.db
    borders_conn = sqlite3.connect(WORLD_BORDERS_DB)

    results = {'per_phase': []}

    try:
        # ── Phase 0: Schema ──
        print("PHASE 0 — Column setup...")
        ensure_geo_columns(raw_sqlite)

        # ── Phase 1: Admin 0 ──
        with Provenance(gw_conn, script_name="spatial_reverse_geocode.py",
                        source="natural_earth", action="enriched",
                        fields="country,continent,region_un,subregion") as prov:
            result = phase1_admin0(raw_sqlite, borders_conn)
            results['per_phase'].append(result)
            if result:
                prov.churches_updated = (result.get('country_filled', 0) +
                                         result.get('continent_filled', 0))
                prov.records_matched = result.get('churches_matched', 0)
                prov.records_attempted = result.get('churches_total', 0)
        gw_conn.commit()  # release lock for next phase

        # ── Phase 2: Admin 1 ──
        with Provenance(gw_conn, script_name="spatial_reverse_geocode.py",
                        source="natural_earth", action="enriched",
                        fields="state") as prov:
            result = phase2_admin1(raw_sqlite, borders_conn)
            results['per_phase'].append(result)
            if result:
                prov.churches_updated = result.get('states_filled', 0)
                prov.records_matched = result.get('states_filled', 0)
                prov.records_attempted = result.get('churches_processed', 0)
        gw_conn.commit()  # release lock for next phase

        # ── Phase 3: US FIPS ──
        with Provenance(gw_conn, script_name="spatial_reverse_geocode.py",
                        source="natural_earth", action="enriched",
                        fields="state (FIPS-derived)") as prov:
            result = phase3_us_fips(raw_sqlite)
            results['per_phase'].append(result)
            if result:
                prov.churches_updated = result.get('states_filled_fips', 0)
                prov.records_matched = result.get('states_filled_fips', 0)
        gw_conn.commit()  # release lock

        # ── Summary ──
        overall_time = time.time() - overall_t0
        print("\n" + "=" * 65)
        print("  SUMMARY")
        print("=" * 65)
        total_updated = sum(
            r.get('country_filled', 0) + r.get('continent_filled', 0) +
            r.get('states_filled', 0) + r.get('states_filled_fips', 0)
            for r in results['per_phase'] if r
        )
        print(f"  Total updates: {total_updated:,}")
        print(f"  Total time: {overall_time:.1f}s ({overall_time / 60:.1f} min)")
        print()

        for r in results['per_phase']:
            if r is None:
                continue
            phase = r.get('phase', '?')
            if phase == 'admin0':
                print(f"  Admin 0: {r['country_filled']:,} countries + {r['continent_filled']:,} "
                      f"continents in {r['duration_seconds']}s")
            elif phase == 'admin1':
                print(f"  Admin 1: {r['states_filled']:,} states in {r['duration_seconds']}s")
                for pc in r.get('per_country', []):
                    if pc['states_filled'] > 0:
                        print(f"    {pc['country']}: {pc['states_filled']:,}")
            elif phase == 'us_fips':
                print(f"  US FIPS: {r['states_filled_fips']:,} states in {r['duration_seconds']}s")

    finally:
        raw_sqlite.close()
        gw_conn.close()
        borders_conn.close()

    print("\n✅ Done.")


if __name__ == '__main__':
    main()
