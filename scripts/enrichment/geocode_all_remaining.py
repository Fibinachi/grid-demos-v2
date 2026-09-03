"""Batch geocode ALL ungeocoded churches with addresses. Same proven pipeline as ChurchUnion rounds."""
import csv, io, sqlite3, time, urllib.request
from datetime import datetime
import pandas as pd

DB = "E:/grid/churches.db"
BATCH_URL = "https://geocoding.geo.census.gov/geocoder/geographies/addressbatch"
SIZE = 500
TODAY = datetime.utcnow().strftime("%Y-%m-%d")
NOW = datetime.utcnow().isoformat()
t0 = time.time()

def log(msg):
    print(f"[{time.time()-t0:6.1f}s] {msg}", flush=True)

# 1. Export
log("Exporting ungeocoded rows with addresses...")
db = sqlite3.connect(DB)
rows = db.execute("""
    SELECT id, address, city, state, zip FROM churches 
    WHERE (latitude IS NULL OR latitude = 0)
      AND address IS NOT NULL AND address != ''
    ORDER BY id
""").fetchall()
db.close()
total = len(rows)
log(f"  {total:,} rows")

# 2. Batch geocode
batches = [rows[i:i+SIZE] for i in range(0, len(rows), SIZE)]
geocoded = 0

with open("E:/grid/data/all_geocode_results.csv", "w", newline="", encoding="utf-8") as outf:
    w = csv.writer(outf)
    w.writerow(["id", "latitude", "longitude", "tract_fips", "status"])
    
    for bi, batch in enumerate(batches):
        buf = io.StringIO()
        cw = csv.writer(buf)
        cw.writerow(["id", "address", "city", "state", "zip"])
        for r in batch:
            cw.writerow([r[0], r[1], r[2], r[3], r[4] or ""])
        
        boundary = "----CensusGeocoderBoundary7MA4YWxk"
        body = (
            f"--{boundary}\r\n"
            'Content-Disposition: form-data; name="addressFile"; filename="batch.csv"\r\n'
            "Content-Type: text/csv\r\n\r\n"
        ).encode("utf-8") + buf.getvalue().encode("utf-8") + (
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
            log(f"  Batch {bi+1}: ERROR {e}")
            for r in batch:
                w.writerow([r[0], "", "", "", "upload_error"])
            continue
        
        batch_geo = 0
        matched_ids = set()
        for row in csv.reader(io.StringIO(result)):
            if len(row) < 6 or row[0].strip('"') == "id":
                continue
            if row[2].strip('"') != "Match":
                continue
            try: uid = int(row[0].strip('"'))
            except: continue
            coords = row[5].strip('"')
            if not coords or "," not in coords: continue
            try: lng, lat = map(float, coords.split(",")[:2])
            except: continue
            tract = ""
            if len(row) >= 11:
                s,c,t = row[8].strip('"'),row[9].strip('"'),row[10].strip('"')
                if s and c and t: tract = f"{s}{c}{t}"
            w.writerow([uid, lat, lng, tract, "match"])
            matched_ids.add(uid)
            batch_geo += 1
        
        for r in batch:
            if r[0] not in matched_ids:
                w.writerow([r[0], "", "", "", "no_match"])
        
        geocoded += batch_geo
        elapsed = time.time()-t0
        done = (bi+1)*SIZE
        rate = done/elapsed if elapsed>0 else 0
        eta = (total-done)/rate if rate>0 else 0
        log(f"  Batch {bi+1}/{len(batches)}: {batch_geo}/{len(batch)} | {geocoded:,} total | ETA {eta/60:.0f}m")
        time.sleep(0.3)

log(f"Geocoded: {geocoded:,}/{total:,} in {elapsed/60:.1f}m")

# 3. Import via pandas + temp table + UPDATE FROM
log("Importing results...")
df = pd.read_csv("E:/grid/data/all_geocode_results.csv")
matches = df[df["status"] == "match"]
no_match = df[df["status"] == "no_match"]

db = sqlite3.connect(DB)
db.execute("PRAGMA synchronous=OFF")

if len(matches) > 0:
    m = matches[["id","latitude","longitude","tract_fips"]].copy()
    m.to_sql("_all_geo", db, if_exists="replace", index=False)
    db.execute("CREATE INDEX _all_geo_idx ON _all_geo(id)")
    db.execute("""
        UPDATE churches SET 
            latitude = COALESCE(t.latitude, churches.latitude),
            longitude = COALESCE(t.longitude, churches.longitude),
            tract_fips = COALESCE(t.tract_fips, churches.tract_fips),
            geocode_source = 'census_batch',
            tract_geocode_source = 'census_batch',
            tract_geocode_date = ?
        FROM _all_geo AS t WHERE churches.id = t.id
    """, (TODAY,))
    db.execute("DROP TABLE _all_geo")
    log(f"  {len(matches):,} geocoded")

if len(no_match) > 0:
    nm = no_match[["id"]].copy()
    nm.to_sql("_all_no", db, if_exists="replace", index=False)
    db.execute("CREATE INDEX _all_no_idx ON _all_no(id)")
    db.execute("""
        UPDATE churches SET 
            geocode_attempts = COALESCE(geocode_attempts,0) + 1,
            geocode_last_attempt = ?
        FROM _all_no AS t WHERE churches.id = t.id
    """, (TODAY,))
    db.execute("DROP TABLE _all_no")
    log(f"  {len(no_match):,} marked no_match")

# Provenance
db.execute("""
    INSERT INTO provenance_log 
    (source, script_name, started_at, completed_at, churches_updated,
     churches_inserted, fields_populated, status, notes)
    VALUES ('census_batch_all', 'geocode_all_remaining.py', ?, ?, ?,
            0, 'latitude,longitude,tract_fips', 'completed', ?)
""", (TODAY, TODAY, len(matches),
      f"Batch geocoded all ungeocoded churches with addresses. {len(matches)}/{total} matched."))

db.commit()
db.close()

# Final stats
db = sqlite3.connect(DB)
t = db.execute("SELECT COUNT(1) FROM churches").fetchone()[0]
g = db.execute("SELECT COUNT(1) FROM churches WHERE latitude IS NOT NULL AND latitude!=0").fetchone()[0]
n = db.execute("SELECT COUNT(1) FROM churches WHERE latitude IS NULL OR latitude=0").fetchone()[0]
db.close()
log(f"\nDONE: {t:,} total | {g:,} geocoded ({g*100/t:.0f}%) | {n:,} remain")
