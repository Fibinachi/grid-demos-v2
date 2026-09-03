"""One-shot: Batch geocode all ChurchUnion rows. 500/batch, Census batch API."""
import csv, io, sqlite3, time, urllib.request
from datetime import datetime

DB = "E:/grid/churches.db"
BATCH = "https://geocoding.geo.census.gov/geocoder/geographies/addressbatch"
SIZE = 500

db = sqlite3.connect(DB, timeout=60)
rows = db.execute("SELECT id, address, city, state, zip FROM churches WHERE source='churchunion_scraper' AND (latitude IS NULL OR latitude=0) ORDER BY id").fetchall()
total = len(rows)
batches = [rows[i:i+SIZE] for i in range(0, len(rows), SIZE)]
print(f"Rows to geocode: {total:,}", flush=True)
print(f"  {len(batches)} batches of {SIZE}", flush=True)

# Progress file for visibility
PROGRESS_FILE = "E:/grid/data/geocode_cu_progress.txt"
geocoded = 0
t0 = time.time()

for bi, batch in enumerate(batches):
    # Build CSV
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["id", "address", "city", "state", "zip"])
    for r in batch:
        w.writerow([r[0], r[1], r[2], r[3], r[4] or ""])
    csv_text = buf.getvalue()
    
    # Upload
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
    
    try:
        req = urllib.request.Request(BATCH, data=body,
            headers={"Content-Type": f"multipart/form-data; boundary={boundary}"}, method="POST")
        with urllib.request.urlopen(req, timeout=60) as resp:
            result = resp.read().decode("utf-8", errors="replace")
    except Exception as e:
        print(f"  Batch {bi+1}/{len(batches)}: UPLOAD ERROR: {e}", flush=True)
        time.sleep(2)
        continue
    
    # Parse matches
    matches = {}
    for row in csv.reader(io.StringIO(result)):
        if len(row) < 6 or row[0].strip('"') == "id":
            continue
        if row[2].strip('"') != "Match":
            continue
        try:
            uid = int(row[0].strip('"'))
            coords = row[5].strip('"')
            if coords and "," in coords:
                lng, lat = map(float, coords.split(",")[:2])
                tract = ""
                if len(row) >= 11:
                    st = row[8].strip('"')
                    co = row[9].strip('"')
                    tr = row[10].strip('"')
                    if st and co and tr:
                        tract = f"{st}{co}{tr}"
                matches[uid] = (lat, lng, tract)
        except (ValueError, IndexError):
            continue
    
    # Update DB
    for uid, (lat, lng, tract) in matches.items():
        db.execute("UPDATE churches SET latitude=?, longitude=?, tract_fips=?, geocode_source='census_batch', tract_geocode_source='census_batch', tract_geocode_date=? WHERE id=?",
                  (lat, lng, tract, datetime.utcnow().strftime("%Y-%m-%d"), uid))
    db.commit()
    geocoded += len(matches)
    
    elapsed = time.time() - t0
    done = (bi + 1) * SIZE
    rate = done / elapsed if elapsed > 0 else 0
    eta = (total - done) / rate if rate > 0 else 0
    print(f"  Batch {bi+1}/{len(batches)}: {len(matches)}/{len(batch)} ok | Total: {geocoded:,} | {rate:.0f}/s | ETA {eta/60:.0f}m", flush=True)
    # Also write to file for visibility
    with open(PROGRESS_FILE, "w") as pf:
        pf.write(f"Batch {bi+1}/{len(batches)}: {len(matches)}/{len(batch)} ok | Total: {geocoded:,}/{total} | {rate:.0f}/s | ETA {eta/60:.0f}m\n")
    time.sleep(0.3)

elapsed = time.time() - t0
print(f"\nDone: {geocoded:,}/{total:,} in {elapsed/60:.1f}m", flush=True)
still = db.execute("SELECT COUNT(1) FROM churches WHERE source='churchunion_scraper' AND (latitude IS NULL OR latitude=0)").fetchone()[0]
print(f"Still ungeocoded: {still:,}", flush=True)
db.close()
