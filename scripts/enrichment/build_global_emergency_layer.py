#!/usr/bin/env python3
"""
build_global_emergency_layer.py — Global Emergency Service Distance Overlay
============================================================================
Fetches hospitals, clinics, fire stations, and police stations from OpenStreetMap
for ALL countries, then computes nearest-neighbor distances for every church
with GPS coordinates worldwide.

Strategy:
  - Queries Overpass API one amenity type at a time per country
    (individual queries are much more reliable than combined for large countries)
  - For the US, preserves existing data from the database if available
  - Resumable — saves progress after each country
  - Saves CSVs incrementally

Usage:
    python scripts/enrichment/build_global_emergency_layer.py               # Full pipeline
    python scripts/enrichment/build_global_emergency_layer.py --fetch-only  # Just fetch data
    python scripts/enrichment/build_global_emergency_layer.py --from-csv    # Import CSVs + compute
    python scripts/enrichment/build_global_emergency_layer.py --compute-only  # Just compute distances
"""

import sys
import os
import json
import csv
import io
import time
import math
import urllib.request
import urllib.parse
import urllib.error
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
from scipy.spatial import cKDTree

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
DATA_DIR = PROJECT_ROOT / 'data' / 'osm'
DATA_DIR.mkdir(parents=True, exist_ok=True)
PROGRESS_FILE = DATA_DIR / 'global_emergency_progress.json'
ALL_FACILITIES_CSV = DATA_DIR / 'global_healthcare_facilities.csv'
ALL_STATIONS_CSV = DATA_DIR / 'global_emergency_stations.csv'

# Countries ordered by church count (ASCENDING) — process small countries first
# for rapid progress. Large countries at the end may need retries.
# US is excluded because we already have its data from existing DB tables.
COUNTRIES = [
    'CC','IO','PM','PN','SJ','TK','CX','NU','TF','GS','YT','GF','NF',
    'NR','GI','BQ','AQ','DJ','FK','MS','TV','BL','VA','EH','SH','GP',
    'MC','MF','PW','AI','MH','MQ','CK','SM','RE','ST','GQ','AX','WF',
    'GL','KI','TC','TJ','GM','GW','SC','GD','VG','LI','AS','SX','CF',
    'DM','SB','MP','MV','GG','CW','FM','FO','KY','ER','AW','VC','TO',
    'BI','KN','JE','AG','NC','GA','MO','KG','AD','BM','SZ','VI','KM',
    'CG','VU','MR','BF','QA','GU','IM','TD','PG','LC','OM','BN','CV',
    'MN','SR','GN','AM','PF','SO','MD','XK','BW','MW','KW','BB','FJ',
    'TL','ME','AO','BZ','NE','LS','SS','KP','IS','GY','MT','WS','BS',
    'NA','LU','SL','MU','BT','LR','RW','ZW','AE','EE','TT','CY','ML',
    'AZ','AL','BH','KZ','BJ','ZM','SN','TM','LV','JM','UY','PS','SG',
    'JO','UG','CM','LB','CU','MK','TG','PA','LT','MZ','MG','SD','GE',
    'TN','ET','BA','SY','HT','IL','LY','UZ','NI','SV','TZ','BG','GH',
    'CI','DO','BY','MA','HN','BO','PY','KE','FI','IQ','PR','RS','HR',
    'HK','EG','KH','VE','SI','NO','GT','NZ','CR','IE','LA','GR','DK',
    'PE','CL','NP','CD','EC','CH','IR','SK','RO','HU','LK','SE','CO',
    'BE','VN','DZ','PK','NL','AT','CZ','AR','PT','ZA','BD','MY','KR',
    'YE','NG','AU','MM','UA','PL','RU','TW','PH','ES','TR','MX','SA',
    'TH','IT','FR','CN','CA','GB','DE','JP','ID','BR','IN',
]

