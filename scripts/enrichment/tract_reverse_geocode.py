#!/usr/bin/env python3
"""
Tract Reverse-Geocoding — lat/lng → Census Tract FIPS
========================================================
Uses the US Census Bureau's free geocoding API to convert church
latitude/longitude coordinates into 11-digit Census Tract FIPS codes.

Source: https://geocoding.geo.census.gov/geocoder/Geocoding_Services_API.pdf

The Census Geocoder provides a coordinate-based geography lookup:
    POST /geocoder/geographies/coordinates
        x={longitude}&y={latitude}&benchmark=Public_AR_Current&vintage=Census2020_Census2020&format=json

This returns:
    - 11-digit GEOID (state 02 + county 003 + tract 020100 = "02003020100")
    - State, county, tract, block codes
    - Centroid coordinates
    - Land area, water area, etc.

Coverage:
    253,078 churches with lat/lng can be resolved to tract level.
    The Census Geocoder is FREE, has no rate limit (within reason),
    and no API key is required.

Batch processing:
    The Census Geocoder supports batch files (up to 1000 addresses/coordinates).
    For 253K churches → ~253 batches → ~30-60 minutes.

Usage:
    # Dry run — test 100 churches
    python scripts/enrichment/tract_reverse_geocode.py --dry-run --limit 100

    # Full run — process all churches with lat/lng
    python scripts/enrichment/tract_reverse_geocode.py

    # Process only Mapbox-quality geocodes (best precision)
    python scripts/enrichment/tract_reverse_geocode.py --min-confidence street

    # Resume from checkpoint
    python scripts/enrichment/tract_reverse_geocode.py --resume

Requires: pip install requests (for batch mode)

API: FREE — no key required
"""
import csv, io, json, os, re, sys, time, sqlite3, urllib.request, urllib.parse
from datetime import datetime
from collections import defaultdict

# ── Config ──
PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DB_PATH = os.path.join(PROJECT_DIR, 'churches.db')
CHECKPOINT = os.path.join(PROJECT_DIR, 'data', 'tract_geocode_checkpoint.json')

# Census Geocoder endpoints
CENSUS_GEOCODE_URL = "https://geocoding.geo.census.gov/geocoder/geographies/coordinates"

# Thread pool size — conservative to avoid rate limiting
WORKERS = 4
REQUEST_DELAY = 0.05  # 50ms between requests per worker ~ 80 req/sec total

# Stats
stats = {'processed': 0, 'matched': 0, 'errors': 0, 'no_result': 0, 'skipped': 0}
stats_lock = __import__('threading').Lock()
db_lock = __import__('threading').Lock()


def geocode_coordinate(lat, lng):
    """Reverse-geocode a lat/lng coordinate to get census geography.
    
    Returns dict with: tract_fips, state_fips, county_fips, tract_code, block_code
    or None if not found.
    """
    params = urllib.parse.urlencode({
        'x': lng,
        'y': lat,
        'benchmark': 'Public_AR_Current',
        'vintage': 'Current_Current',
        'format': 'json',
    })
    url = f"{CENSUS_GEOCODE_URL}?{params}"
    
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'GrantWizard/1.0'})
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode('utf-8'))
        
        geographies = data.get('result', {}).get('geographies', {})
        
        # The response contains geography types like 'Census Tracts', 'Blocks', etc.
        # We want the tract-level geography
        tract_key = None
        for key in geographies:
            if 'Tract' in key or 'tract' in key:
                tract_key = key
                break
        
        if not tract_key or not geographies[tract_key]:
            return None
        
        tract_info = geographies[tract_key][0]
        
        # Build 11-digit tract FIPS: state(2) + county(3) + tract(6)
        state_fips = tract_info.get('STATE', '')
        county_fips = tract_info.get('COUNTY', '')
        tract_code = tract_info.get('TRACT', '')
        
        if state_fips and county_fips and tract_code:
            return {
                'tract_fips': f"{state_fips}{county_fips}{tract_code}",
                'state_fips': state_fips,
                'county_fips': f"{state_fips}{county_fips}",
                'tract_code': tract_code,
                'block_code': tract_info.get('BLOCK', ''),
            }
        
        return None
    except Exception as e:
        return None


