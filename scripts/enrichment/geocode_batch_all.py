
"""Batch geocode all ungeocoded churches via Census addressbatch API.
Handles up to 10K addresses per request. Checkpoint/resume support.
Usage: python geocode_batch_all.py [--resume]
"""
import csv, io, os, sqlite3, sys, time, urllib.request, json
from datetime import datetime

BASE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # up to grantwizard/
DB_PATH = os.path.join(BASE, 'churches.db')
CENSUS_BATCH = 'https://geocoding.geo.census.gov/geocoder/geographies/addressbatch'
CHUNK_SIZE = 500       # Census allows up to 10K, 500 is reliable
DELAY = 0.25            # seconds between batches

RESUME = '--resume' in sys.argv
SOURCE = None
for a in sys.argv:
    if a.startswith('--source='):
        SOURCE = a.split('=', 1)[1]

CHECKPOINT = os.path.join(BASE, 'data', f'geocode_batch_{SOURCE}_checkpoint.json' if SOURCE else 'geocode_batch_checkpoint.json')

def load_checkpoint():
    if os.path.exists(CHECKPOINT):
        with open(CHECKPOINT) as f:
            return json.load(f)
    return {'processed': 0, 'geocoded': 0, 'batches': 0}

def save_checkpoint(processed, geocoded, batches):
    os.makedirs(os.path.dirname(CHECKPOINT), exist_ok=True)
    with open(CHECKPOINT, 'w') as f:
        json.dump({'processed': processed, 'geocoded': geocoded, 'batches': batches, 'last': datetime.utcnow().isoformat()}, f)

def get_ungeocoded(source=None):
    """Get all churches needing geocoding that have addresses."""
    conn = sqlite3.connect(DB_PATH, timeout=30)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    if source:
        c.execute("""
            SELECT id, address, city, state, zip
            FROM churches 
            WHERE source = ?
              AND (latitude IS NULL OR latitude = 0)
              AND address IS NOT NULL AND address != ''
              AND city IS NOT NULL AND city != ''
              AND state IS NOT NULL AND state != ''
            ORDER BY id
        """, (source,))
    else:
        c.execute("""
            SELECT id, address, city, state, zip
            FROM churches 
            WHERE geocode_attempts = 0
              AND address IS NOT NULL AND address != ''
              AND city IS NOT NULL AND city != ''
              AND state IS NOT NULL AND state != ''
            ORDER BY id
        """)
    rows = [dict(r) for r in c.fetchall()]
    conn.close()
    return rows

def write_csv(chunk, path):
    with open(path, 'w', newline='', encoding='utf-8') as f:
        w = csv.writer(f)
        w.writerow(['id', 'address', 'city', 'state', 'zip'])
        for r in chunk:
            w.writerow([r['id'], r['address'], r['city'], r['state'], r['zip']])

def parse_result(results_csv):
    """Parse Census batch geocoding results.
    Response format: id, input_address, match_status, match_type, matched_addr, coords(lng,lat), tiger_line_id, side, state_fips, county_fips, tract, block
    Trailer row: "id","address, city, state, zip","No_Match"
    """
    results = {}
    reader = csv.reader(io.StringIO(results_csv))
    for row in reader:
        if len(row) < 6:
            continue
        # Skip trailer row
        if row[0] == 'id' or row[0].strip('"') == 'id':
            continue
        # Skip non-matches
        if row[2].strip('"') != 'Match':
            continue
        try:
            uid = int(row[0].strip('"'))
        except ValueError:
            continue
        
        # Coordinates: row[5] = "lng,lat"
        coords = row[5].strip('"')
        lat, lng = None, None
        if coords and ',' in coords:
            parts = coords.split(',')
            if len(parts) >= 2:
                try:
                    lng = float(parts[0].strip())
                    lat = float(parts[1].strip())
                except ValueError:
                    continue
        
        # Tract FIPS: row[8]=state, row[9]=county, row[10]=tract
        tract_fips = ''
        if len(row) >= 11:
            st = row[8].strip('"') if len(row) > 8 else ''
            co = row[9].strip('"') if len(row) > 9 else ''
            tr = row[10].strip('"') if len(row) > 10 else ''
            if st and co and tr:
                tract_fips = f'{st}{co}{tr}'
        
        if lat and lng:
            results[uid] = {
                'latitude': lat, 'longitude': lng,
                'tract_fips': tract_fips,
                'geocode_source': 'census_batch',
                'tract_geocode_source': 'census_batch',
                'tract_geocode_date': datetime.utcnow().strftime('%Y-%m-%d'),
            }
    return results

