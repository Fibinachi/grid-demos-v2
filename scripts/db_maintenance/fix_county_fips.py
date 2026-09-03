"""
Fix bad county_fips_5 records using spatial join against US Census county boundaries.
Downloads county shapefile from Census Bureau, then point-in-polygon matches all
records where county_fips_5 state prefix doesn't match the record's state.

Uses the gw_db helper and provenance logging.
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import sqlite3
import urllib.request
import tempfile
import zipfile
import io
import json
from collections import defaultdict

import geopandas as gpd
import pandas as pd
from shapely.geometry import Point
from shapely import STRtree

from gw_db import connect as get_db

DB_PATH = Path(__file__).resolve().parents[2] / "churches.db"
CENSUS_URL = "https://www2.census.gov/geo/tiger/GENZ2023/shp/cb_2023_us_county_500k.zip"
CHUNK_SIZE = 500

# Standard state FIPS (same as audit)
STATE_FIPS = {
    'AL': '01', 'AK': '02', 'AZ': '04', 'AR': '05', 'CA': '06',
    'CO': '08', 'CT': '09', 'DE': '10', 'DC': '11', 'FL': '12',
    'GA': '13', 'HI': '15', 'ID': '16', 'IL': '17', 'IN': '18',
    'IA': '19', 'KS': '20', 'KY': '21', 'LA': '22', 'ME': '23',
    'MD': '24', 'MA': '25', 'MI': '26', 'MN': '27', 'MS': '28',
    'MO': '29', 'MT': '30', 'NE': '31', 'NV': '32', 'NH': '33',
    'NJ': '34', 'NM': '35', 'NY': '36', 'NC': '37', 'ND': '38',
    'OH': '39', 'OK': '40', 'OR': '41', 'PA': '42', 'RI': '44',
    'SC': '45', 'SD': '46', 'TN': '47', 'TX': '48', 'UT': '49',
    'VT': '50', 'VA': '51', 'WA': '53', 'WV': '54', 'WI': '55',
    'WY': '56',
    'Alabama': '01', 'Alaska': '02', 'Arizona': '04', 'Arkansas': '05',
    'California': '06', 'Colorado': '08', 'Connecticut': '09',
    'Delaware': '10', 'Florida': '12', 'Georgia': '13', 'Hawaii': '15',
    'Idaho': '16', 'Illinois': '17', 'Indiana': '18', 'Iowa': '19',
    'Kansas': '20', 'Kentucky': '21', 'Louisiana': '22', 'Maine': '23',
    'Maryland': '24', 'Massachusetts': '25', 'Michigan': '26',
    'Minnesota': '27', 'Mississippi': '28', 'Missouri': '29',
    'Montana': '30', 'Nebraska': '31', 'Nevada': '32',
    'New Hampshire': '33', 'New Jersey': '34', 'New Mexico': '35',
    'New York': '36', 'North Carolina': '37', 'North Dakota': '38',
    'Ohio': '39', 'Oklahoma': '40', 'Oregon': '41', 'Pennsylvania': '42',
    'Rhode Island': '44', 'South Carolina': '45', 'South Dakota': '46',
    'Tennessee': '47', 'Texas': '48', 'Utah': '49', 'Vermont': '50',
    'Virginia': '51', 'Washington': '53', 'West Virginia': '54',
    'Wisconsin': '55', 'Wyoming': '56',
}


def download_counties():
    """Download county shapefile, return GeoDataFrame with GEOID and geometry."""
    print("Downloading US county boundaries (Census TIGER 2023)...")
    with urllib.request.urlopen(CENSUS_URL) as resp:
        data = resp.read()
    print(f"   {len(data)/1024/1024:.1f} MB downloaded")

    with zipfile.ZipFile(io.BytesIO(data)) as zf:
        # Find the .shp file
        shp_name = [n for n in zf.namelist() if n.endswith('.shp')][0]
        print(f"   Extracting {shp_name}...")
        with tempfile.TemporaryDirectory() as tmp:
            zf.extractall(tmp)
            gdf = gpd.read_file(Path(tmp) / shp_name)

    gdf = gdf[['GEOID', 'NAME', 'geometry']].copy()
    gdf['GEOID'] = gdf['GEOID'].astype(str).str.zfill(5)
    print(f"   {len(gdf):,} counties loaded")
    return gdf


def get_bad_records(db_path: Path):
    """Get all records with bad county_fips_5 that have GPS coordinates."""
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row

    # Build query for all bad records: state prefix doesn't match FIPS prefix
    conditions = []
    for state, prefix in STATE_FIPS.items():
        conditions.append(f"(state = '{state}' AND county_fips_5 NOT LIKE '{prefix}%')")

    query = f"""
        SELECT id, name, state, county_fips_5, latitude, longitude
        FROM churches
        WHERE country = 'US'
          AND state IS NOT NULL AND state != ''
          AND county_fips_5 IS NOT NULL AND county_fips_5 != ''
          AND latitude IS NOT NULL AND longitude IS NOT NULL
          AND ({' OR '.join(conditions)})
    """
    records = []
    for r in conn.execute(query):
        records.append(dict(r))
    conn.close()
    return records


def spatial_fix(records: list, counties: gpd.GeoDataFrame):
    """Spatial join: for each bad record, find containing county. Returns {id: new_fips}."""
    print(f"\nBuilding spatial index for {len(counties):,} counties...")
    tree = STRtree(counties.geometry.values)
    county_geoids = counties['GEOID'].values
    county_geoms = counties.geometry.values

    print(f"Point-in-polygon matching {len(records):,} records...")
    fixes = {}
    no_match = 0
    multi_match = 0

    for i, rec in enumerate(records):
        if i % 1000 == 0:
            print(f"   {i}/{len(records)}...")

        point = Point(rec['longitude'], rec['latitude'])
        # Find candidate counties via spatial index
        indices = tree.query(point, predicate='intersects')

        if len(indices) == 0:
            no_match += 1
            continue
        elif len(indices) > 1:
            # Pick the one whose state prefix matches (if available)
            best = None
            state_fips = STATE_FIPS.get(rec['state'], '')
            for idx in indices:
                geoid = county_geoids[idx]
                if state_fips and geoid.startswith(state_fips):
                    best = geoid
                    break
            if best is None:
                best = county_geoids[indices[0]]  # fallback to first
                multi_match += 1
            fixes[rec['id']] = best
        else:
            fixes[rec['id']] = county_geoids[indices[0]]

    print(f"   Matched: {len(fixes):,}")
    print(f"   No spatial match: {no_match}")
    print(f"   Multiple candidates (used first): {multi_match}")
    return fixes


def apply_fixes(fixes: dict, records: list):
    """Update churches with corrected county_fips_5 AND state using spatial join results.
    Derives correct state from the county FIPS prefix."""
    db = get_db()
    cur = db.cursor()

    rec_map = {r['id']: r for r in records}

    # Build FIPS-to-state reverse map (2-digit prefix -> state abbreviation)
    fips_to_state = {}
    for state, prefix in STATE_FIPS.items():
        if len(state) == 2:  # Only use abbreviations
            fips_to_state[prefix] = state

    updated_fips = 0
    updated_state = 0
    batch_fips = []
    batch_state = []

    for church_id, new_fips in fixes.items():
        old_rec = rec_map.get(church_id)
        if not old_rec:
            continue

        new_state = fips_to_state.get(new_fips[:2], old_rec['state'])

        old_fips = old_rec['county_fips_5']
        old_state = old_rec['state']

        if old_fips != new_fips:
            batch_fips.append((new_fips, church_id))
            updated_fips += 1

        if old_state != new_state and len(new_state) == 2:
            batch_state.append((new_state, church_id))
            updated_state += 1

    print(f"\nFixing {updated_fips:,} FIPS values and {updated_state:,} state values...")

    # Update FIPS
    for i in range(0, len(batch_fips), CHUNK_SIZE):
        chunk = batch_fips[i:i + CHUNK_SIZE]
        cur.executemany("UPDATE churches SET county_fips_5 = ? WHERE id = ?", chunk)
        db.commit()
    if updated_fips:
        print(f"   {updated_fips:,} county_fips_5 corrected")

    # Update state
    for i in range(0, len(batch_state), CHUNK_SIZE):
        chunk = batch_state[i:i + CHUNK_SIZE]
        cur.executemany("UPDATE churches SET state = ? WHERE id = ?", chunk)
        db.commit()
    if updated_state:
        print(f"   {updated_state:,} state values corrected")

    # Log provenance
    total = updated_fips + updated_state
    cur.execute("""
        INSERT INTO provenance_log (source, script_name, churches_updated, status)
        VALUES (?, ?, ?, ?)
    """, ('spatial_join_fix', 'fix_county_fips.py', total, 'completed'))
    db.commit()

    # Log enrichment changes for state fixes
    for church_id, new_fips in fixes.items():
        old_rec = rec_map.get(church_id)
        if not old_rec:
            continue
        new_state = fips_to_state.get(new_fips[:2], old_rec['state'])
        if old_rec['state'] != new_state and len(new_state) == 2:
            cur.execute("""
                INSERT INTO enrichment_change_log (church_id, field_name, old_value, new_value, change_source)
                VALUES (?, 'state', ?, ?, 'fix_county_fips_spatial')
            """, (church_id, old_rec['state'], new_state))
        if old_rec['county_fips_5'] != new_fips:
            cur.execute("""
                INSERT INTO enrichment_change_log (church_id, field_name, old_value, new_value, change_source)
                VALUES (?, 'county_fips_5', ?, ?, 'fix_county_fips_spatial')
            """, (church_id, old_rec['county_fips_5'], new_fips))

    db.commit()
    print(f"   Provenance + enrichment log entries written")
    db.close()
    return updated_fips + updated_state


def main():
    print("=" * 60)
    print("COUNTY FIPS SPATIAL FIX")
    print("=" * 60)

    # 1. Download counties
    counties = download_counties()

    # 2. Find bad records
    print("\nFinding records with bad county_fips_5...")
    records = get_bad_records(DB_PATH)
    print(f"   {len(records):,} bad records with GPS coordinates")

    if not records:
        print("   Nothing to fix!")
        return

    # Show breakdown
    by_state = defaultdict(int)
    for r in records:
        by_state[r['state']] += 1
    print("   By state:")
    for state, n in sorted(by_state.items(), key=lambda x: -x[1]):
        print(f"     {state}: {n:,}")

    # 3. Spatial fix
    fixes = spatial_fix(records, counties)

    # 4. Apply
    updated = apply_fixes(fixes, records)

    print(f"\n{'=' * 60}")
    print(f"DONE: {updated:,} county_fips_5 values corrected")
    print(f"{'=' * 60}")


if __name__ == '__main__':
    main()
