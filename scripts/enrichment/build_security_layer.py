#!/usr/bin/env python3
"""
build_security_layer.py — US Emergency Station Distance Enrichment
===================================================================
Queries Overpass API for all US fire stations & police stations (state-by-state),
imports them into an R-tree indexed table, then computes nearest-neighbor
distances for every US church with GPS coordinates.

Adds columns to churches table:
  - nearest_fire_km     (distance to nearest fire station in km)
  - nearest_police_km   (distance to nearest police station in km)
  - security_updated     (timestamp of last security distance computation)

Usage:
    python scripts/enrichment/build_security_layer.py [--compute-only]

Examples:
    python scripts/enrichment/build_security_layer.py              # Full pipeline
    python scripts/enrichment/build_security_layer.py --compute-only  # Just compute distances
"""

import sys
import os
import time
import io
import csv
import urllib.request
import urllib.parse
import urllib.error
from datetime import datetime, timezone
from pathlib import Path

# ── Paths ──────────────────────────────────────────────────────────────
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent  # e:\grid
DATA_DIR = PROJECT_ROOT / 'data' / 'osm'
DATA_DIR.mkdir(parents=True, exist_ok=True)
STATIONS_CSV = DATA_DIR / 'us_emergency_stations.csv'

# US state codes
US_STATES = [
    'AL','AK','AZ','AR','CA','CO','CT','DE','FL','GA',
    'HI','ID','IL','IN','IA','KS','KY','LA','ME','MD',
    'MA','MI','MN','MS','MO','MT','NE','NV','NH','NJ',
    'NM','NY','NC','ND','OH','OK','OR','PA','RI','SC',
    'SD','TN','TX','UT','VT','VA','WA','WV','WI','WY',
    'DC',  # District of Columbia
]

# ── Progress bar ───────────────────────────────────────────────────────
def progress_bar(current, total, label='', width=40):
    """Render a progress bar to stderr."""
    if total == 0:
        return
    pct = current / total
    filled = int(width * pct)
    bar = '█' * filled + '░' * (width - filled)
    sys.stderr.write(f'\r{label} [{bar}] {current:,}/{total:,} ({pct*100:.1f}%)')
    sys.stderr.flush()
    if current >= total:
        sys.stderr.write('\n')


# ══════════════════════════════════════════════════════════════════════════
# STEP 1: Query Overpass API for all US fire & police stations
# ══════════════════════════════════════════════════════════════════════════

def query_overpass_state(state_code, amenity, max_retries=5):
    """
    Query Overpass API for amenity nodes+ways in a state.
    Returns list of (lat, lon, name) tuples. Retries with backoff on failure.
    """
    query = (
        f'[out:csv(::lat,::lon,name;true;"|")][timeout:120];'
        f'area["ISO3166-2"="US-{state_code}"]->.s;'
        f'(node["amenity"="{amenity}"](area.s);'
        f'way["amenity"="{amenity}"](area.s););'
        f'out center;'
    )
    data = urllib.parse.urlencode({'data': query}).encode()

    for attempt in range(max_retries):
        try:
            req = urllib.request.Request(
                'https://overpass-api.de/api/interpreter',
                data=data,
                headers={'User-Agent': 'GRID/1.0 (religious infrastructure research)'}
            )
            with urllib.request.urlopen(req, timeout=180) as r:
                text = r.read().decode('utf-8')

            results = []
            reader = csv.reader(io.StringIO(text), delimiter='|')
            header = next(reader, None)  # skip header
            for row in reader:
                if len(row) >= 2:
                    try:
                        lat, lon = float(row[0]), float(row[1])
                        name = row[2].strip() if len(row) > 2 else ''
                        results.append((lat, lon, name))
                    except (ValueError, IndexError):
                        continue
            return results

        except urllib.error.HTTPError as e:
            if e.code == 429:
                wait = min(5 * (2 ** attempt), 120)  # 5, 10, 20, 40, 80, 120
                if attempt < max_retries - 1:
                    time.sleep(wait)
                    continue
            elif e.code == 504:
                wait = min(10 * (2 ** attempt), 180)
                if attempt < max_retries - 1:
                    time.sleep(wait)
                    continue
            print(f'\n  {state_code} {amenity}: HTTP {e.code} (attempt {attempt+1}/{max_retries})')
        except Exception as e:
            if attempt < max_retries - 1:
                time.sleep(5)
                continue
            print(f'\n  {state_code} {amenity}: {e} (attempt {attempt+1}/{max_retries})')

    return []  # All retries exhausted