AMENITIES = ['hospital', 'clinic', 'fire_station', 'police']
OVERPASS = 'https://overpass-api.de/api/interpreter'


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
# PHASE 1: Fetch
# ══════════════════════════════════════════════════════════════════════════

def query_amenity(country_code, amenity):
    """Query Overpass for a single amenity type in a country.
    Returns list of (lat, lon, amenity, name) or None on failure."""
    query = (
        f'[out:csv(::lat,::lon,name,amenity;true;"|")][timeout:300][maxsize:1500000000];'
        f'area["ISO3166-1"="{country_code}"]->.s;'
        f'(node["amenity"="{amenity}"](area.s);'
        f' way["amenity"="{amenity}"](area.s););'
        f'out center;'
    )
    data = urllib.parse.urlencode({'data': query}).encode()

    for attempt in range(5):
        try:
            req = urllib.request.Request(
                OVERPASS, data=data,
                headers={'User-Agent': 'GRID/1.0 (global emergency overlay)'}
            )
            with urllib.request.urlopen(req, timeout=300) as r:
                text = r.read().decode('utf-8')
            results = []
            reader = csv.reader(io.StringIO(text), delimiter='|')
            next(reader, None)
            for row in reader:
                if len(row) >= 3:
                    try:
                        lat, lon = float(row[0]), float(row[1])
                        name = row[2].strip() if len(row) > 2 else ''
                        a = row[3].strip() if len(row) > 3 else amenity
                        results.append((lat, lon, a, name))
                    except (ValueError, IndexError):
                        continue
            return results

        except urllib.error.HTTPError as e:
            if attempt >= 4:
                return None
            wait = [10, 20, 40, 80][attempt]
            if e.code in (429, 504):
                wait = [20, 40, 80, 120][attempt]
            sys.stderr.write(f'\r  {country_code}.{amenity}: HTTP {e.code}, wait {wait}s ({attempt+1}/5)')
            sys.stderr.flush()
            time.sleep(wait)
        except Exception as e:
            if attempt >= 4:
                return None
            time.sleep(10)

    return None


def load_progress():
    if PROGRESS_FILE.exists():
        with open(PROGRESS_FILE, 'r') as f:
            return json.load(f)
    return {'completed': {}, 'failed': [], 'status': 'idle', 'type_counts': {}}


def save_progress(progress):
    with open(PROGRESS_FILE, 'w') as f:
        json.dump(progress, f, indent=2)


def _save_csvs(facilities, stations):
    with open(ALL_FACILITIES_CSV, 'w', newline='', encoding='utf-8') as f:
        w = csv.writer(f)
        w.writerow(['lat', 'lon', 'facility_type', 'name', 'country'])
        for row in facilities:
            w.writerow(row)
    with open(ALL_STATIONS_CSV, 'w', newline='', encoding='utf-8') as f:
        w = csv.writer(f)
        w.writerow(['lat', 'lon', 'station_type', 'name', 'country'])
        for row in stations:
            w.writerow(row)


def extract_existing_us_data(db):
    """Extract existing US healthcare and emergency data from the database
    (from previous build_security_layer.py and build_healthcare_layer.py runs)
    so we don't need to re-fetch the US."""
    facilities = []
    stations = []
    try:
        rows = db.execute("SELECT latitude, longitude, facility_type, name FROM healthcare_facilities").fetchall()
        for r in rows:
            facilities.append((float(r[0]), float(r[1]), r[2], r[3] or '', 'US'))
        print(f'  Extracted {len(facilities):,} existing US healthcare facilities from DB')
    except Exception:
        print('  No existing healthcare_facilities table found')

    try:
        rows = db.execute("SELECT latitude, longitude, station_type, name FROM emergency_stations").fetchall()
        for r in rows:
            stations.append((float(r[0]), float(r[1]), r[2], r[3] or '', 'US'))
        print(f'  Extracted {len(stations):,} existing US emergency stations from DB')
    except Exception:
        print('  No existing emergency_stations table found')

    return facilities, stations