def upload_batch(csv_path):
    boundary = '----CensusGeocoderBoundary7MA4YWxk'
    with open(csv_path, 'rb') as f:
        file_data = f.read()
    
    body = (
        f'--{boundary}\r\n'
        'Content-Disposition: form-data; name="addressFile"; filename="batch.csv"\r\n'
        'Content-Type: text/csv\r\n\r\n'
    ).encode('utf-8') + file_data + (
        f'\r\n--{boundary}\r\n'
        'Content-Disposition: form-data; name="benchmark"\r\n\r\n'
        'Public_AR_Current\r\n'
        f'--{boundary}\r\n'
        'Content-Disposition: form-data; name="vintage"\r\n\r\n'
        'Current_Current\r\n'
        f'--{boundary}\r\n'
        'Content-Disposition: form-data; name="layers"\r\n\r\n'
        '2020\r\n'
        f'--{boundary}--\r\n'
    ).encode('utf-8')
    
    req = urllib.request.Request(CENSUS_BATCH, data=body,
        headers={'Content-Type': f'multipart/form-data; boundary={boundary}'},
        method='POST')
    with urllib.request.urlopen(req, timeout=120) as resp:
        return resp.read().decode('utf-8', errors='replace')

def update_db(results, conn, failed_ids):
    c = conn.cursor()
    now = datetime.utcnow().isoformat()
    updated = 0
    for uid, data in results.items():
        c.execute("""
            UPDATE churches 
            SET latitude = ?, longitude = ?, tract_fips = ?,
                geocode_source = ?, tract_geocode_source = ?, tract_geocode_date = ?,
                geocode_attempts = geocode_attempts + 1, geocode_last_attempt = ?
            WHERE id = ?
        """, (data['latitude'], data['longitude'], data['tract_fips'],
              data['geocode_source'], data['tract_geocode_source'],
              data['tract_geocode_date'], now, uid))
        updated += c.rowcount
    # Mark failed attempts too
    for uid in failed_ids:
        c.execute("""
            UPDATE churches SET 
                geocode_attempts = geocode_attempts + 1, geocode_last_attempt = ?
            WHERE id = ?
        """, (now, uid))
    conn.commit()
    return updated

def main():
    print("=== Census Batch Geocoding (All Churches) ===", flush=True)
    
    churches = get_ungeocoded(source=SOURCE)
    label = f" (source={SOURCE})" if SOURCE else ""
    print(f"Churches needing geocoding{label}: {len(churches):,}", flush=True)
    
    if not churches:
        print("All churches already geocoded!")
        return
    
    ck = load_checkpoint()
    start_batch = ck['batches'] if RESUME else 0
    total_geocoded = ck['geocoded'] if RESUME else 0
    total_processed = ck['processed'] if RESUME else 0
    
    if RESUME:
        print(f"Resuming from batch {start_batch} (processed {total_processed:,}, geocoded {total_geocoded:,})", flush=True)
        churches = churches[total_processed:]
    
    conn = sqlite3.connect(DB_PATH, timeout=30)
    batch_num = start_batch
    temp_dir = os.path.join(BASE, 'data', 'fcc')
    os.makedirs(temp_dir, exist_ok=True)
    
    for start in range(0, len(churches), CHUNK_SIZE):
        chunk = churches[start:start + CHUNK_SIZE]
        batch_num += 1
        csv_path = os.path.join(temp_dir, f'geocode_batch_{batch_num:04d}.csv')
        
        write_csv(chunk, csv_path)
        print(f"  Batch {batch_num}: {len(chunk)} addresses "
              f"({total_processed + start + 1:,}-{total_processed + start + len(chunk):,} "
              f"of {total_processed + len(churches):,})", flush=True, end=" ")
        
        try:
            result_csv = upload_batch(csv_path)
            results = parse_result(result_csv)
            matched = len(results)
            # IDs that were submitted but didn't get a match
            submitted_ids = [r['id'] for r in chunk]
            matched_ids = set(results.keys())
            failed_ids = [i for i in submitted_ids if i not in matched_ids]
            if matched:
                updated = update_db(results, conn, failed_ids)
                total_geocoded += updated
            else:
                # All failed — mark them
                update_db({}, conn, submitted_ids)
            total_processed += len(chunk)
            save_checkpoint(total_processed, total_geocoded, batch_num)
            print(f"-> {matched:,}/{len(chunk):,} matched ({total_geocoded:,} total)", flush=True)
        except Exception as e:
            print(f"FAILED: {e}", flush=True)
            # Save checkpoint even on failure so we can resume
            save_checkpoint(total_processed, total_geocoded, batch_num)
        
        try:
            os.unlink(csv_path)
        except:
            pass
        
        if start + CHUNK_SIZE < len(churches):
            time.sleep(DELAY)
    
    conn.close()
    print(f"\nDone. Total geocoded: {total_geocoded:,}", flush=True)

if __name__ == '__main__':
    main()