def fetch_all_stations():
    """Fetch all US fire and police stations state-by-state via Overpass API."""
    all_stations = []  # (lat, lon, station_type, name, osm_id)
    osm_id = 1

    print(f'\n=== Fetching US emergency stations from OpenStreetMap ===')
    print(f'  Querying {len(US_STATES)} states/territories via Overpass API...')
    print(f'  (With retry/backoff, ~3-5s between states)')

    t0 = time.time()
    total_fire = 0
    total_police = 0
    failed_fire = 0
    failed_police = 0
    failed_states = []

    for i, state in enumerate(US_STATES):
        # Fire stations
        fire_stations = query_overpass_state(state, 'fire_station')
        if fire_stations:
            for lat, lon, name in fire_stations:
                all_stations.append((lat, lon, 'fire', name, osm_id))
                osm_id += 1
            total_fire += len(fire_stations)
        else:
            failed_fire += 1

        # Police stations
        police_stations = query_overpass_state(state, 'police')
        if police_stations:
            for lat, lon, name in police_stations:
                all_stations.append((lat, lon, 'police', name, osm_id))
                osm_id += 1
            total_police += len(police_stations)
        else:
            failed_police += 1

        progress_bar(i + 1, len(US_STATES),
                    f'Fetching ({total_fire:,} fire, {total_police:,} police)')

        # Polite pause between states (3-5s to avoid rate limiting)
        if i < len(US_STATES) - 1:
            time.sleep(4.0)

    elapsed = time.time() - t0
    print(f'\n  Completed in {elapsed:.0f}s')
    print(f'  Fire stations: {total_fire:,} (failed: {failed_fire} states)')
    print(f'  Police stations: {total_police:,} (failed: {failed_police} states)')
    print(f'  Total: {len(all_stations):,}')

    return all_stations


