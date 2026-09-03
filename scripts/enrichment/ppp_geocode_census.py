"""
Census Batch Geocoder for unmatched PPP loans (500 per block).
Uses Census batch geocoding API:
  POST https://geocoding.geo.census.gov/geocoder/locations/addressbatch

CSV format: unique_id, street, city, state, zip
Response:    id, address, match, matched_address, lat, lon, tiger_line_id, side
"""
import csv, io, os, sys, time, urllib.request, urllib.error
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from gw_db import connect

CENSUS_URL = "https://geocoding.geo.census.gov/geocoder/locations/addressbatch"
BATCH_SIZE = 500
BENCHMARK = "4"  # Public_AR_Current

def progress_bar(i, total, label='', width=40):
    if total == 0: return
    pct = (i + 1) / total
    filled = int(width * pct)
    bar = chr(0x2588) * filled + chr(0x2591) * (width - filled)
    print(f'\r  {label} [{bar}] {i+1:,}/{total:,} ({pct*100:.0f}%)', end='', flush=True)

def main():
    db = connect()
    # Set busy timeout to avoid "database is locked" from concurrent writers
    db._conn.execute("PRAGMA busy_timeout=10000")  # 10 second timeout
    
    # ---- Load unmatched PPP loans with addresses ----
    cur = db.execute("""
        SELECT id, borrower_name, borrower_address, borrower_city, borrower_state, borrower_zip
        FROM sba_ppp_loans
        WHERE church_id IS NULL
          AND latitude IS NULL
          AND borrower_address IS NOT NULL AND borrower_address != ''
          AND borrower_city IS NOT NULL AND borrower_city != ''
    """)
    rows = cur.fetchall()
    total = len(rows)
    print(f'Unmatched PPP loans to geocode: {total:,}')
    print(f'Batch size: {BATCH_SIZE}, batches: {total // BATCH_SIZE + 1}')
    
    if total == 0:
        print('Nothing to geocode.')
        db.close()
        return
    
    # ---- Batch process ----
    geocoded = 0
    failed = 0
    errors = 0
    t0 = time.time()
    batches = (total + BATCH_SIZE - 1) // BATCH_SIZE
    
    for batch_idx in range(batches):
        start = batch_idx * BATCH_SIZE
        end = min(start + BATCH_SIZE, total)
        chunk = rows[start:end]
        
        # Build CSV payload
        buf = io.StringIO()
        writer = csv.writer(buf)
        for ppp_id, name, addr, city, state, zip5 in chunk:
            street = str(addr).split(',')[0].strip()[:100] if addr else ''
            c = str(city).strip()[:100] if city else ''
            s = str(state).strip()[:2] if state else ''
            z = str(zip5).strip().split('-')[0][:5] if zip5 else ''
            writer.writerow([ppp_id, street, c, s, z])
        
        csv_data = buf.getvalue()
        
        # Send to Census batch geocoder
        try:
            boundary = f'----CensusGeocoder{int(time.time())}'
            body = (
                f'--{boundary}\r\n'
                f'Content-Disposition: form-data; name="addressFile"; filename="addresses.csv"\r\n'
                f'Content-Type: text/csv\r\n\r\n'
                f'{csv_data}\r\n'
                f'--{boundary}\r\n'
                f'Content-Disposition: form-data; name="benchmark"\r\n\r\n'
                f'{BENCHMARK}\r\n'
                f'--{boundary}--\r\n'
            ).encode('utf-8')
            
            # Send with retry
            result_text = None
            max_retries = 3
            for attempt in range(max_retries):
                try:
                    req = urllib.request.Request(
                        CENSUS_URL,
                        data=body,
                        headers={
                            'Content-Type': f'multipart/form-data; boundary={boundary}',
                            'User-Agent': 'GRID/1.0 (research project)'
                        }
                    )
                    with urllib.request.urlopen(req, timeout=90) as resp:
                        result_text = resp.read().decode('utf-8', errors='replace')
                    break
                except (urllib.error.URLError, urllib.error.HTTPError, ConnectionError, TimeoutError) as e:
                    if attempt < max_retries - 1:
                        wait = (attempt + 1) * 5
                        print(f'\n  Retry {attempt+1}/{max_retries} in {wait}s: {type(e).__name__}')
                        time.sleep(wait)
                    else:
                        raise
            
            if result_text is None:
                raise RuntimeError("All retries exhausted")
            
            # Parse results
            # Format (match): id, input_addr, "Match", "Exact"/"Non_Exact", matched_addr, "lon,lat", tiger_id, side
            # Format (no_match): id, input_addr, "No_Match"
            reader = csv.reader(io.StringIO(result_text))
            batch_hits = 0
            for result_row in reader:
                if len(result_row) < 3:
                    continue
                try:
                    rid = int(result_row[0])
                    match_type = result_row[2]
                    
                    if match_type == "Match" and len(result_row) >= 6:
                        # lon,lat are in one quoted field: "-77.03,38.89"
                        lonlat = result_row[5]
                        if "," in lonlat:
                            lon_str, lat_str = lonlat.split(",")
                            lat = float(lat_str)
                            lon = float(lon_str)
                            
                            if lat != 0 and lon != 0:
                                db.execute(
                                    "UPDATE sba_ppp_loans SET latitude=?, longitude=? WHERE id=?",
                                    (lat, lon, rid)
                                )
                                geocoded += 1
                                batch_hits += 1
                            else:
                                failed += 1
                        else:
                            failed += 1
                    else:
                        failed += 1
                except (ValueError, IndexError):
                    failed += 1
            
            progress_bar(batch_idx, batches, f'Geocoding (hit={batch_hits})')
            
        except urllib.error.HTTPError as e:
            errors += 1
            body = e.read().decode('utf-8', errors='replace')[:200] if e.fp else ''
            print(f'\n  HTTP {e.code} batch {batch_idx}: {body}')
            time.sleep(5)
        except Exception as e:
            errors += 1
            print(f'\n  Error batch {batch_idx}: {type(e).__name__}: {e}')
            time.sleep(5)
        
        # Commit every batch
        db.commit()
        
        # Rate limit: be polite to Census server
        time.sleep(0.8)
    
    db.commit()
    
    elapsed = time.time() - t0
    print(f'\n\nDone in {elapsed/60:.1f}m')
    print(f'  Geocoded: {geocoded:,}')
    print(f'  Failed to match: {failed:,}')
    print(f'  Batch errors: {errors}')
    print(f'  Rate: {geocoded/elapsed:.1f}/s')
    
    # Summary
    cur = db.execute("SELECT COUNT(*) FROM sba_ppp_loans WHERE latitude IS NOT NULL")
    total_geocoded = cur.fetchone()[0]
    cur = db.execute("SELECT COUNT(*) FROM sba_ppp_loans WHERE church_id IS NULL AND latitude IS NULL")
    remaining = cur.fetchone()[0]
    print(f'\n  Total geocoded PPP loans: {total_geocoded:,}')
    print(f'  Remaining unmatched+ungeocoded: {remaining:,}')
    
    db.close()

if __name__ == '__main__':
    main()