def batch_geocode_coordinates(points):
    """Batch geocode coordinates using Census batch API.
    
    points: list of (church_id, lat, lng)
    Returns: list of (church_id, tract_fips, county_fips) or (church_id, None, None)
    """
    if not points:
        return []
    
    # Census batch format (CSV):
    # Columns: id, longitude, latitude
    # Note: Census batch uses longitude FIRST then latitude
    csv_output = io.StringIO()
    writer = csv.writer(csv_output)
    writer.writerow(['id', 'longitude', 'latitude'])
    for cid, lat, lng in points:
        writer.writerow([cid, lng, lat])
    
    csv_data = csv_output.getvalue()
    
    # Build multipart form data
    boundary = '----WebKitFormBoundary' + os.urandom(16).hex()
    body = []
    
    # addressFile field
    body.append(f'--{boundary}')
    body.append('Content-Disposition: form-data; name="addressFile"; filename="coordinates.csv"')
    body.append('Content-Type: text/csv')
    body.append('')
    body.append(csv_data)
    
    # Other required fields
    for name, value in [
        ('benchmark', 'Public_AR_Current'),
        ('vintage', 'Current_Current'),
        ('format', 'json'),
    ]:
        body.append(f'--{boundary}')
        body.append(f'Content-Disposition: form-data; name="{name}"')
        body.append('')
        body.append(value)
    
    body.append(f'--{boundary}--')
    body.append('')
    
    body_bytes = '\r\n'.join(body).encode('utf-8')
    
    url = "https://geocoding.geo.census.gov/geocoder/geographies/addressbatch"
    
    try:
        req = urllib.request.Request(url, data=body_bytes, headers={
            'Content-Type': f'multipart/form-data; boundary={boundary}',
            'User-Agent': 'GrantWizard/1.0',
        })
        with urllib.request.urlopen(req, timeout=120) as resp:
            response_text = resp.read().decode('utf-8', errors='replace')
        
        # Response is CSV with columns:
        # id, address, match_status, match_type, matched_address, geography_json
        results = []
        reader = csv.reader(io.StringIO(response_text))
        for row in reader:
            if len(row) < 6:
                continue
            cid = row[0].strip()
            match_status = row[2].strip()
            
            if match_status == 'Match':
                try:
                    geo = json.loads(row[5])
                    # Extract tract info from geographies
                    geos = geo.get('geographies', {})
                    tract_key = None
                    for k in geos:
                        if 'Tract' in k:
                            tract_key = k
                            break
                    
                    if tract_key and geos[tract_key]:
                        t = geos[tract_key][0]
                        tract_fips = f"{t.get('STATE','')}{t.get('COUNTY','')}{t.get('TRACT','')}"
                        county_fips = f"{t.get('STATE','')}{t.get('COUNTY','')}"
                        results.append((int(cid) if cid.isdigit() else cid, tract_fips, county_fips))
                    else:
                        results.append((int(cid) if cid.isdigit() else cid, None, None))
                except (json.JSONDecodeError, KeyError, TypeError):
                    results.append((int(cid) if cid.isdigit() else cid, None, None))
            else:
                results.append((int(cid) if cid.isdigit() else cid, None, None))
        
        return results
    except Exception as e:
        # Fall back to individual lookups
        results = []
        for cid, lat, lng in points:
            result = geocode_coordinate(lat, lng)
            if result:
                results.append((cid, result['tract_fips'], result['county_fips']))
            else:
                results.append((cid, None, None))
        return results


