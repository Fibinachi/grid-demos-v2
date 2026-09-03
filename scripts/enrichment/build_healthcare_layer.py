#!/usr/bin/env python3
"""
build_healthcare_layer.py — US Hospital & Clinic Distance Enrichment
=====================================================================
Queries Overpass API for all US hospitals & clinics (state-by-state),
imports them into an R-tree indexed table, then computes nearest-neighbor
distances for every US church with GPS coordinates.

Adds columns to churches table:
  - nearest_hospital_km   (distance to nearest hospital in km)
  - nearest_clinic_km     (distance to nearest clinic in km)
  - healthcare_updated    (timestamp of last healthcare distance computation)

Usage:
    python scripts/enrichment/build_healthcare_layer.py              # Full pipeline
    python scripts/enrichment/build_healthcare_layer.py --compute-only  # Just compute distances
    python scripts/enrichment/build_healthcare_layer.py --fetch-only    # Just fetch+import
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
FACILITIES_CSV = DATA_DIR / 'us_healthcare_facilities.csv'

# US state codes
US_STATES = [
    'AL','AK','AZ','AR','CA','CO','CT','DE','FL','GA',
    'HI','ID','IL','IN','IA','KS','KY','LA','ME','MD',
    'MA','MI','MN','MS','MO','MT','NE','NV','NH','NJ',
    'NM','NY','NC','ND','OH','OK','OR','PA','RI','SC',
    'SD','TN','TX','UT','VT','VA','WA','WV','WI','WY',
    'DC',
]

# ── Progress bar ───────────────────────────────────────────────────────
def progress_bar(current, total, label='', width=40):
    if total == 0:
        return
    pct = current / total
    filled = int(width * pct)
    bar = chr(0x2588) * filled + chr(0x2591) * (width - filled)
    sys.stderr.write(f'\r{label} [{bar}] {current:,}/{total:,} ({pct*100:.1f}%)')
    sys.stderr.flush()
    if current >= total:
        sys.stderr.write('\n')


# ══════════════════════════════════════════════════════════════════════════
# STEP 1: Query Overpass API for all US hospitals & clinics
# ══════════════════════════════════════════════════════════════════════════

def query_overpass_state(state_code, amenity, max_retries=5):
    """
    Query Overpass API for amenity nodes+ways in a state.
    Returns list of (lat, lon, name) tuples.
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
            header = next(reader, None)
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
                wait = min(5 * (2 ** attempt), 120)
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

    return []


def fetch_all_facilities():
    """Fetch all US hospitals and clinics state-by-state via Overpass API."""
    all_facilities = []
    osm_id = 1

    print(f'\n=== Fetching US healthcare facilities from OpenStreetMap ===')
    print(f'  Querying {len(US_STATES)} states/territories via Overpass API...')

    t0 = time.time()
    total_hospital = 0
    total_clinic = 0
    failed_hospital = 0
    failed_clinic = 0

    for i, state in enumerate(US_STATES):
        # Hospitals
        hospitals = query_overpass_state(state, 'hospital')
        if hospitals:
            for lat, lon, name in hospitals:
                all_facilities.append((lat, lon, 'hospital', name, osm_id))
                osm_id += 1
            total_hospital += len(hospitals)
        else:
            failed_hospital += 1

        # Clinics
        clinics = query_overpass_state(state, 'clinic')
        if clinics:
            for lat, lon, name in clinics:
                all_facilities.append((lat, lon, 'clinic', name, osm_id))
                osm_id += 1
            total_clinic += len(clinics)
        else:
            failed_clinic += 1

        progress_bar(i + 1, len(US_STATES),
                    f'Fetching ({total_hospital:,} hospitals, {total_clinic:,} clinics)')

        if i < len(US_STATES) - 1:
            time.sleep(4.0)

    elapsed = time.time() - t0
    print(f'\n  Completed in {elapsed:.0f}s')
    print(f'  Hospitals: {total_hospital:,} (failed: {failed_hospital} states)')
    print(f'  Clinics: {total_clinic:,} (failed: {failed_clinic} states)')
    print(f'  Total: {len(all_facilities):,}')

    return all_facilities


