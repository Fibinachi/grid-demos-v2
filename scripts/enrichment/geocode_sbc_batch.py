"""
Geocode SBC directory churches using Census batch API.
Updates lat/lng and tract FIPS so food desert data becomes available.
"""
import csv, io, os, sqlite3, time, urllib.request, urllib.parse, http.client

DB_PATH = r'E:\grid\churches.db'
CENSUS_BATCH = 'https://geocoding.geo.census.gov/geocoder/geographies/addressbatch'
CHUNK_SIZE = 500  # Max batch size (Census allows up to 10K, but 500 is safer)
DELAY = 1.0  # Delay between batches

def get_churches():
    """Get SBC directory churches that need geocoding."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    
    # Exclude already-geocoded ones
    c.execute("""
        SELECT id, address, city, state, zip
        FROM churches 
        WHERE classification_source IN ('sbc_directory', 'sbc_scrape')
          AND (latitude IS NULL OR latitude = 0)
          AND address != '' AND city != '' AND state != ''
        ORDER BY id
    """)
    rows = [dict(r) for r in c.fetchall()]
    conn.close()
    print(f"Churches needing geocoding: {len(rows):,}")
    return rows

def write_csv(chunk, path):
    """Write a batch CSV for Census upload."""
    with open(path, 'w', newline='', encoding='utf-8') as f:
        w = csv.writer(f)
        w.writerow(['id', 'address', 'city', 'state', 'zip'])
        for r in chunk:
            w.writerow([r['id'], r['address'], r['city'], r['state'], r['zip']])

def parse_result(results_csv):
    """Parse Census batch geocoding results."""
    results = {}
    reader = csv.reader(io.StringIO(results_csv))
    for row in reader:
        if len(row) < 9:
            continue
        try:
            uid = int(row[0].strip())
        except:
            continue
        match_type = row[1].strip() if len(row) > 1 else ''
        matched_addr = row[2].strip() if len(row) > 2 else ''
        coords = row[4].strip() if len(row) > 4 else ''
        tract_geoid = row[8].strip() if len(row) > 8 else ''
        
        lat, lng = None, None
        if coords:
            parts = coords.split(',')
            if len(parts) == 2:
                try:
                    lng = float(parts[0].strip())
                    lat = float(parts[1].strip())
                except:
                    pass
        
        # Extract tract FIPS from GEOID (15 chars: SSCCCTTTTTT)
        tract_fips = ''
        if tract_geoid and len(tract_geoid) >= 11:
            # GEOID format: SSCCCTTTTTT (state+county+tract)
            tract_fips = tract_geoid[-11:] if len(tract_geoid) >= 11 else tract_geoid
        
        if lat and lng:
            results[uid] = {
                'latitude': lat,
                'longitude': lng,
                'tract_fips': tract_fips,
                'match_type': match_type,
                'geocode_source': 'census_batch',
                'tract_geocode_source': 'census_batch',
            }
    return results

def upload_batch(csv_path):
    """Upload batch to Census geocoder."""
    boundary = '----WebKitFormBoundary7MA4YWxkTrZu0gW'
    
    with open(csv_path, 'rb') as f:
        file_data = f.read()
    
    body = (
        f'--{boundary}\r\n'
        f'Content-Disposition: form-data; name="addressFile"; filename="batch.csv"\r\n'
        f'Content-Type: text/csv\r\n\r\n'
    ).encode('utf-8') + file_data + (
        f'\r\n--{boundary}\r\n'
        f'Content-Disposition: form-data; name="benchmark"\r\n\r\n'
        f'Public_AR_Current\r\n'
        f'--{boundary}\r\n'
        f'Content-Disposition: form-data; name="vintage"\r\n\r\n'
        f'Current_Current\r\n'
        f'--{boundary}\r\n'
        f'Content-Disposition: form-data; name="layers"\r\n\r\n'
        f'2020\r\n'
        f'--{boundary}--\r\n'
    ).encode('utf-8')
    
    headers = {
        'Content-Type': f'multipart/form-data; boundary={boundary}',
        'Accept': 'text/html,application/xhtml+xml',
    }
    
    req = urllib.request.Request(CENSUS_BATCH, data=body, headers=headers, method='POST')
    with urllib.request.urlopen(req, timeout=120) as resp:
        return resp.read().decode('utf-8', errors='replace')

def update_db(results):
    """Update churches table with geocoding results."""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    updated = 0
    for uid, data in results.items():
        c.execute("""
            UPDATE churches 
            SET latitude = ?, longitude = ?,
                tract_fips = ?,
                geocode_source = ?,
                tract_geocode_source = ?,
                tract_geocode_date = date('now')
            WHERE id = ?
        """, (
            data['latitude'], data['longitude'],
            data['tract_fips'],
            data['geocode_source'],
            data['tract_geocode_source'],
            uid
        ))
        updated += 1
        if updated % 500 == 0:
            conn.commit()
    conn.commit()
    c.close()
    return updated

def main():
    print("Census Batch Geocoding for SBC Directory Churches\n")
    
    churches = get_churches()
    if not churches:
        print("No churches need geocoding.")
        return
    
    total = len(churches)
    all_results = {}
    batch_num = 0
    
    for start in range(0, total, CHUNK_SIZE):
        chunk = churches[start:start + CHUNK_SIZE]
        batch_num += 1
        csv_path = f'data/fcc/geocode_batch_{batch_num}.csv'
        
        write_csv(chunk, csv_path)
        print(f"  Batch {batch_num}: {len(chunk)} addresses ({start+1}-{start+len(chunk)} of {total})")
        print(f"    Uploading...", end=' ', flush=True)
        
        try:
            result_csv = upload_batch(csv_path)
            results = parse_result(result_csv)
            all_results.update(results)
            matched = len(results)
            print(f"{matched}/{len(chunk)} matched")
        except Exception as e:
            print(f"FAILED: {e}")
            matched = 0
        
        os.unlink(csv_path)
        if start + CHUNK_SIZE < total:
            time.sleep(DELAY)
    
    # Update DB
    if all_results:
        n = update_db(all_results)
        print(f"\nUpdated {n:,} churches with coordinates + tract FIPS")
    
    # Summary
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT COUNT(1) FROM churches WHERE classification_source IN ('sbc_directory','sbc_scrape') AND latitude IS NOT NULL AND latitude != 0")
    geo = c.fetchone()[0]
    print(f"Total SBC churches now geocoded: {geo:,}")
    conn.close()

if __name__ == '__main__':
    main()