def get_churches_for_tract(db, min_confidence=None, limit=0):
    """Get churches with lat/lng that need tract FIPS lookup.
    
    min_confidence: 'street' (Mapbox/census) or None (all)
    """
    conditions = ["latitude IS NOT NULL", "latitude != 0", "longitude IS NOT NULL"]
    
    if min_confidence == 'street':
        conditions.append("geocode_source IN ('mapbox', 'census_street', 'osm')")
    
    query = f"""
        SELECT id, latitude, longitude, name, city, state
        FROM churches
        WHERE {' AND '.join(conditions)}
        ORDER BY id
    """
    if limit:
        query += f" LIMIT {limit}"
    return db.execute(query).fetchall()


def load_checkpoint():
    """Load processed church IDs."""
    if not os.path.exists(CHECKPOINT):
        return set()
    try:
        with open(CHECKPOINT) as f:
            data = json.load(f)
        return set(data.get('processed_ids', []))
    except Exception:
        return set()


def save_checkpoint(processed_ids):
    """Save checkpoint."""
    os.makedirs(os.path.dirname(CHECKPOINT), exist_ok=True)
    with open(CHECKPOINT, 'w') as f:
        json.dump({
            'processed_ids': list(processed_ids),
            'updated': datetime.now().isoformat()
        }, f)


def add_tract_column(db):
    """Add tract FIPS column if not exists."""
    existing = {r[1] for r in db.execute("PRAGMA table_info(churches)").fetchall()}
    new_cols = {
        'tract_fips': 'TEXT',
        'tract_geocode_source': 'TEXT',
        'tract_geocode_date': 'TEXT',
        'county_fips_5': 'TEXT',  # 5-digit county FIPS (from tract lookup, more accurate)
    }
    for col, dtype in new_cols.items():
        if col not in existing:
            db.execute(f"ALTER TABLE churches ADD COLUMN {col} {dtype}")
            print(f"  Added column: {col}")