def fetch_all():
    """Fetch global emergency facilities, one amenity type at a time per country."""
    progress = load_progress()
    completed = progress.get('completed', {})  # country -> list of completed amenities
    failed = set(progress.get('failed', []))

    all_facilities = []
    all_stations = []

    # Load existing CSV data
    if ALL_FACILITIES_CSV.exists():
        with open(ALL_FACILITIES_CSV, 'r', encoding='utf-8') as f:
            for row in csv.DictReader(f):
                all_facilities.append((
                    float(row['lat']), float(row['lon']),
                    row['facility_type'], row.get('name', ''),
                    row.get('country', '')
                ))
        print(f'  Loaded {len(all_facilities):,} previously fetched healthcare facilities')

    if ALL_STATIONS_CSV.exists():
        with open(ALL_STATIONS_CSV, 'r', encoding='utf-8') as f:
            for row in csv.DictReader(f):
                all_stations.append((
                    float(row['lat']), float(row['lon']),
                    row['station_type'], row.get('name', ''),
                    row.get('country', '')
                ))
        print(f'  Loaded {len(all_stations):,} previously fetched emergency stations')

    print(f'\n{"="*60}')
    print(f'  PHASE 1: Fetching global emergency facilities')
    print(f'{"="*60}')
    print(f'  Countries: {len(COUNTRIES)}')
    print(f'  Amenity types per country: {len(AMENITIES)}')
    print(f'  Total queries: {len(COUNTRIES) * len(AMENITIES)}')
    print(f'  Already have data for countries: {len(completed)}')

    # Extract existing US data
    us_facilities_added = False
    us_stations_added = False

    t0 = time.time()
    t_last_save = time.time()
    consecutive_errors = 0
    total_fetched = 0

    for i, country in enumerate(COUNTRIES):
        # Skip if all amenities already completed for this country
        country_done = completed.get(country, [])
        if len(country_done) >= len(AMENITIES):
            continue

        country_facilities = 0
        country_stations = 0
        country_amenities_done = list(country_done)

        for amenity in AMENITIES:
            if amenity in country_done:
                continue

            results = query_amenity(country, amenity)

            if results is None:
                failed.add(country)
                consecutive_errors += 1
                sys.stderr.write(f'\n  {country}.{amenity}: FAILED\n')
                if consecutive_errors >= 3:
                    sys.stderr.write('  Cooling down 60s...')
                    sys.stderr.flush()
                    time.sleep(60)
                    consecutive_errors = 0
                else:
                    time.sleep(20)
                continue

            consecutive_errors = 0

            for lat, lon, a, name in results:
                if a in ('hospital', 'clinic'):
                    all_facilities.append((lat, lon, a, name, country))
                    country_facilities += 1
                elif a in ('fire_station', 'police'):
                    all_stations.append((lat, lon, a, name, country))
                    country_stations += 1

            country_amenities_done.append(amenity)
            total_fetched += len(results)

            sys.stderr.write(f'\r  {country}.{amenity}: {len(results):,} results')
            sys.stderr.flush()

            # Rate limiting between queries
            time.sleep(5)

        # Mark country as processed
        completed[str(country)] = country_amenities_done
        progress['completed'] = completed
        progress['failed'] = list(failed)
        save_progress(progress)

        # Save CSVs every 5 countries or 5 minutes
        elapsed_since_save = time.time() - t_last_save
        if len(completed) % 5 == 0 or elapsed_since_save > 300:
            _save_csvs(all_facilities, all_stations)
            t_last_save = time.time()

        # Progress
        elapsed = time.time() - t0
        done = len(completed) + len(failed)
        rate = done / elapsed if elapsed > 0 else 0
        remaining = len(COUNTRIES) - done
        eta = f'{remaining/rate/60:.0f}m' if rate > 0 else '?'
        print(f'\n  {country}: +{country_facilities:,} health +{country_stations:,} emergency '
              f'[{done}/{len(COUNTRIES)}] {elapsed/60:.0f}m, ETA {eta}')

    # Final save
    _save_csvs(all_facilities, all_stations)

    elapsed = time.time() - t0
    print(f'\n  Fetch complete in {elapsed/60:.1f} minutes')
    print(f'  Total fetched: {total_fetched:,} facilities/stations')

    h = sum(1 for f in all_facilities if f[2] == 'hospital')
    c = sum(1 for f in all_facilities if f[2] == 'clinic')
    f_cnt = sum(1 for s in all_stations if s[2] == 'fire_station')
    p = sum(1 for s in all_stations if s[2] == 'police')
    print(f'  Hospitals: {h:,}  Clinics: {c:,}  Fire: {f_cnt:,}  Police: {p:,}')

    progress['status'] = 'fetch_complete'
    progress['fetched_at'] = datetime.now(timezone.utc).isoformat()
    save_progress(progress)

    return all_facilities, all_stations


