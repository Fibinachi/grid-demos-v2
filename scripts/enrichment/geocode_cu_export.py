"""Export ungeocoded ChurchUnion rows to CSV, geocode via batch API, write results CSV."""
import csv, io, sqlite3, time, urllib.request, os

DB = "E:/grid/churches.db"
OUT = "E:/grid/data/cu_ungeocoded.csv"
RES = "E:/grid/data/cu_geocoded_results.csv"
SIZE = 500

# Step 1: Export
print("Exporting ungeocoded rows...", flush=True)
db = sqlite3.connect(DB)
rows = db.execute("SELECT id, address, city, state, zip FROM churches WHERE source='churchunion_scraper' AND (latitude IS NULL OR latitude=0) ORDER BY id").fetchall()
db.close()

with open(OUT, "w", newline="", encoding="utf-8") as f:
    w = csv.writer(f)
    w.writerow(["id", "address", "city", "state", "zip"])
    for r in rows:
        w.writerow([r[0], r[1], r[2], r[3], r[4] or ""])
print(f"  Exported {len(rows):,} rows to {OUT}", flush=True)

# Step 2: Read back and geocode in batches
print("Geocoding via Census batch API...", flush=True)
BATCH_URL = "https://geocoding.geo.census.gov/geocoder/geographies/addressbatch"

with open(RES, "w", newline="", encoding="utf-8") as outf:
    w = csv.writer(outf)
    w.writerow(["id", "latitude", "longitude", "tract_fips", "status"])
    
    with open(OUT, encoding="utf-8") as inf:
        reader = list(csv.DictReader(inf))
    
    batches = [reader[i:i+SIZE] for i in range(0, len(reader), SIZE)]
    t0 = time.time()
    geocoded = 0
    
    for bi, batch in enumerate(batches):
        # Build CSV for upload
        buf = io.StringIO()
        cw = csv.writer(buf)
        cw.writerow(["id", "address", "city", "state", "zip"])
        for r in batch:
            cw.writerow([r["id"], r["address"], r["city"], r["state"], r["zip"]])
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
            req = urllib.request.Request(BATCH_URL, data=body,
                headers={"Content-Type": f"multipart/form-data; boundary={boundary}"}, method="POST")
            with urllib.request.urlopen(req, timeout=60) as resp:
                result = resp.read().decode("utf-8", errors="replace")
        except Exception as e:
            print(f"  Batch {bi+1}: UPLOAD ERROR: {e}", flush=True)
            for r in batch:
                w.writerow([r["id"], "", "", "", "upload_error"])
            continue
        
        # Parse and write results
        batch_geo = 0
        matched_ids = set()
        for row in csv.reader(io.StringIO(result)):
            if len(row) < 6 or row[0].strip('"') == "id":
                continue
            try:
                uid = int(row[0].strip('"'))
            except ValueError:
                continue
            if row[2].strip('"') == "Match":
                coords = row[5].strip('"')
                if coords and "," in coords:
                    try:
                        lng, lat = map(float, coords.split(",")[:2])
                    except ValueError:
                        w.writerow([uid, "", "", "", "parse_error"])
                        continue
                    tract = ""
                    if len(row) >= 11:
                        st = row[8].strip('"')
                        co = row[9].strip('"')
                        tr = row[10].strip('"')
                        if st and co and tr:
                            tract = f"{st}{co}{tr}"
                    w.writerow([uid, lat, lng, tract, "match"])
                    matched_ids.add(uid)
                    batch_geo += 1
                    geocoded += 1
            # else: No_Match - skip (will be handled below)
        
        # Write no_match for unmatched
        for r in batch:
            if int(r["id"]) not in matched_ids:
                w.writerow([r["id"], "", "", "", "no_match"])
        
        elapsed = time.time() - t0
        done = (bi + 1) * SIZE
        rate = done / elapsed if elapsed > 0 else 0
        eta = (len(reader) - done) / rate if rate > 0 else 0
        print(f"  Batch {bi+1}/{len(batches)}: {batch_geo}/{len(batch)} matched | {geocoded:,} total | {rate:.0f}/s | ETA {eta/60:.0f}m", flush=True)
        time.sleep(0.2)

elapsed = time.time() - t0
print(f"\nDone: {geocoded:,} geocoded in {elapsed/60:.1f}m", flush=True)
print(f"Results: {RES}", flush=True)