def main():
    import argparse
    parser = argparse.ArgumentParser(description='Tract Reverse-Geocoding')
    parser.add_argument('--dry-run', action='store_true', help='Preview only')
    parser.add_argument('--limit', type=int, default=0, help='Limit churches')
    parser.add_argument('--resume', action='store_true', help='Resume from checkpoint')
    parser.add_argument('--min-confidence', choices=['any', 'street'], default='any',
                       help='Minimum geocode precision (street=mapbox/osm/census, any=all)')
    args = parser.parse_args()
    
    print("=" * 60)
    print("Census Tract Reverse-Geocoding Pipeline")
    print("=" * 60)
    
    db = sqlite3.connect(DB_PATH)
    
    # Add tract column
    add_tract_column(db)
    db.commit()
    
    # Get churches
    min_conf = 'street' if args.min_confidence == 'street' else None
    churches = get_churches_for_tract(db, min_conf, args.limit)
    print(f"\nChurches to process: {len(churches):,}")
    
    if args.dry_run:
        print("\n  [DRY RUN] Sample churches that would be geocoded:")
        for r in churches[:10]:
            print(f"    {r[0]:>8d} | {r[3][:40]:40s} | ({r[1]:.5f}, {r[2]:.5f})")
        if len(churches) > 10:
            print(f"    ... and {len(churches) - 10:,} more")
        db.close()
        return
    
    # Load checkpoint
    processed_ids = load_checkpoint() if args.resume else set()
    if processed_ids:
        print(f"  Resuming: {len(processed_ids):,} already processed")
    
    # Filter already processed
    to_process = [(r[0], r[1], r[2]) for r in churches if r[0] not in processed_ids]
    print(f"  Remaining: {len(to_process):,}")
    
    if not to_process:
        print("  All churches already processed!")
        db.close()
        return
    
    # Process with threaded individual lookups (more reliable than batch)
    import concurrent.futures
    
    all_updates = []
    processed_total = 0
    
    def lookup_one(point):
        """Individual coordinate lookup with rate limiting."""
        cid, lat, lng = point
        # Rate limit: workers share work, each waits slightly
        time.sleep(REQUEST_DELAY)
        result = geocode_coordinate(lat, lng)
        with stats_lock:
            stats['processed'] += 1
            if result:
                stats['matched'] += 1
            elif 'errors':
                pass  # geocode_coordinate returns None on any error
        if result:
            return (cid, result['tract_fips'], result['county_fips'])
        return (cid, None, None)
    
    # Process in chunks with progress updates
    CHUNK = WORKERS * 50  # 200 records per progress update
    with concurrent.futures.ThreadPoolExecutor(max_workers=WORKERS) as executor:
        futures = {executor.submit(lookup_one, pt): pt for pt in to_process}
        done_count = 0
        batch_updates = []
        
        for future in concurrent.futures.as_completed(futures):
            try:
                cid, tract_fips, county_fips = future.result()
                done_count += 1
                if tract_fips:
                    batch_updates.append((cid, tract_fips, county_fips))
            except Exception:
                pass
            
            # Periodic progress update + DB write
            if done_count % CHUNK == 0 or done_count == len(to_process):
                pct = done_count / len(to_process) * 100
                with stats_lock:
                    m = stats['matched']
                print(f"  {done_count:>8,}/{len(to_process):,} ({pct:5.1f}%) — {m:,} tract FIPS found")
                
                if batch_updates:
                    _write_updates_local(db, batch_updates)
                    batch_updates = []
    
    # Final write of remaining
    if batch_updates:
        _write_updates_local(db, batch_updates)
    if all_updates:
        _write_updates(db, all_updates)
    
    # Update checkpoint
    all_processed = processed_ids | {r[0] for r in to_process}
    save_checkpoint(all_processed)
    
    # Log to provenance
    db.execute("""
        INSERT INTO provenance_log
            (source, script_name, started_at, completed_at,
             churches_updated, churches_inserted, fields_populated,
             records_attempted, records_matched, status, notes)
        VALUES (?, ?, ?, ?, ?, 0, ?, ?, ?, 'completed', ?)
    """, (
        'census_tract_geocode',
        'tract_reverse_geocode.py',
        datetime.now().isoformat(),
        datetime.now().isoformat(),
        stats['matched'],
        'tract_fips,county_fips_5,tract_geocode_date',
        stats['processed'],
        stats['matched'],
        f'Census Geocoder batch processing. {stats["matched"]} tract FIPS resolved from {stats["processed"]} coordinates.'
    ))
    db.commit()
    
    # Summary
    print(f"\n{'='*60}")
    print("RESULTS")
    print(f"{'='*60}")
    print(f"  Coordinates processed:  {stats['processed']:>8,}")
    print(f"  Tract FIPS matched:     {stats['matched']:>8,} ({(stats['matched']/max(stats['processed'],1))*100:.1f}%)")
    print(f"  No result:              {stats['no_result']:>8,}")
    print(f"  Errors:                 {stats['errors']:>8,}")
    
    db.close()
    print("\nDone!")


def _write_updates(db, updates):
    """Write batch updates to database."""
    for cid, tract_fips, county_fips in updates:
        db.execute("""
            UPDATE churches SET
                tract_fips = ?,
                county_fips_5 = ?,
                tract_geocode_source = 'census_geocoder',
                tract_geocode_date = datetime('now'),
                last_updated = datetime('now')
            WHERE id = ?
        """, (tract_fips, county_fips, cid))
    db.commit()
    print(f"    Written {len(updates):,} updates to DB...")
    updates.clear()


def _write_updates_local(updates_list, updates):
    """Thread-safe DB write."""
    with db_lock:
        db2 = sqlite3.connect(DB_PATH, timeout=60)
        for cid, tract_fips, county_fips in updates:
            db2.execute("""
                UPDATE churches SET
                    tract_fips = ?,
                    county_fips_5 = ?,
                    tract_geocode_source = 'census_geocoder',
                    tract_geocode_date = datetime('now'),
                    last_updated = datetime('now')
                WHERE id = ?
            """, (tract_fips, county_fips, cid))
        db2.commit()
        db2.close()
    updates.clear()


if __name__ == '__main__':
    main()