def save_facilities_csv(facilities, csv_path):
    """Save facilities to CSV for backup/reuse."""
    print(f'\nSaving facilities to CSV: {csv_path}')
    with open(csv_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(['lat', 'lon', 'facility_type', 'name', 'osm_id'])
        for lat, lon, ftype, name, osm_id in facilities:
            writer.writerow([lat, lon, ftype, name, osm_id])
    size_kb = csv_path.stat().st_size / 1024
    print(f'  Saved {len(facilities):,} facilities ({size_kb:.0f} KB)')


# ══════════════════════════════════════════════════════════════════════════
# STEP 2: Import facilities into SQLite with R-tree spatial index
# ══════════════════════════════════════════════════════════════════════════

def import_facilities_to_db(facilities_or_csv, db):
    """Import healthcare facilities into database with R-tree index."""
    import csv as csv_mod

    print(f'\n=== Importing healthcare facilities ===')

    # Create tables
    db.execute('DROP TABLE IF EXISTS healthcare_facilities')
    db.execute('DROP TABLE IF EXISTS healthcare_facilities_rtree')
    db.execute('''
        CREATE TABLE healthcare_facilities (
            id INTEGER PRIMARY KEY,
            latitude REAL NOT NULL,
            longitude REAL NOT NULL,
            facility_type TEXT NOT NULL CHECK(facility_type IN ('hospital', 'clinic')),
            name TEXT,
            osm_id INTEGER
        )
    ''')

    db.execute('''
        CREATE VIRTUAL TABLE IF NOT EXISTS healthcare_facilities_rtree
        USING rtree(id, min_lat, max_lat, min_lon, max_lon)
    ''')

    # Load data
    if isinstance(facilities_or_csv, list):
        facilities = facilities_or_csv
    else:
        facilities = []
        with open(facilities_or_csv, 'r', encoding='utf-8') as f:
            reader = csv_mod.DictReader(f)
            for row in reader:
                facilities.append((
                    float(row['lat']), float(row['lon']),
                    row['facility_type'], row.get('name', ''),
                    int(row.get('osm_id', 0))
                ))

    CHUNK = 500
    total = len(facilities)

    for i in range(0, total, CHUNK):
        chunk = facilities[i:i + CHUNK]
        rows = [(lat, lon, ftype, name, osm_id) for lat, lon, ftype, name, osm_id in chunk]
        db.executemany(
            'INSERT INTO healthcare_facilities (latitude, longitude, facility_type, name, osm_id) VALUES (?,?,?,?,?)',
            rows
        )
        progress_bar(min(i + CHUNK, total), total, 'Importing facilities')

    db.commit()
    print(f'\n  Inserted {total:,} facilities')

    # Populate R-tree
    print('  Building R-tree spatial index...')
    cur = db.execute('SELECT id, latitude, longitude FROM healthcare_facilities')
    rtree_data = []
    eps = 0.000001
    for row in cur:
        rtree_data.append((row[0], row[1] - eps, row[1] + eps,
                          row[2] - eps, row[2] + eps))

    for i in range(0, len(rtree_data), CHUNK):
        chunk = rtree_data[i:i + CHUNK]
        db.executemany(
            'INSERT INTO healthcare_facilities_rtree VALUES (?,?,?,?,?)',
            chunk
        )
        progress_bar(min(i + CHUNK, len(rtree_data)), len(rtree_data), 'Building R-tree')

    db.commit()
    print(f'\n  R-tree index built with {len(rtree_data):,} entries')

    hospital_cnt = db.execute(
        "SELECT COUNT(*) FROM healthcare_facilities WHERE facility_type='hospital'"
    ).fetchone()[0]
    clinic_cnt = db.execute(
        "SELECT COUNT(*) FROM healthcare_facilities WHERE facility_type='clinic'"
    ).fetchone()[0]
    rtree_cnt = db.execute(
        'SELECT COUNT(*) FROM healthcare_facilities_rtree'
    ).fetchone()[0]
    print(f'  Verified: {hospital_cnt:,} hospitals, {clinic_cnt:,} clinics, {rtree_cnt:,} rtree entries')


# ══════════════════════════════════════════════════════════════════════════
# STEP 3: Compute nearest-neighbor distances for all US churches
# ══════════════════════════════════════════════════════════════════════════

def compute_nearest_distances(db):
    """For each US church with GPS, find nearest hospital and clinic distances."""
    import math
    import numpy as np
    from scipy.spatial import cKDTree

    print(f'\n=== Computing nearest healthcare facility distances ===')

    # Add columns if they don't exist
    for col, col_type in [
        ('nearest_hospital_km', 'REAL'),
        ('nearest_clinic_km', 'REAL'),
        ('healthcare_updated', 'TEXT'),
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

    # Load all facilities into memory
    facilities = db.execute(
        'SELECT id, latitude, longitude, facility_type FROM healthcare_facilities'
    ).fetchall()

    hospital_coords = np.array([(float(f[1]), float(f[2])) for f in facilities if f[3] == 'hospital'])
    clinic_coords = np.array([(float(f[1]), float(f[2])) for f in facilities if f[3] == 'clinic'])
    print(f'  Loaded {len(hospital_coords):,} hospitals, {len(clinic_coords):,} clinics')

    # Build KD-trees
    def latlon_to_xyz(coords):
        lat_rad = np.radians(coords[:, 0])
        lon_rad = np.radians(coords[:, 1])
        x = np.cos(lat_rad) * np.cos(lon_rad)
        y = np.cos(lat_rad) * np.sin(lon_rad)
        z = np.sin(lat_rad)
        return np.column_stack([x, y, z])

    def chord_to_km(chord_dist):
        return 2 * 6371.0 * np.arcsin(np.clip(chord_dist / 2.0, -1.0, 1.0))

    print('  Building KD-trees...')
    t0 = time.time()
    hospital_tree = cKDTree(latlon_to_xyz(hospital_coords)) if len(hospital_coords) > 0 else None
    clinic_tree = cKDTree(latlon_to_xyz(clinic_coords)) if len(clinic_coords) > 0 else None
    print(f'  KD-trees built in {time.time()-t0:.1f}s')

    # Query nearest neighbor for each church
    print('  Querying nearest neighbors...')
    t0 = time.time()

    CHUNK = 5000
    church_ids = [c[0] for c in churches]
    church_coords = np.array([(c[1], c[2]) for c in churches])
    church_xyz = latlon_to_xyz(church_coords)

    for i in range(0, total, CHUNK):
        end = min(i + CHUNK, total)
        chunk_xyz = church_xyz[i:end]
        chunk_ids = church_ids[i:end]

        # Hospital distances
        if hospital_tree is not None:
            hospital_chord, _ = hospital_tree.query(chunk_xyz, k=1)
            hospital_km = chord_to_km(hospital_chord)
            hospital_batch = [(round(float(d), 4), int(cid))
                             for d, cid in zip(hospital_km, chunk_ids) if not np.isnan(d)]
            if hospital_batch:
                db.executemany('UPDATE churches SET nearest_hospital_km=? WHERE id=?', hospital_batch)

        # Clinic distances
        if clinic_tree is not None:
            clinic_chord, _ = clinic_tree.query(chunk_xyz, k=1)
            clinic_km = chord_to_km(clinic_chord)
            clinic_batch = [(round(float(d), 4), int(cid))
                           for d, cid in zip(clinic_km, chunk_ids) if not np.isnan(d)]
            if clinic_batch:
                db.executemany('UPDATE churches SET nearest_clinic_km=? WHERE id=?', clinic_batch)

        db.commit()
        elapsed = time.time() - t0
        rate = end / elapsed if elapsed > 0 else 0
        progress_bar(end, total, f'Computing distances ({rate:.0f}/s)')

    # Set timestamp
    now = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
    db.execute("UPDATE churches SET healthcare_updated=? WHERE country='US' "
               "AND latitude IS NOT NULL AND longitude IS NOT NULL", (now,))
    db.commit()

    elapsed = time.time() - t0
    print(f'\n  Computed in {elapsed:.0f}s ({total/elapsed:.0f} churches/s)')

    # Summary stats
    stats = db.execute("""
        SELECT
            COUNT(*) as total,
            ROUND(AVG(nearest_hospital_km), 2) as avg_hosp_km,
            ROUND(AVG(nearest_clinic_km), 2) as avg_clinic_km,
            ROUND(MIN(nearest_hospital_km), 4) as min_hosp_km,
            ROUND(MIN(nearest_clinic_km), 4) as min_clinic_km,
            ROUND(MAX(nearest_hospital_km), 1) as max_hosp_km,
            ROUND(MAX(nearest_clinic_km), 1) as max_clinic_km
        FROM churches
        WHERE country='US' AND nearest_hospital_km IS NOT NULL
    """).fetchone()
    print(f'\n  Results for {stats[0]:,} US churches:')
    print(f'    Hospital: avg={stats[1]} km, min={stats[3]} km, max={stats[5]} km')
    print(f'    Clinic:   avg={stats[2]} km, min={stats[4]} km, max={stats[6]} km')


# ══════════════════════════════════════════════════════════════════════════
# STEP 4: Log provenance
# ══════════════════════════════════════════════════════════════════════════

def log_provenance(db, hospital_count, clinic_count, churches_updated):
    db.execute(
        "INSERT INTO provenance_log (source, script_name, started_at, completed_at, "
        "churches_updated, fields_populated, status, notes) VALUES (?,?,?,?,?,?,?,?)",
        (
            "osm_healthcare",
            "build_healthcare_layer.py",
            datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'),
            datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'),
            churches_updated,
            "nearest_hospital_km, nearest_clinic_km, healthcare_updated",
            "completed",
            f"US healthcare facilities: {hospital_count:,} hospitals, {clinic_count:,} clinics "
            f"from OSM Overpass API. {churches_updated:,} churches enriched."
        )
    )
    db.commit()
    print(f'\n  Provenance logged.')


# ══════════════════════════════════════════════════════════════════════════
# Main
# ══════════════════════════════════════════════════════════════════════════

def main():
    import argparse
    import sqlite3

    parser = argparse.ArgumentParser(description='Build healthcare facility proximity layer')
    parser.add_argument('--compute-only', action='store_true',
                       help='Skip fetching, just compute distances from existing table')
    parser.add_argument('--fetch-only', action='store_true',
                       help='Only fetch and import, skip distance computation')
    parser.add_argument('--db', default=str(PROJECT_ROOT / 'churches.db'),
                       help='Path to churches.db')
    args = parser.parse_args()

    db = sqlite3.connect(args.db)
    db.execute("PRAGMA journal_mode=WAL")
    db.execute("PRAGMA busy_timeout=30000")

    if not args.compute_only:
        # Fetch from Overpass
        facilities = fetch_all_facilities()
        if not facilities:
            print('\n  ERROR: No facilities fetched. Check Overpass API connectivity.')
            db.close()
            sys.exit(1)

        # Save CSV backup
        save_facilities_csv(facilities, FACILITIES_CSV)

        # Import to DB
        import_facilities_to_db(facilities, db)
    else:
        print('\n  --compute-only: Skipping fetch, using existing healthcare_facilities table')

    if not args.fetch_only:
        # Compute distances
        compute_nearest_distances(db)

        # Log provenance
        hospital_count = db.execute(
            "SELECT COUNT(*) FROM healthcare_facilities WHERE facility_type='hospital'"
        ).fetchone()[0]
        clinic_count = db.execute(
            "SELECT COUNT(*) FROM healthcare_facilities WHERE facility_type='clinic'"
        ).fetchone()[0]
        churches_updated = db.execute(
            "SELECT COUNT(*) FROM churches WHERE country='US' AND nearest_hospital_km IS NOT NULL"
        ).fetchone()[0]
        log_provenance(db, hospital_count, clinic_count, churches_updated)

    db.close()
    print(f'\n{"="*60}')
    print(f'  Healthcare proximity layer complete.')
    print(f'{"="*60}\n')


if __name__ == '__main__':
    main()