def save_stations_csv(stations, csv_path):
    """Save stations to CSV for backup/reuse."""
    print(f'\nSaving stations to CSV: {csv_path}')
    with open(csv_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(['lat', 'lon', 'station_type', 'name', 'osm_id'])
        for lat, lon, stype, name, osm_id in stations:
            writer.writerow([lat, lon, stype, name, osm_id])
    size_kb = csv_path.stat().st_size / 1024
    print(f'  Saved {len(stations):,} stations ({size_kb:.0f} KB)')


# ══════════════════════════════════════════════════════════════════════════
# STEP 3: Import stations into SQLite with R-tree spatial index
# ══════════════════════════════════════════════════════════════════════════

def import_stations_to_db(stations_or_csv, db):
    """Import stations into emergency_stations table with R-tree index."""
    import csv

    print(f'\n=== Importing emergency stations ===')

    # Create tables
    db.execute('DROP TABLE IF EXISTS emergency_stations')
    db.execute('DROP TABLE IF EXISTS emergency_stations_rtree')
    db.execute('''
        CREATE TABLE emergency_stations (
            id INTEGER PRIMARY KEY,
            latitude REAL NOT NULL,
            longitude REAL NOT NULL,
            station_type TEXT NOT NULL CHECK(station_type IN ('fire', 'police')),
            name TEXT,
            osm_id INTEGER
        )
    ''')

    # Create R-tree spatial index
    db.execute('''
        CREATE VIRTUAL TABLE IF NOT EXISTS emergency_stations_rtree
        USING rtree(id, min_lat, max_lat, min_lon, max_lon)
    ''')

    # Import data
    if isinstance(stations_or_csv, list):
        stations = stations_or_csv
    else:
        stations = []
        with open(stations_or_csv, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                stations.append((
                    float(row['lat']), float(row['lon']),
                    row['station_type'], row.get('name', ''),
                    int(row.get('osm_id', 0))
                ))

    CHUNK = 500
    total = len(stations)
    inserted = 0
    spatial_inserts = []

    for i in range(0, total, CHUNK):
        chunk = stations[i:i + CHUNK]
        # Insert into main table
        rows = [(lat, lon, stype, name, osm_id) for lat, lon, stype, name, osm_id in chunk]
        db.executemany(
            'INSERT INTO emergency_stations (latitude, longitude, station_type, name, osm_id) VALUES (?,?,?,?,?)',
            rows
        )
        # Collect for R-tree (id = last_insert_rowid + offset)
        # We need to get the actual IDs; for bulk insert we use a different approach
        progress_bar(min(i + CHUNK, total), total, 'Importing stations')

    db.commit()
    print(f'\n  Inserted {total:,} stations')

    # Populate R-tree (use IDs from 1 to total)
    print('  Building R-tree spatial index...')
    cur = db.execute('SELECT id, latitude, longitude FROM emergency_stations')
    rtree_data = []
    for row in cur:
        # R-tree bounding box: use point with tiny epsilon
        eps = 0.000001  # ~0.1m
        rtree_data.append((row[0], row[1] - eps, row[1] + eps,
                          row[2] - eps, row[2] + eps))

    for i in range(0, len(rtree_data), CHUNK):
        chunk = rtree_data[i:i + CHUNK]
        db.executemany(
            'INSERT INTO emergency_stations_rtree VALUES (?,?,?,?,?)',
            chunk
        )
        progress_bar(min(i + CHUNK, len(rtree_data)), len(rtree_data), 'Building R-tree')

    db.commit()
    print(f'\n  R-tree index built with {len(rtree_data):,} entries')

    # Verify
    fire_cnt = db.execute(
        "SELECT COUNT(*) FROM emergency_stations WHERE station_type='fire'"
    ).fetchone()[0]
    police_cnt = db.execute(
        "SELECT COUNT(*) FROM emergency_stations WHERE station_type='police'"
    ).fetchone()[0]
    rtree_cnt = db.execute(
        'SELECT COUNT(*) FROM emergency_stations_rtree'
    ).fetchone()[0]
    print(f'  Verified: {fire_cnt:,} fire, {police_cnt:,} police, {rtree_cnt:,} rtree entries')


# ══════════════════════════════════════════════════════════════════════════
# STEP 4: Compute nearest-neighbor distances for all US churches
# ══════════════════════════════════════════════════════════════════════════

def compute_nearest_distances(db):
    """For each US church with GPS, find nearest fire and police station distances."""
    import math
    import numpy as np
    from scipy.spatial import cKDTree

    print(f'\n=== Computing nearest emergency station distances ===')

    # Add columns if they don't exist
    for col, col_type in [
        ('nearest_fire_km', 'REAL'),
        ('nearest_police_km', 'REAL'),
        ('security_updated', 'TEXT'),
    ]:
        try:
            db.execute(f'ALTER TABLE churches ADD COLUMN {col} {col_type}')
            print(f'  Added column: {col}')
        except Exception:
            pass

    # Get all US churches with GPS
    rows = db.execute(
        "SELECT id, latitude, longitude FROM churches "
        "WHERE country='US' AND latitude IS NOT NULL AND longitude IS NOT NULL "
        "AND latitude != '' AND longitude != ''"
    ).fetchall()
    # Filter out non-numeric coordinates
    churches = []
    for r in rows:
        try:
            lat, lon = float(r[1]), float(r[2])
            churches.append((r[0], lat, lon))
        except (ValueError, TypeError):
            continue
    total = len(churches)
    print(f'  US churches with GPS: {total:,}')

    if total == 0:
        print('  No churches to process.')
        return

    # Load all stations into memory
    stations = db.execute(
        'SELECT id, latitude, longitude, station_type FROM emergency_stations'
    ).fetchall()

    fire_coords = np.array([(float(s[1]), float(s[2])) for s in stations if s[3] == 'fire'])
    police_coords = np.array([(float(s[1]), float(s[2])) for s in stations if s[3] == 'police'])
    print(f'  Loaded {len(fire_coords):,} fire, {len(police_coords):,} police stations')

    # Build KD-trees (convert lat/lon to 3D cartesian for accurate Haversine via Euclidean)
    def latlon_to_xyz(coords):
        """Convert (lat, lon) in degrees to 3D unit sphere coordinates."""
        lat_rad = np.radians(coords[:, 0])
        lon_rad = np.radians(coords[:, 1])
        x = np.cos(lat_rad) * np.cos(lon_rad)
        y = np.cos(lat_rad) * np.sin(lon_rad)
        z = np.sin(lat_rad)
        return np.column_stack([x, y, z])

    def chord_to_km(chord_dist):
        """Convert chord distance on unit sphere to km (Earth radius = 6371)."""
        # chord = 2*sin(theta/2), so theta = 2*arcsin(chord/2)
        # km = theta * R
        return 2 * 6371.0 * np.arcsin(np.clip(chord_dist / 2.0, -1.0, 1.0))

    print('  Building KD-trees...')
    t0 = time.time()
    fire_tree = cKDTree(latlon_to_xyz(fire_coords)) if len(fire_coords) > 0 else None
    police_tree = cKDTree(latlon_to_xyz(police_coords)) if len(police_coords) > 0 else None
    print(f'  KD-trees built in {time.time()-t0:.1f}s')

    # Query nearest neighbor for each church
    print('  Querying nearest neighbors...')
    t0 = time.time()

    # Process in chunks
    CHUNK = 5000
    church_ids = [c[0] for c in churches]
    church_coords = np.array([(c[1], c[2]) for c in churches])
    church_xyz = latlon_to_xyz(church_coords)

    for i in range(0, total, CHUNK):
        end = min(i + CHUNK, total)
        chunk_xyz = church_xyz[i:end]
        chunk_ids = church_ids[i:end]

        # Fire distances
        if fire_tree is not None:
            fire_chord, _ = fire_tree.query(chunk_xyz, k=1)
            fire_km = chord_to_km(fire_chord)
            fire_batch = [(round(float(d), 4), int(cid))
                         for d, cid in zip(fire_km, chunk_ids) if not np.isnan(d)]
            if fire_batch:
                db.executemany('UPDATE churches SET nearest_fire_km=? WHERE id=?', fire_batch)

        # Police distances
        if police_tree is not None:
            police_chord, _ = police_tree.query(chunk_xyz, k=1)
            police_km = chord_to_km(police_chord)
            police_batch = [(round(float(d), 4), int(cid))
                           for d, cid in zip(police_km, chunk_ids) if not np.isnan(d)]
            if police_batch:
                db.executemany('UPDATE churches SET nearest_police_km=? WHERE id=?', police_batch)

        db.commit()
        elapsed = time.time() - t0
        rate = end / elapsed if elapsed > 0 else 0
        progress_bar(end, total, f'Computing distances ({rate:.0f}/s)')

    # Set timestamp
    ts = datetime.now(timezone.utc).isoformat()
    db.execute(
        "UPDATE churches SET security_updated=? WHERE country='US' AND latitude IS NOT NULL",
        (ts,)
    )
    db.commit()

    elapsed = time.time() - t0
    print(f'\n  Completed in {elapsed:.1f}s ({total / elapsed:.0f} churches/sec)')

    # Stats
    stats = db.execute('''
        SELECT
            COUNT(*) as total,
            ROUND(AVG(nearest_fire_km), 2) as avg_fire_km,
            ROUND(AVG(nearest_police_km), 2) as avg_police_km,
            ROUND(MIN(nearest_fire_km), 4) as min_fire_km,
            ROUND(MIN(nearest_police_km), 4) as min_police_km,
            ROUND(MAX(nearest_fire_km), 1) as max_fire_km,
            ROUND(MAX(nearest_police_km), 1) as max_police_km
        FROM churches
        WHERE country='US' AND nearest_fire_km IS NOT NULL
    ''').fetchone()
    print(f'\n=== US Security Distance Statistics ===')
    print(f'  Churches measured: {stats[0]:,}')
    print(f'  Avg fire distance: {stats[1]} km')
    print(f'  Avg police distance: {stats[2]} km')
    print(f'  Min fire distance: {stats[3]} km')
    print(f'  Min police distance: {stats[4]} km')
    print(f'  Max fire distance: {stats[5]} km')
    print(f'  Max police distance: {stats[6]} km')

    # Percentiles
    for label, col in [('Fire', 'nearest_fire_km'), ('Police', 'nearest_police_km')]:
        for pct in [50, 75, 90, 95, 99]:
            row = db.execute(f'''
                SELECT {col} FROM churches
                WHERE country='US' AND {col} IS NOT NULL
                ORDER BY {col} LIMIT 1 OFFSET
                (SELECT CAST(COUNT(*)*{pct/100.0} AS INT)
                 FROM churches WHERE country='US' AND {col} IS NOT NULL)
            ''').fetchone()
            if row:
                print(f'  {label} P{pct}: {row[0]:.2f} km')


# ══════════════════════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════════════════════

def main():
    import argparse
    parser = argparse.ArgumentParser(description='Build US security distance layer')
    parser.add_argument('--compute-only', action='store_true',
                       help='Only compute distances (skip station fetch)')
    parser.add_argument('--csv-only', action='store_true',
                       help='Only fetch stations and save CSV, skip DB')
    args = parser.parse_args()

    # Add project root to path for gw_db
    sys.path.insert(0, str(PROJECT_ROOT))
    from gw_db import connect, Provenance

    if args.csv_only:
        # Just fetch and save
        stations = fetch_all_stations()
        save_stations_csv(stations, STATIONS_CSV)
        print('\nStations saved to CSV. Done.')
        return

    db = connect()

    with Provenance(db, 'build_security_layer.py', source='osm_overpass',
                    action='enriched',
                    fields='nearest_fire_km,nearest_police_km,security_updated'):

        if not args.compute_only:
            # Step 1: Fetch from Overpass (or load from CSV if exists)
            if STATIONS_CSV.exists():
                print(f'\nLoading stations from cached CSV: {STATIONS_CSV}')
                stations = []
                with open(STATIONS_CSV, 'r', encoding='utf-8') as f:
                    reader = csv.DictReader(f)
                    for row in reader:
                        stations.append((
                            float(row['lat']), float(row['lon']),
                            row['station_type'], row.get('name', ''),
                            int(row.get('osm_id', 0))
                        ))
                print(f'  Loaded {len(stations):,} stations from CSV')
            else:
                stations = fetch_all_stations()
                # Save CSV backup
                save_stations_csv(stations, STATIONS_CSV)

            # Step 2: Import to DB
            import_stations_to_db(stations, db)

        # Step 3: Compute distances
        compute_nearest_distances(db)

    db.close()
    print('\n✅ Security layer complete.')


if __name__ == '__main__':
    main()