# ══════════════════════════════════════════════════════════════════════════
# PHASE 2: Import into DB
# ══════════════════════════════════════════════════════════════════════════

def import_into_db(db, facilities, stations):
    print(f'\n{"="*60}')
    print(f'  PHASE 2: Importing into database')
    print(f'{"="*60}')

    # healthcare_facilities
    print(f'\n  --- Healthcare facilities ({len(facilities):,}) ---')
    db.execute('DROP TABLE IF EXISTS healthcare_facilities')
    db.execute('DROP TABLE IF EXISTS healthcare_facilities_rtree')
    db.execute('''
        CREATE TABLE healthcare_facilities (
            id INTEGER PRIMARY KEY,
            latitude REAL NOT NULL,
            longitude REAL NOT NULL,
            facility_type TEXT NOT NULL CHECK(facility_type IN ('hospital', 'clinic')),
            name TEXT,
            country TEXT
        )
    ''')
    db.execute('''
        CREATE VIRTUAL TABLE IF NOT EXISTS healthcare_facilities_rtree
        USING rtree(id, min_lat, max_lat, min_lon, max_lon)
    ''')

    CHUNK = 500
    total = len(facilities)
    for i in range(0, total, CHUNK):
        chunk = facilities[i:i + CHUNK]
        db.executemany(
            'INSERT INTO healthcare_facilities (latitude, longitude, facility_type, name, country) VALUES (?,?,?,?,?)',
            [(lat, lon, ftype, name, c) for lat, lon, ftype, name, c in chunk]
        )
        db.commit()
        progress_bar(min(i + CHUNK, total), total, 'Importing healthcare')

    print(f'\n  Inserted {total:,} healthcare facilities')
    _build_rtree(db, 'healthcare_facilities')
    h = db.execute("SELECT COUNT(*) FROM healthcare_facilities WHERE facility_type='hospital'").fetchone()[0]
    c = db.execute("SELECT COUNT(*) FROM healthcare_facilities WHERE facility_type='clinic'").fetchone()[0]
    print(f'  Verified: {h:,} hospitals, {c:,} clinics')

    # emergency_stations
    print(f'\n  --- Emergency stations ({len(stations):,}) ---')
    db.execute('DROP TABLE IF EXISTS emergency_stations')
    db.execute('DROP TABLE IF EXISTS emergency_stations_rtree')
    db.execute('''
        CREATE TABLE emergency_stations (
            id INTEGER PRIMARY KEY,
            latitude REAL NOT NULL,
            longitude REAL NOT NULL,
            station_type TEXT NOT NULL CHECK(station_type IN ('fire_station', 'police')),
            name TEXT,
            country TEXT
        )
    ''')
    db.execute('''
        CREATE VIRTUAL TABLE IF NOT EXISTS emergency_stations_rtree
        USING rtree(id, min_lat, max_lat, min_lon, max_lon)
    ''')

    total = len(stations)
    for i in range(0, total, CHUNK):
        chunk = stations[i:i + CHUNK]
        db.executemany(
            'INSERT INTO emergency_stations (latitude, longitude, station_type, name, country) VALUES (?,?,?,?,?)',
            [(lat, lon, stype, name, c) for lat, lon, stype, name, c in chunk]
        )
        db.commit()
        progress_bar(min(i + CHUNK, total), total, 'Importing emergency')

    print(f'\n  Inserted {total:,} emergency stations')
    _build_rtree(db, 'emergency_stations')
    f_cnt = db.execute("SELECT COUNT(*) FROM emergency_stations WHERE station_type='fire_station'").fetchone()[0]
    p = db.execute("SELECT COUNT(*) FROM emergency_stations WHERE station_type='police'").fetchone()[0]
    print(f'  Verified: {f_cnt:,} fire, {p:,} police')


