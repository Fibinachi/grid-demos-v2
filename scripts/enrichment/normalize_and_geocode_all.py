"""Normalize ALL ungeocoded church addresses across all sources. Then re-geocode."""
import csv, io, sqlite3, re, time, urllib.request
from datetime import datetime
import pandas as pd

DB = "E:/grid/churches.db"
BATCH_URL = "https://geocoding.geo.census.gov/geocoder/geographies/addressbatch"
SIZE = 500
TODAY = datetime.utcnow().strftime("%Y-%m-%d")
NOW = datetime.utcnow().isoformat()
t0 = time.time()

# State name → abbreviation
STATE_MAP = {
    'ALABAMA':'AL','ALASKA':'AK','ARIZONA':'AZ','ARKANSAS':'AR','CALIFORNIA':'CA',
    'COLORADO':'CO','CONNECTICUT':'CT','DELAWARE':'DE','FLORIDA':'FL','GEORGIA':'GA',
    'HAWAII':'HI','IDAHO':'ID','ILLINOIS':'IL','INDIANA':'IN','IOWA':'IA',
    'KANSAS':'KS','KENTUCKY':'KY','LOUISIANA':'LA','MAINE':'ME','MARYLAND':'MD',
    'MASSACHUSETTS':'MA','MICHIGAN':'MI','MINNESOTA':'MN','MISSISSIPPI':'MS',
    'MISSOURI':'MO','MONTANA':'MT','NEBRASKA':'NE','NEVADA':'NV','NEW HAMPSHIRE':'NH',
    'NEW JERSEY':'NJ','NEW MEXICO':'NM','NEW YORK':'NY','NORTH CAROLINA':'NC',
    'NORTH DAKOTA':'ND','OHIO':'OH','OKLAHOMA':'OK','OREGON':'OR',
    'PENNSYLVANIA':'PA','RHODE ISLAND':'RI','SOUTH CAROLINA':'SC','SOUTH DAKOTA':'SD',
    'TENNESSEE':'TN','TEXAS':'TX','UTAH':'UT','VERMONT':'VT','VIRGINIA':'VA',
    'WASHINGTON':'WA','WEST VIRGINIA':'WV','WISCONSIN':'WI','WYOMING':'WY',
    'DISTRICT OF COLUMBIA':'DC','PUERTO RICO':'PR','GUAM':'GU',
}

def log(msg):
    print(f"[{time.time()-t0:6.1f}s] {msg}", flush=True)

# ── 1. Load & Normalize ──
log("Loading ungeocoded rows...")
db = sqlite3.connect(DB)
df = pd.read_sql_query("""
    SELECT id, name, address, city, state, zip
    FROM churches 
    WHERE (latitude IS NULL OR latitude = 0)
      AND address IS NOT NULL AND address != ''
    ORDER BY id
""", db)
db.close()
log(f"  {len(df):,} rows")

# State name normalization
df["state"] = df["state"].str.strip().str.upper().map(STATE_MAP).fillna(df["state"])
# Clean "None" strings
df["zip"] = df["zip"].apply(lambda z: "" if str(z).strip().upper() == "NONE" else (str(z) if str(z) != "nan" else ""))
df["city"] = df["city"].apply(lambda c: "" if str(c).strip().upper() == "NONE" else str(c))

# Normalize addresses — more flexible patterns
zip_re = re.compile(r',\s*([A-Z]{2})\s+(\d{5}(?:-\d{4})?)\s*(?:,\s*(?:United States|USA|Canada|US))?\s*$')
# Also match ZIP embedded mid-address like "addr city, ST 12345 more text"
zip_re_mid = re.compile(r',\s*([A-Z]{2})\s+(\d{5}(?:-\d{4})?)(?:\s*,|\s*$)')
country_re = re.compile(r',?\s*(?:United States|USA|Canada|US)\s*$', re.IGNORECASE)

fixed_addr = 0
fixed_zip = 0
fixed_state = 0

new_addresses = []
new_zips = []
new_states = []

for _, row in df.iterrows():
    addr = str(row["address"] or "").strip()
    city = str(row["city"] or "").strip()
    state = str(row["state"] or "").strip()
    zp = str(row["zip"] or "").strip()
    
    # Skip NaN IDs
    if str(row["id"]) == "nan" or str(row["id"]) == "None":
        new_addresses.append(addr)
        new_zips.append(zp)
        new_states.append(state)
        continue
    
    # Strip country suffix first
    addr = country_re.sub("", addr).strip().rstrip(",").strip()
    
    # Try end-of-string ZIP pattern
    m = zip_re.search(addr)
    if not m:
        m = zip_re_mid.search(addr)
    
    if m:
        st, extracted_zip = m.group(1), m.group(2)
        addr = addr[:m.start()].strip().rstrip(",").strip()
        if not zp or zp == "" or zp.upper() == "NONE":
            zp = extracted_zip
            fixed_zip += 1
        if not state or state == "" or state.upper() in STATE_MAP:
            state = st
            fixed_state += 1
    
    if addr != str(row["address"] or "").strip():
        fixed_addr += 1
    
    new_addresses.append(addr)
    new_zips.append(zp)
    new_states.append(state)

df["address"] = new_addresses
df["zip"] = new_zips
df["state"] = new_states

# Drop NaN IDs
df = df[df["id"].notna() & (df["id"] != "None")]
df["id"] = df["id"].astype("Int64")

log(f"  Fixed address: {fixed_addr:,}  ZIP: {fixed_zip:,}  State: {fixed_state:,}  Valid rows: {len(df):,}")

