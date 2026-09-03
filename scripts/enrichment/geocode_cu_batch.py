"""Batch geocode ChurchUnion rows via Census batch API (1000/request, one at a time)."""
import csv, io, os, sqlite3, time, urllib.request, json
from datetime import datetime

DB = "E:/grid/churches.db"
CENSUS_BATCH = "https://geocoding.geo.census.gov/geocoder/geographies/addressbatch"
CHUNK = 500
CK_FILE = "E:/grid/data/geocode_cu_checkpoint.json"
TEMP = "E:/grid/data/geocode_cu_batch.csv"

def load_ck():
    if os.path.exists(CK_FILE):
        return json.load(open(CK_FILE))
    return {"batches": 0, "geocoded": 0}

def save_ck(batches, geocoded):
    with open(CK_FILE, "w") as f:
        json.dump({"batches": batches, "geocoded": geocoded, "last": datetime.utcnow().isoformat()}, f)

def upload(csv_text):
    boundary = "----CensusGeocoderBoundary7MA4YWxk"
    body = (
        f"--{boundary}\r\n"
        'Content-Disposition: form-data; name="addressFile"; filename="batch.csv"\r\n'
        "Content-Type: text/csv\r\n\r\n"
    ).encode("utf-8") + csv_text.encode("utf-8") + (
        f"\r\n--{boundary}\r\n"
        'Content-Disposition: form-data; name="benchmark"\r\n\r\n'
        "Public_AR_Current\r\n"
        f"--{boundary}\r\n"
        'Content-Disposition: form-data; name="vintage"\r\n\r\n'
        "Current_Current\r\n"
        f"--{boundary}\r\n"
        'Content-Disposition: form-data; name="layers"\r\n\r\n'
        "2020\r\n"
        f"--{boundary}--\r\n"
    ).encode("utf-8")
    req = urllib.request.Request(CENSUS_BATCH, data=body,
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"}, method="POST")
    with urllib.request.urlopen(req, timeout=120) as resp:
        return resp.read().decode("utf-8", errors="replace")

def parse_results(csv_text):
    """Returns {id: {lat, lng, tract_fips}} for matched rows."""
    results = {}
    for row in csv.reader(io.StringIO(csv_text)):
        if len(row) < 6 or row[0].strip('"') == "id":
            continue
        if row[2].strip('"') != "Match":
            continue
        try:
            uid = int(row[0].strip('"'))
        except ValueError:
            continue
        coords = row[5].strip('"')
        if not coords or "," not in coords:
            continue
        try:
            lng, lat = map(float, coords.split(",")[:2])
        except ValueError:
            continue
        tract = ""
        if len(row) >= 11:
            st = row[8].strip('"')
            co = row[9].strip('"')
            tr = row[10].strip('"')
            if st and co and tr:
                tract = f"{st}{co}{tr}"
        results[uid] = {"lat": lat, "lng": lng, "tract": tract}
    return results

def main():
    ck = load_ck()
    db = sqlite3.connect(DB, timeout=60)
    
    rows = db.execute("""
        SELECT id, address, city, state, zip FROM churches 
        WHERE source='churchunion_scraper' AND (latitude IS NULL OR latitude=0)
        ORDER BY id
    """).fetchall()
    total = len(rows)
    print(f"ChurchUnion rows to geocode: {total:,}", flush=True)
    
    if ck["batches"] > 0:
        skip = ck["batches"] * CHUNK
        rows = rows[skip:]
        print(f"  Resuming from batch {ck['batches']} ({ck['geocoded']:,} already geocoded)", flush=True)
    
    batches = [rows[i:i+CHUNK] for i in range(0, len(rows), CHUNK)]
    geocoded = ck["geocoded"]
    t0 = time.time()
    
    for bi, batch in enumerate(batches):
        bn = ck["batches"] + bi + 1
        
        # Build CSV in memory
        csv_buf = io.StringIO()
        w = csv.writer(csv_buf)
        w.writerow(["id", "address", "city", "state", "zip"])
        for r in batch:
            w.writerow([r[0], r[1], r[2], r[3], r[4] or ""])
        csv_text = csv_buf.getvalue()
        
        try:
            result_csv = upload(csv_text)
            matches = parse_results(result_csv)
        except Exception as e:
            print(f"  Batch {bn}: ERROR {e}", flush=True)
            time.sleep(2)
            continue
        
        matched_ids = set(matches.keys())
        for uid, data in matches.items():
            db.execute("""
                UPDATE churches SET latitude=?, longitude=?, tract_fips=?,
                    geocode_source='census_batch', tract_geocode_source='census_batch',
                    tract_geocode_date=?
                WHERE id=?
            """, (data["lat"], data["lng"], data["tract"], datetime.utcnow().strftime("%Y-%m-%d"), uid))
        
        now = datetime.utcnow().isoformat()
        for r in batch:
            if r[0] not in matched_ids:
                db.execute("UPDATE churches SET geocode_attempts=COALESCE(geocode_attempts,0)+1, geocode_last_attempt=? WHERE id=?", (now, r[0]))
        
        db.commit()
        geocoded += len(matches)
        save_ck(bn, geocoded)
        
        elapsed = time.time() - t0
        done_rows = bn * CHUNK
        pct = min(done_rows / total * 100, 100)
        rate = done_rows / elapsed if elapsed > 0 else 0
        remaining = total - done_rows
        eta = remaining / rate if rate > 0 else 0
        print(f"  Batch {bn}/{len(batches)+ck['batches']}: {len(matches)}/{len(batch)} matched | Total: {geocoded:,} | ETA {eta/60:.0f}m", flush=True)
        
        time.sleep(0.5)
    
    elapsed = time.time() - t0
    print(f"\nDone: {geocoded:,}/{total:,} geocoded in {elapsed/60:.1f}m", flush=True)
    
    still = db.execute("SELECT COUNT(1) FROM churches WHERE source='churchunion_scraper' AND (latitude IS NULL OR latitude=0)").fetchone()[0]
    print(f"Still ungeocoded: {still:,}", flush=True)
    db.close()
    
    if os.path.exists(TEMP):
        os.remove(TEMP)

if __name__ == "__main__":
    main()
