"""
Geocode US churches via Census batch API.
Batch size = 1,000 to avoid 500 errors.
"""
import csv, io, json, os, sys, time, re
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
import sqlite3

DB_PATH = Path("E:/grid/churches.db")
CENSUS_URL = "https://geocoding.geo.census.gov/geocoder/locations/addressbatch"
BENCHMARK = "Public_AR_Current"
BATCH_SIZE = 1000
CHECKPOINT = Path("data/geocode_census_checkpoint.json")


def load_checkpoint():
    if CHECKPOINT.exists():
        with open(CHECKPOINT) as f:
            return set(int(x) for x in json.load(f) if x is not None)
    return set()


def save_checkpoint(ids):
    existing = load_checkpoint()
    existing.update(int(x) for x in ids if x is not None)
    CHECKPOINT.parent.mkdir(parents=True, exist_ok=True)
    with open(CHECKPOINT, 'w') as f:
        json.dump(sorted(existing), f)


def clean(val):
    if not val: return ""
    return str(val).replace(',', ' ').replace('\n', ' ').replace('\r', ' ').strip()[:100]


def build_csv(records):
    lines = []
    for ch_id, address, city, state, zip5 in records:
        lines.append(f'{ch_id},"{clean(address)}","{clean(city)}","{clean(state)}",{clean(zip5).split("-")[0][:5]}')
    return '\n'.join(lines)


def send_batch(csv_body):
    """Send to Census, return {id: {lat, lon}}."""
    boundary = "----CensusBoundary" + str(int(time.time()))
    body = (
        f'--{boundary}\r\n'
        f'Content-Disposition: form-data; name="addressFile"; filename="batch.csv"\r\n'
        f'Content-Type: text/csv\r\n\r\n'
        f'{csv_body}\r\n'
        f'--{boundary}\r\n'
        f'Content-Disposition: form-data; name="benchmark"\r\n\r\n'
        f'{BENCHMARK}\r\n'
        f'--{boundary}\r\n'
        f'Content-Disposition: form-data; name="vintage"\r\n\r\n'
        f'Current_Current\r\n'
        f'--{boundary}--\r\n'
    ).encode('utf-8')
    
    try:
        req = urllib.request.Request(
            CENSUS_URL, data=body,
            headers={'Content-Type': f'multipart/form-data; boundary={boundary}'}
        )
        with urllib.request.urlopen(req, timeout=120) as resp:
            raw = resp.read().decode('utf-8-sig')
    except Exception as e:
        print(f"API error: {e}")
        return {}
    
    results = {}
    reader = csv.reader(io.StringIO(raw))
    for row in reader:
        if len(row) < 6:
            continue
        try:
            ch_id = int(row[0].strip())
            match_type = row[2].strip() if len(row) > 2 else ''
            coord_str = row[5].strip() if len(row) > 5 else ''
            if match_type in ('Match', 'Exact') and coord_str and ',' in coord_str:
                parts = coord_str.split(',')
                lon = float(parts[0])
                lat = float(parts[1])
                if lat != 0 and lon != 0 and -90 <= lat <= 90 and -180 <= lon <= 180:
                    results[ch_id] = {'lat': lat, 'lon': lon}
        except (ValueError, IndexError):
            continue
    return results


def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument('--phase', type=int, choices=[1,2], default=1)
    ap.add_argument('--dry-run', action='store_true')
    ap.add_argument('--batch-size', type=int, default=BATCH_SIZE)
    ap.add_argument('--quick-test', type=int, help='Test with N addresses')
    args = ap.parse_args()

    checkpoint = load_checkpoint()
    
    conn = sqlite3.connect(str(DB_PATH))
    conn.execute("PRAGMA journal_mode=WAL")
    
    if args.phase == 1:
        rows = conn.execute("""
            SELECT id, address, city, state, zip5 FROM churches
            WHERE country='US' AND address IS NOT NULL AND address != ''
              AND city IS NOT NULL AND city != '' AND state IS NOT NULL AND state != ''
              AND (latitude IS NULL OR longitude IS NULL OR latitude=0 OR longitude=0)
            ORDER BY id
        """).fetchall()
    else:
        rows = conn.execute("""
            SELECT id, '', city, state, zip5 FROM churches
            WHERE country='US' AND (address IS NULL OR address = '')
              AND city IS NOT NULL AND city != '' AND state IS NOT NULL AND state != ''
              AND (latitude IS NULL OR longitude IS NULL OR latitude=0 OR longitude=0)
            ORDER BY id
        """).fetchall()
    
    conn.close()
    
    records = [(r[0], r[1], r[2], r[3], r[4]) for r in rows if r[0] not in checkpoint]
    
    if args.quick_test:
        records = records[:args.quick_test]
    
    print(f"Records to geocode: {len(records):,}")
    if args.dry_run or not records:
        return
    
    total_matched = 0
    total_nomatch = 0
    total_errors = 0
    start = time.time()
    
    for i in range(0, len(records), args.batch_size):
        batch = records[i:i+args.batch_size]
        csv_body = build_csv(batch)
        
        batch_start = time.time()
        results = send_batch(csv_body)
        batch_time = time.time() - batch_start
        
        matched_ids = set()
        updates = []
        for ch_id, rec in results.items():
            updates.append((rec['lat'], rec['lon'], ch_id))
            matched_ids.add(ch_id)
        
        # Write to DB
        if updates:
            conn2 = sqlite3.connect(str(DB_PATH))
            conn2.execute("PRAGMA journal_mode=WAL")
            conn2.executemany(
                "UPDATE churches SET latitude=?, longitude=?, geocode_source='census_batch' WHERE id=?",
                updates
            )
            conn2.commit()
            conn2.close()
            save_checkpoint(matched_ids)
        
        batch_matched = len(results)
        batch_nomatch = len(batch) - batch_matched
        total_matched += batch_matched
        total_nomatch += batch_nomatch
        
        batch_num = i // args.batch_size + 1
        total_batches = (len(records) + args.batch_size - 1) // args.batch_size
        elapsed = time.time() - start
        rate = (i + len(batch)) / elapsed if elapsed > 0 else 0
        
        print(f"  Batch {batch_num}/{total_batches}: {len(batch):,} addr → "
              f"{batch_matched} matched, {batch_nomatch} no-match "
              f"({batch_time:.1f}s) | Running: {total_matched:,} matched, "
              f"{rate:.0f}/s")
        
        time.sleep(1)  # Be polite
    
    total_time = time.time() - start
    print(f"\n{'='*60}")
    print(f"DONE: {len(records):,} processed in {total_time:.0f}s ({total_time/60:.1f} min)")
    print(f"  Matched:  {total_matched:,}")
    print(f"  No match: {total_nomatch:,}")
    print(f"  Errors:   {total_errors:,}")


if __name__ == '__main__':
    main()