# ── 2. Write normalization back ──
log("Writing normalized addresses...")
db = sqlite3.connect(DB)
db.execute("PRAGMA synchronous=OFF")
changed = df[["id", "address", "city", "state", "zip"]].copy()
changed["id"] = changed["id"].astype("Int64")  # nullable int
changed.to_sql("_norm_all", db, if_exists="replace", index=False)
db.execute("CREATE INDEX _norm_all_idx ON _norm_all(id)")
db.execute("""
    UPDATE churches SET 
        address = COALESCE(t.address, churches.address),
        city = COALESCE(t.city, churches.city),
        state = COALESCE(t.state, churches.state),
        zip = COALESCE(t.zip, churches.zip)
    FROM _norm_all AS t WHERE churches.id = t.id
""")
db.execute("DROP TABLE _norm_all")
log(f"  Written ({time.time()-t0:.1f}s)")

# ── 3. Batch geocode ──
log("Batch geocoding...")
rows = [(int(r["id"]), r["address"], r["city"], r["state"], r["zip"]) for _, r in df.iterrows()]
total = len(rows)
batches = [rows[i:i+SIZE] for i in range(0, total, SIZE)]
geocoded = 0

with open("E:/grid/data/all_geo_norm.csv", "w", newline="", encoding="utf-8") as outf:
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
            if bi % 10 == 0: log(f"  Batch {bi+1}: ERROR {e}")
            for r in batch: w.writerow([r[0], "", "", "", "upload_error"])
            continue
        
        batch_geo = 0
        matched_ids = set()
        for row in csv.reader(io.StringIO(result)):
            if len(row) < 2 or row[0].strip('"') == "id": continue
            status = row[2].strip('"') if len(row) >= 3 else "No_Match"
            if status != "Match": continue
            if len(row) < 6: continue
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
        if (bi+1) % 5 == 0 or bi == len(batches)-1:
            elapsed = time.time()-t0
            done = (bi+1)*SIZE
            rate = done/elapsed if elapsed>0 else 0
            eta = (total-done)/rate if rate>0 else 0
            log(f"  Batch {bi+1}/{len(batches)}: {batch_geo}/{len(batch)} | {geocoded:,} total | ETA {eta/60:.0f}m")
        time.sleep(0.2)

log(f"Geocoded: {geocoded:,}/{total:,}")

# ── 4. Import results ──
log("Importing results...")
df_res = pd.read_csv("E:/grid/data/all_geo_norm.csv")
matches = df_res[df_res["status"] == "match"]
no_match = df_res[df_res["status"] == "no_match"]

if len(matches) > 0:
    m = matches[["id","latitude","longitude","tract_fips"]].copy()
    m.to_sql("_all_geo2", db, if_exists="replace", index=False)
    db.execute("CREATE INDEX _all_geo2_idx ON _all_geo2(id)")
    db.execute("""
        UPDATE churches SET 
            latitude = COALESCE(t.latitude, churches.latitude),
            longitude = COALESCE(t.longitude, churches.longitude),
            tract_fips = COALESCE(t.tract_fips, churches.tract_fips),
            geocode_source = 'census_batch',
            tract_geocode_source = 'census_batch',
            tract_geocode_date = ?
        FROM _all_geo2 AS t WHERE churches.id = t.id
    """, (TODAY,))
    db.execute("DROP TABLE _all_geo2")
    log(f"  {len(matches):,} geocoded")

if len(no_match) > 0:
    nm = no_match[["id"]].copy()
    nm.to_sql("_all_no2", db, if_exists="replace", index=False)
    db.execute("CREATE INDEX _all_no2_idx ON _all_no2(id)")
    db.execute("""
        UPDATE churches SET 
            geocode_attempts = COALESCE(geocode_attempts,0) + 1,
            geocode_last_attempt = ?
        FROM _all_no2 AS t WHERE churches.id = t.id
    """, (TODAY,))
    db.execute("DROP TABLE _all_no2")
    log(f"  {len(no_match):,} marked no_match")

# Provenance
db.execute("""
    INSERT INTO provenance_log 
    (source, script_name, started_at, completed_at, churches_updated,
     churches_inserted, fields_populated, status, notes)
    VALUES (?, ?, ?, ?, 0, ?, 'completed', ?)
""", ("addr_normalization", "normalize_all_addresses.py", TODAY, TODAY,
      "address,city,state,zip",
      f"Normalized addresses for all ungeocoded rows: {fixed_addr} address, {fixed_zip} ZIP, {fixed_state} state, {fixed_city_state} city"))
db.execute("""
    INSERT INTO provenance_log 
    (source, script_name, started_at, completed_at, churches_updated,
     churches_inserted, fields_populated, status, notes)
    VALUES (?, ?, ?, ?, 0, ?, 'completed', ?)
""", ("census_batch_all2", "geocode_all_normalized.py", TODAY, TODAY,
      "latitude,longitude,tract_fips",
      f"Batch geocoded all ungeocoded normalized addresses. {len(matches)}/{total} matched."))

db.commit()
db.close()

# Final stats
db = sqlite3.connect(DB)
t = db.execute("SELECT COUNT(1) FROM churches").fetchone()[0]
g = db.execute("SELECT COUNT(1) FROM churches WHERE latitude IS NOT NULL AND latitude!=0").fetchone()[0]
n = db.execute("SELECT COUNT(1) FROM churches WHERE latitude IS NULL OR latitude=0").fetchone()[0]
db.close()
log(f"\nDONE: {t:,} total | {g:,} geocoded ({g*100/t:.0f}%) | {n:,} remain")