def _build_rtree(db, table_name):
    eps = 0.000001
    cur = db.execute(f'SELECT id, latitude, longitude FROM {table_name}')
    data = [(row[0], row[1]-eps, row[1]+eps, row[2]-eps, row[2]+eps) for row in cur]
    rtree_name = f'{table_name}_rtree'
    for i in range(0, len(data), 500):
        db.executemany(f'INSERT INTO {rtree_name} VALUES (?,?,?,?,?)', data[i:i+500])
    db.commit()
    print(f'  R-tree: {len(data):,} entries')


# ══════════════════════════════════════════════════════════════════════════
# PHASE 3: Compute nearest-neighbor distances
# ══════════════════════════════════════════════════════════════════════════

def latlon_to_xyz(coords):
    lat_rad = np.radians(coords[:, 0])
    lon_rad = np.radians(coords[:, 1])
    x = np.cos(lat_rad) * np.cos(lon_rad)
    y = np.cos(lat_rad) * np.sin(lon_rad)
    z = np.sin(lat_rad)
    return np.column_stack([x, y, z])


def chord_to_km(chord_dist):
    return 2 * 6371.0 * np.arcsin(np.clip(chord_dist / 2.0, -1.0, 1.0))


def compute_nearest_distances(db):
    print(f'\n{"="*60}')
    print(f'  PHASE 3: Computing nearest distances')
    print(f'{"="*60}')

    for col, col_type in [
        ('nearest_hospital_km', 'REAL'), ('nearest_clinic_km', 'REAL'),
        ('nearest_fire_km', 'REAL'), ('nearest_police_km', 'REAL'),
        ('healthcare_updated', 'TEXT'), ('security_updated', 'TEXT'),
    ]:
        try:
            db.execute(f'ALTER TABLE churches ADD COLUMN {col} {col_type}')
            print(f'  Added column: {col}')
        except Exception:
            pass

    print('  Loading churches...')
    rows = db.execute("""
        SELECT rowid, latitude, longitude FROM churches
        WHERE latitude IS NOT NULL AND latitude != ''
          AND longitude IS NOT NULL AND longitude != ''
    """).fetchall()
    churches = []
    for r in rows:
        try:
            lat, lon = float(r[1]), float(r[2])
            if -90 <= lat <= 90 and -180 <= lon <= 180:
                churches.append((r[0], lat, lon))
        except (ValueError, TypeError):
            continue
    total = len(churches)
    print(f'  Churches with GPS: {total:,}')
    if total == 0:
        print('  No churches to process.')
        return

    print('  Loading facilities...')
    facilities = db.execute(
        'SELECT id, latitude, longitude, facility_type FROM healthcare_facilities'
    ).fetchall()
    hospital_coords = np.array([(float(f[1]), float(f[2])) for f in facilities if f[3] == 'hospital'])
    clinic_coords = np.array([(float(f[1]), float(f[2])) for f in facilities if f[3] == 'clinic'])

    stations = db.execute(
        'SELECT id, latitude, longitude, station_type FROM emergency_stations'
    ).fetchall()
    fire_coords = np.array([(float(s[1]), float(s[2])) for s in stations if s[3] == 'fire_station'])
    police_coords = np.array([(float(s[1]), float(s[2])) for s in stations if s[3] == 'police'])

    print(f'  Hospitals: {len(hospital_coords):,}  Clinics: {len(clinic_coords):,}')
    print(f'  Fire: {len(fire_coords):,}  Police: {len(police_coords):,}')

    print('  Building KD-trees...')
    t0 = time.time()
    hospital_tree = cKDTree(latlon_to_xyz(hospital_coords)) if len(hospital_coords) > 0 else None
    clinic_tree = cKDTree(latlon_to_xyz(clinic_coords)) if len(clinic_coords) > 0 else None
    fire_tree = cKDTree(latlon_to_xyz(fire_coords)) if len(fire_coords) > 0 else None
    police_tree = cKDTree(latlon_to_xyz(police_coords)) if len(police_coords) > 0 else None
    print(f'  Built in {time.time()-t0:.1f}s')

    church_ids = [c[0] for c in churches]
    church_coords = np.array([(c[1], c[2]) for c in churches])
    church_xyz = latlon_to_xyz(church_coords)

    CHUNK = 5000
    print('  Computing...')
    t0 = time.time()
    for i in range(0, total, CHUNK):
        end = min(i + CHUNK, total)
        chunk_xyz = church_xyz[i:end]
        chunk_ids = church_ids[i:end]

        for tree, col in [(hospital_tree, 'nearest_hospital_km'),
                          (clinic_tree, 'nearest_clinic_km'),
                          (fire_tree, 'nearest_fire_km'),
                          (police_tree, 'nearest_police_km')]:
            if tree is not None:
                chord, _ = tree.query(chunk_xyz, k=1)
                km = chord_to_km(chord)
                batch = [(round(float(d), 4), int(cid))
                         for d, cid in zip(km, chunk_ids) if not np.isnan(d)]
                if batch:
                    db.executemany(f'UPDATE churches SET {col}=? WHERE rowid=?', batch)

        db.commit()
        elapsed = time.time() - t0
        rate = end / elapsed if elapsed > 0 else 0
        progress_bar(end, total, f'Computing ({rate:.0f}/s)')

    now = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
    db.execute("""
        UPDATE churches SET healthcare_updated=?, security_updated=?
        WHERE latitude IS NOT NULL AND latitude != ''
          AND longitude IS NOT NULL AND longitude != ''
    """, (now, now))
    db.commit()

    elapsed = time.time() - t0
    print(f'\n  Computed in {elapsed:.0f}s ({total/elapsed:.0f} churches/s)')


