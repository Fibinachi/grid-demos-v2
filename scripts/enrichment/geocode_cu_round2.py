"""Re-geocode remaining 15K ChurchUnion rows with cleaned addresses."""
import csv, io, sqlite3, time, urllib.request, sys
from datetime import datetime

DB = "E:/grid/churches.db"
BATCH_URL = "https://geocoding.geo.census.gov/geocoder/geographies/addressbatch"
SIZE = 500
RESULTS = "E:/grid/data/cu_geocode_round2.csv"

t0 = time.time()

# 1. Export (DB closed immediately)
print("Exporting ungeocoded rows...", flush=True)
db = sqlite3.connect(DB)
rows = db.execute("""
    SELECT id, address, city, state, zip FROM churches 
    WHERE source='churchunion_scraper' AND (latitude IS NULL OR latitude=0)
    ORDER BY id
""").fetchall()
db.close()
total = len(rows)
print(f"  {total:,} rows ({time.time()-t0:.1f}s)", flush=True)

# 2. Geocode via batch API
batches = [rows[i:i+SIZE] for i in range(0, len(rows), SIZE)]
geocoded = 0

with open(RESULTS, "w", newline="", encoding="utf-8") as outf:
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
            print(f"  Batch {bi+1}: ERROR {e}", flush=True)
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
        elapsed = time.time() - t0
        done = (bi+1)*SIZE
        rate = done/elapsed if elapsed > 0 else 0
        eta = (total-done)/rate if rate > 0 else 0
        print(f"  Batch {bi+1}/{len(batches)}: {batch_geo}/{len(batch)} matched | {geocoded:,} total | {rate:.0f}/s | ETA {eta/60:.0f}m", flush=True)
        time.sleep(0.3)

elapsed = time.time() - t0
print(f"\nGeocoded: {geocoded:,}/{total:,} in {elapsed/60:.1f}m", flush=True)
print(f"Results: {RESULTS}", flush=True)

# 3. Import results via load-memory-write-sql
if geocoded > 0:
    print("\nImporting results to DB...", flush=True)
    import pandas as pd
    df = pd.read_csv(RESULTS)
    matches = df[df["status"] == "match"]
    no_match = df[df["status"] == "no_match"]
    
    db = sqlite3.connect(DB)
    db.execute("PRAGMA synchronous=OFF")
    
    # Matches
    if len(matches) > 0:
        m = matches[["id","latitude","longitude","tract_fips"]].copy()
        m.to_sql("_cu_geo_r2", db, if_exists="replace", index=False)
        db.execute("CREATE INDEX _cu_geo_r2_idx ON _cu_geo_r2(id)")
        db.execute("""
            UPDATE churches SET 
                latitude = COALESCE(t.latitude, churches.latitude),
                longitude = COALESCE(t.longitude, churches.longitude),
                tract_fips = COALESCE(t.tract_fips, churches.tract_fips),
                geocode_source = 'census_batch',
                tract_geocode_source = 'census_batch',
                tract_geocode_date = '2026-06-17'
            FROM _cu_geo_r2 AS t WHERE churches.id = t.id
        """)
        db.execute("DROP TABLE _cu_geo_r2")
    
    # No match
    if len(no_match) > 0:
        nm = no_match[["id"]].copy()
        nm.to_sql("_cu_no_r2", db, if_exists="replace", index=False)
        db.execute("CREATE INDEX _cu_no_r2_idx ON _cu_no_r2(id)")
        db.execute("""
            UPDATE churches SET 
                geocode_attempts = COALESCE(geocode_attempts,0) + 1,
                geocode_last_attempt = '2026-06-17'
            FROM _cu_no_r2 AS t WHERE churches.id = t.id
        """)
        db.execute("DROP TABLE _cu_no_r2")
    
    # Provenance
    db.execute("""
        INSERT INTO provenance_log 
        (source, script_name, started_at, completed_at, churches_updated,
         churches_inserted, fields_populated, status, notes)
        VALUES ('census_batch_r2', 'geocode_cu_round2.py', ?, ?, ?,
                0, 'latitude,longitude,tract_fips', 'completed', ?)
    """, (datetime.utcnow().strftime("%Y-%m-%d"), datetime.utcnow().strftime("%Y-%m-%d"),
          len(matches), f"Round 2 batch geocode of ChurchUnion rows (cleaned addresses). {len(matches)}/{total} matched."))
    
    db.commit()
    db.close()
    print(f"  Imported: {len(matches):,} matched, {len(no_match):,} no_match", flush=True)

# 4. Final status
db = sqlite3.connect(DB)
total_cu = db.execute("SELECT COUNT(1) FROM churches WHERE source='churchunion_scraper'").fetchone()[0]
geo_cu = db.execute("SELECT COUNT(1) FROM churches WHERE source='churchunion_scraper' AND latitude IS NOT NULL AND latitude!=0").fetchone()[0]
need_cu = db.execute("SELECT COUNT(1) FROM churches WHERE source='churchunion_scraper' AND (latitude IS NULL OR latitude=0)").fetchone()[0]
db.close()
print(f"\nChurchUnion: {total_cu:,} total | {geo_cu:,} geocoded ({geo_cu*100/total_cu:.0f}%) | {need_cu:,} remain")
