#!/usr/bin/env python3
"""
elevate_churches.py — Fetch elevation for churches from Open-Meteo
======================================================================
Adds an `elevation_m` column to the churches table and populates it
using the free Open-Meteo Elevation API (no API key needed).

Usage:
    python scripts/enrichment/elevate_churches.py                          # Fill all missing
    python scripts/enrichment/elevate_churches.py --state KY              # Just one state
    python scripts/enrichment/elevate_churches.py --bbox "37,-86,39,-84" # Just one area
    python scripts/enrichment/elevate_churches.py --check-only            # Just check coverage
"""

import sys, os, json, time, urllib.request, sqlite3
from pathlib import Path
from datetime import datetime

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
DB_PATH = PROJECT_ROOT / 'churches.db'
BATCH_SIZE = 100  # Open-Meteo batch limit
SLEEP_BETWEEN = 2.5  # seconds between batches


def add_column(db):
    """Add elevation_m column if it doesn't exist."""
    try:
        db.execute("ALTER TABLE churches ADD COLUMN elevation_m REAL")
        print('  Added column: elevation_m')
    except Exception:
        pass  # already exists


def get_churches_to_fill(db, state=None, bbox=None):
    """Get churches with GPS that need elevation."""
    where = ["latitude IS NOT NULL", "latitude != ''",
             "longitude IS NOT NULL", "longitude != ''",
             "elevation_m IS NULL"]
    params = []
    if state:
        where.append("country='US' AND state=?")
        params.append(state)
    if bbox:
        min_lat, min_lon, max_lat, max_lon = bbox
        where.append("latitude BETWEEN ? AND ?")
        where.append("longitude BETWEEN ? AND ?")
        params.extend([min_lat, max_lat, min_lon, max_lon])
    
    rows = db.execute(f"""
        SELECT rowid, latitude, longitude FROM churches
        WHERE {' AND '.join(where)}
    """, params).fetchall()
    
    # Filter valid coords
    result = []
    for r in rows:
        try:
            lat, lon = float(r[1]), float(r[2])
            if -90 <= lat <= 90 and -180 <= lon <= 180:
                result.append((r[0], lat, lon))
        except (ValueError, TypeError):
            continue
    return result


def fetch_elevations(coords):
    """Fetch elevation for a list of (rowid, lat, lon) tuples.
    Returns dict of rowid -> elevation_m."""
    result = {}
    total = len(coords)
    
    for i in range(0, total, BATCH_SIZE):
        batch = coords[i:i + BATCH_SIZE]
        lats = ','.join(str(c[1]) for c in batch)
        lons = ','.join(str(c[2]) for c in batch)
        
        url = f'https://api.open-meteo.com/v1/elevation?latitude={lats}&longitude={lons}'
        
        for attempt in range(5):
            try:
                req = urllib.request.Request(url, headers={'User-Agent': 'GRID/1.0 (elevation)'})
                with urllib.request.urlopen(req, timeout=30) as r:
                    data = json.loads(r.read())
                elevations = data.get('elevation', [])
                for j, c in enumerate(batch):
                    if j < len(elevations) and elevations[j] is not None:
                        result[c[0]] = round(elevations[j], 1)
                break
            except urllib.error.HTTPError as e:
                if e.code == 429:
                    wait = 10 * (2 ** attempt)
                    if attempt < 4:
                        sys.stderr.write(f'\n  Rate limited, waiting {wait}s')
                        sys.stderr.flush()
                        time.sleep(wait)
                        continue
                elif e.code == 504:
                    time.sleep(10 * (attempt + 1))
                    continue
                else:
                    if attempt < 4:
                        time.sleep(5)
                        continue
                    print(f'\n  Batch error HTTP {e.code}', file=sys.stderr)
            except Exception as e:
                if attempt < 4:
                    time.sleep(5)
                    continue
                print(f'\n  Batch error: {e}', file=sys.stderr)
        
        if (i // BATCH_SIZE) % 10 == 0:
            print(f'\r  {min(i+BATCH_SIZE, total):,}/{total:,}', end='')
            sys.stdout.flush()
        
        time.sleep(SLEEP_BETWEEN)
    
    print(f'\r  {total:,}/{total:,}', file=sys.stderr)
    return result


def check_coverage(db):
    """Print elevation coverage stats."""
    total = db.execute("SELECT COUNT(*) FROM churches").fetchone()[0]
    with_elev = db.execute("SELECT COUNT(*) FROM churches WHERE elevation_m IS NOT NULL").fetchone()[0]
    with_gps = db.execute("""
        SELECT COUNT(*) FROM churches 
        WHERE latitude IS NOT NULL AND latitude != ''
          AND longitude IS NOT NULL AND longitude != ''
    """).fetchone()[0]
    print(f'\n=== Elevation Coverage ===')
    print(f'  Total churches:     {total:>9,}')
    print(f'  With GPS:           {with_gps:>9,} ({with_gps/total*100:.1f}%)')
    print(f'  With elevation:     {with_elev:>9,} ({with_elev/total*100:.1f}%)')
    print(f'  Missing elevation:  {with_gps - with_elev:>9,}')

    if with_elev > 0:
        print(f'\n  Sample elevations:')
        for r in db.execute("SELECT elevation_m, COUNT(*) FROM churches WHERE elevation_m IS NOT NULL GROUP BY CAST(elevation_m AS INT) ORDER BY COUNT(*) DESC LIMIT 10"):
            print(f'    ~{r[0]:.0f}m: {r[1]:,} churches')


def main():
    import argparse
    p = argparse.ArgumentParser(description='Fetch church elevations from Open-Meteo')
    p.add_argument('--state', help='US state code to fill')
    p.add_argument('--bbox', nargs=4, type=float, help='min_lat min_lon max_lat max_lon')
    p.add_argument('--check-only', action='store_true', help='Just check coverage, no fetch')
    p.add_argument('--limit', type=int, help='Max churches to process')
    args = p.parse_args()

    db = sqlite3.connect(str(DB_PATH))
    add_column(db)

    if args.check_only:
        check_coverage(db)
        db.close()
        return

    churches = get_churches_to_fill(db, args.state, args.bbox)
    if args.limit:
        churches = churches[:args.limit]

    if not churches:
        print('No churches need elevation data.')
        check_coverage(db)
        db.close()
        return

    print(f'Fetching elevation for {len(churches):,} churches...')
    elevations = fetch_elevations(churches)

    # Update DB
    print('  Writing to database...')
    db.execute("BEGIN TRANSACTION")
    updates = [(elev, rowid) for rowid, elev in elevations.items()]
    db.executemany("UPDATE churches SET elevation_m=? WHERE rowid=?", updates)
    db.commit()

    check_coverage(db)

    # Log provenance
    try:
        db.execute("""
            INSERT INTO provenance_log (source, script_name, started_at, completed_at,
                churches_updated, fields_populated, status, notes)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            'open-meteo_elevation', 'elevate_churches.py',
            datetime.now().isoformat(), datetime.now().isoformat(),
            len(elevations), 'elevation_m', 'completed',
            f'Elevation fetched for {len(elevations):,} churches from Open-Meteo API.'
        ))
        db.commit()
    except Exception as e:
        print(f'  Provenance log skipped: {e}')

    db.close()
    print('Done.')


if __name__ == '__main__':
    main()