# ══════════════════════════════════════════════════════════════════════════
# PHASE 4: Provenance
# ══════════════════════════════════════════════════════════════════════════

def log_provenance(db, facilities_count, stations_count, churches_updated):
    try:
        h = db.execute("SELECT COUNT(*) FROM healthcare_facilities WHERE facility_type='hospital'").fetchone()[0]
        c = db.execute("SELECT COUNT(*) FROM healthcare_facilities WHERE facility_type='clinic'").fetchone()[0]
        f = db.execute("SELECT COUNT(*) FROM emergency_stations WHERE station_type='fire_station'").fetchone()[0]
        p = db.execute("SELECT COUNT(*) FROM emergency_stations WHERE station_type='police'").fetchone()[0]
        notes = (f"Global OSM emergency overlay: {facilities_count:,} healthcare ({h:,} hosp, {c:,} clin), "
                 f"{stations_count:,} emergency ({f:,} fire, {p:,} police).")
        db.execute("""
            INSERT INTO provenance_log
                (source, script_name, started_at, completed_at,
                 churches_updated, fields_populated, status, notes)
            VALUES (?,?,?,?,?,?,?,?)
        """, ("osm_global_emergency", "build_global_emergency_layer.py",
              datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'),
              datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'),
              churches_updated,
              "nearest_hospital_km, nearest_clinic_km, nearest_fire_km, nearest_police_km",
              "completed", notes))
        db.commit()
    except Exception as e:
        print(f'  Provenance skipped: {e}')


# ══════════════════════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════════════════════

def main():
    import sqlite3

    args = set(sys.argv[1:])
    fetch_only = '--fetch-only' in args
    compute_only = '--compute-only' in args
    from_csv = '--from-csv' in args or '--import-only' in args

    db_path = str(PROJECT_ROOT / 'churches.db')

    do_fetch = not compute_only and not from_csv
    do_import = not fetch_only and not compute_only
    do_compute = not fetch_only

    facilities = stations = None

    # Phase 1: Fetch
    if do_fetch:
        # First extract existing US data from the DB
        db_temp = sqlite3.connect(db_path)
        existing_us_facilities, existing_us_stations = extract_existing_us_data(db_temp)
        db_temp.close()

        facilities, stations = fetch_all()

        # Merge existing US data (for countries where fetch failed or was skipped)
        if existing_us_facilities:
            # Check if US was fetched; if not, add existing US data
            has_us_facilities = any(f[4] == 'US' for f in facilities)
            if not has_us_facilities:
                facilities.extend(existing_us_facilities)
                print(f'  Added {len(existing_us_facilities):,} existing US healthcare facilities')
            if not any(s[4] == 'US' for s in stations):
                stations.extend(existing_us_stations)
                print(f'  Added {len(existing_us_stations):,} existing US emergency stations')

        if fetch_only:
            _save_csvs(facilities, stations)
            print('\n--fetch-only complete. Data saved to CSV.')
            return

    # Phase 2: Import
    if do_import or from_csv:
        if facilities is None and stations is None:
            print(f'\n{"="*60}')
            print(f'  Loading from CSV files')
            print(f'{"="*60}')
            facilities = []
            stations = []
            if ALL_FACILITIES_CSV.exists():
                with open(ALL_FACILITIES_CSV, 'r', encoding='utf-8') as f:
                    for row in csv.DictReader(f):
                        facilities.append((
                            float(row['lat']), float(row['lon']),
                            row['facility_type'], row.get('name', ''),
                            row.get('country', '')
                        ))
                print(f'  Loaded {len(facilities):,} healthcare facilities from CSV')
            if ALL_STATIONS_CSV.exists():
                with open(ALL_STATIONS_CSV, 'r', encoding='utf-8') as f:
                    for row in csv.DictReader(f):
                        stations.append((
                            float(row['lat']), float(row['lon']),
                            row['station_type'], row.get('name', ''),
                            row.get('country', '')
                        ))
                print(f'  Loaded {len(stations):,} emergency stations from CSV')

        db = sqlite3.connect(db_path)
        import_into_db(db, facilities, stations)
    elif compute_only:
        db = sqlite3.connect(db_path)
    else:
        db = sqlite3.connect(db_path)

    # Phase 3: Compute
    if do_compute:
        compute_nearest_distances(db)

    # Phase 4: Provenance
    if do_compute:
        f_count = db.execute('SELECT COUNT(*) FROM healthcare_facilities').fetchone()[0]
        s_count = db.execute('SELECT COUNT(*) FROM emergency_stations').fetchone()[0]
        updated = db.execute("SELECT COUNT(*) FROM churches WHERE nearest_hospital_km IS NOT NULL").fetchone()[0]
        log_provenance(db, f_count, s_count, updated)

    db.commit()
    try:
        db.execute('PRAGMA wal_checkpoint(TRUNCATE)')
    except Exception:
        pass
    db.close()
    print(f'\n{"="*60}\n  Done!\n{"="*60}')


if __name__ == '__main__':
    main()
