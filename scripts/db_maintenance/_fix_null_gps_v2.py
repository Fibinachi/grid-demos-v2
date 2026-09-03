"""
Fix null GPS records using Census Geocoder (free, batch, accurate).

Strategy:
  1. Copy 94 existing lat/lon from church_addresses -> churches
  2. Census batch geocode all US records with street+city+state or city+state
  3. ZIP centroids for US records with only ZIP
  4. State centroids for US records with only state
  5. Non-US records: note for future (HERE/Nominatim)

Usage:
  python _fix_null_gps_v2.py --apply
  python _fix_null_gps_v2.py          (dry run/report)
"""
import csv
import io
import shutil
import sqlite3
import sys
import time
import urllib.request
from datetime import datetime

DB = 'E:/grid/churches.db'
ZCTA_PATH = 'E:/grid/data/Gaz_zcta_national.txt'
BATCH_URL = 'https://geocoding.geo.census.gov/geocoder/geographies/addressbatch'
CHUNK_SIZE = 500
t0 = time.time()
apply_fix = '--apply' in sys.argv


def progress_bar(current, total, start_time, extra=""):
    """Draw a progress bar with ETA."""
    cols = shutil.get_terminal_size().columns - 20
    bar_w = max(10, cols - 40)
    pct = current / total if total else 0
    filled = int(bar_w * pct)
    bar = '█' * filled + '░' * (bar_w - filled)
    elapsed = time.time() - start_time
    rate = current / elapsed if elapsed > 0 and current > 0 else 0
    if rate > 0 and current < total:
        eta = (total - current) / rate
        eta_str = f"{eta:.0f}s"
    else:
        eta_str = "done!"
    print(f"\r  {current:>7,}/{total:<7,} [{bar}] {pct:>5.1f}% | {rate:>,.0f} rec/s | ETA {eta_str} {extra}", end='', flush=True)


def log(msg):
    print(f"[{time.time()-t0:6.1f}s] {msg}", flush=True)

db = sqlite3.connect(DB)
db.execute("PRAGMA synchronous=OFF")

total_null = db.execute("SELECT COUNT(1) FROM churches WHERE latitude IS NULL AND longitude IS NULL").fetchone()[0]
print(f"Total null-GPS records: {total_null:,}")
print(f"Mode: {'APPLY' if apply_fix else 'DRY RUN'}")
print()

# ════════════════════════════════════════════════════════════════
# PHASE 1: Copy lat/lon from church_addresses -> churches
# ════════════════════════════════════════════════════════════════
print("=" * 60)
print("PHASE 1: Copy lat/lon from church_addresses")

p1_rows = db.execute("""
    SELECT DISTINCT c.rowid, c.id, ca.latitude, ca.longitude, ca.geocode_source
    FROM churches c
    JOIN church_addresses ca ON ca.church_rowid = c.rowid
    WHERE c.latitude IS NULL AND c.longitude IS NULL
    AND ca.latitude IS NOT NULL AND ca.longitude IS NOT NULL
""").fetchall()
print(f"  Records to copy: {len(p1_rows):,}")

if apply_fix and p1_rows:
    t_p1 = time.time()

    db.execute("""
        UPDATE churches SET
            latitude = ca.latitude,
            longitude = ca.longitude,
            geocode_source = COALESCE(ca.geocode_source, 'address_copy')
        FROM (
            SELECT DISTINCT ca.church_rowid, ca.latitude, ca.longitude, ca.geocode_source
            FROM church_addresses ca
            WHERE ca.latitude IS NOT NULL AND ca.longitude IS NOT NULL
        ) AS ca
        WHERE churches.rowid = ca.church_rowid
        AND churches.latitude IS NULL AND churches.longitude IS NULL
    """)

    now = datetime.now().isoformat()
    log_data = []
    for i, r in enumerate(p1_rows):
        cid = r[1] or r[0]
        log_data.append((cid, 'latitude', 'NULL', str(r[2]), 'address_copy', now))
        log_data.append((cid, 'longitude', 'NULL', str(r[3]), 'address_copy', now))
        progress_bar(i + 1, len(p1_rows), t_p1, "| logging provenance")
    print()

    db.executemany(
        "INSERT INTO enrichment_change_log (church_id, field_name, old_value, new_value, change_source, changed_at) VALUES (?, ?, ?, ?, ?, ?)",
        log_data
    )
    db.execute("INSERT OR IGNORE INTO provenance_log (source, action, timestamp, details) VALUES ('null_gps_fix', 'updated', ?, ?)",
               (now, f'Phase 1: copied lat/lon from church_addresses for {len(p1_rows)} records'))
    db.commit()
    print(f"  Copied {len(p1_rows):,} records. Provenance logged.")
elif not apply_fix:
    print("  (dry run)")

print()

# ════════════════════════════════════════════════════════════════
# PHASE 2: Census batch geocode US records with address data
# ════════════════════════════════════════════════════════════════
print("=" * 60)
print("PHASE 2: Census batch geocode (US records with address data)")

# Find records: need at minimum city+state, ideally street+city+state
# Build address string from churches.address or address_components
p2_export = db.execute("""
    WITH addr AS (
        SELECT c.rowid, c.id, c.name, c.country,
               COALESCE(NULLIF(c.address,''), '') AS addr,
               COALESCE(NULLIF(c.city,''), '') AS city,
               COALESCE(NULLIF(c.state,''), '') AS state,
               COALESCE(NULLIF(c.zip,''), '') AS zip
        FROM churches c
        WHERE c.latitude IS NULL AND c.longitude IS NULL
        AND c.country = 'US'
        AND (
            (c.address IS NOT NULL AND c.address != ''
             AND c.city IS NOT NULL AND c.city != ''
             AND c.state IS NOT NULL AND c.state != '')
            OR
            (c.city IS NOT NULL AND c.city != ''
             AND c.state IS NOT NULL AND c.state != '')
        )
    )
    SELECT rowid, id, addr, city, state, zip
    FROM addr
    ORDER BY rowid
""").fetchall()

print(f"  Records to batch geocode: {len(p2_export):,}")

if apply_fix and p2_export:
    num_batches = (len(p2_export) + CHUNK_SIZE - 1) // CHUNK_SIZE
    total_geocoded = 0
    geocoded_results = {}  # rowid -> (lat, lng)
    t_phase2 = time.time()

    for bi in range(num_batches):
        batch = p2_export[bi * CHUNK_SIZE:(bi + 1) * CHUNK_SIZE]

        buf = io.StringIO()
        cw = csv.writer(buf)
        cw.writerow(['id','address','city','state','zip'])
        for r in batch:
            addr = r[2] if r[2] else ''
            city = r[3] if r[3] else ''
            st = r[4] if r[4] else ''
            zp = r[5] if r[5] else ''
            cw.writerow([r[0], addr, city, st, zp])

        boundary = '----CensusGeocoderBoundary7MA4YWxk'
        body = (
            f'--{boundary}\r\n'
            'Content-Disposition: form-data; name="addressFile"; filename="batch.csv"\r\n'
            'Content-Type: text/csv\r\n\r\n'
        ).encode('utf-8') + buf.getvalue().encode('utf-8') + (
            f'\r\n--{boundary}\r\n'
            'Content-Disposition: form-data; name="benchmark"\r\n\r\n'
            'Public_AR_Current\r\n'
            f'--{boundary}\r\n'
            'Content-Disposition: form-data; name="vintage"\r\n\r\n'
            'Current_Current\r\n'
            f'--{boundary}--\r\n'
        ).encode('utf-8')

        try:
            req = urllib.request.Request(BATCH_URL, data=body,
                headers={'Content-Type': f'multipart/form-data; boundary={boundary}'},
                method='POST')
            with urllib.request.urlopen(req, timeout=60) as resp:
                result = resp.read().decode('utf-8', errors='replace')
        except Exception as e:
            progress_bar(bi + 1, num_batches, t_phase2, f"| ❌ ERROR: {e}")
            continue

        batch_geo = 0
        for row in csv.reader(io.StringIO(result)):
            if len(row) < 6 or row[0].strip('"') == 'id':
                continue
            if row[2].strip('"') != 'Match':
                continue
            try:
                uid = int(row[0].strip('"'))
            except ValueError:
                continue
            coords = row[5].strip('"')
            if not coords or ',' not in coords:
                continue
            try:
                lng, lat = map(float, coords.split(',')[:2])
            except ValueError:
                continue
            geocoded_results[uid] = (lat, lng)
            batch_geo += 1

        total_geocoded += batch_geo
        progress_bar(bi + 1, num_batches, t_phase2, f"| {total_geocoded:,} matched")
        time.sleep(0.3)

    print()

    # Batch update churches table
    if geocoded_results:
        now = datetime.now().isoformat()
        db.execute("DROP TABLE IF EXISTS _census_geo")
        db.execute("CREATE TEMP TABLE _census_geo (rowid INTEGER PRIMARY KEY, latitude REAL, longitude REAL)")
        geo_items = list(geocoded_results.items())
        t_p2insert = time.time()
        for i in range(0, len(geo_items), CHUNK_SIZE):
            chunk = geo_items[i:i + CHUNK_SIZE]
            db.executemany(
                "INSERT INTO _census_geo (rowid, latitude, longitude) VALUES (?, ?, ?)",
                [(rid, lat, lng) for rid, (lat, lng) in chunk]
            )
            progress_bar(min(i + CHUNK_SIZE, len(geo_items)), len(geo_items), t_p2insert, "| inserting temp")
        print()

        t_p2update = time.time()
        db.execute("""
            UPDATE churches SET
                latitude = c.latitude,
                longitude = c.longitude,
                geocode_source = 'census_batch'
            FROM _census_geo AS c
            WHERE churches.rowid = c.rowid
            AND churches.latitude IS NULL AND churches.longitude IS NULL
        """)
        updated = db.execute("SELECT changes()").fetchone()[0]
        print(f"  Updated {updated:,} churches records")
        db.execute("DROP TABLE IF EXISTS _census_geo")

        # Provenance — batch write with progress bar
        t_p2prov = time.time()
        log_data = []
        geo_items = list(geocoded_results.items())
        for i, (rid, (lat, lng)) in enumerate(geo_items):
            cid_row = db.execute("SELECT id FROM churches WHERE rowid=?", (rid,)).fetchone()
            cid = cid_row[0] if cid_row else rid
            log_data.append((cid, 'latitude', 'NULL', str(lat), 'census_batch', now))
            log_data.append((cid, 'longitude', 'NULL', str(lng), 'census_batch', now))
            progress_bar(i + 1, len(geo_items), t_p2prov, "| building provenance")
        print()

        db.executemany(
            "INSERT INTO enrichment_change_log (church_id, field_name, old_value, new_value, change_source, changed_at) VALUES (?, ?, ?, ?, ?, ?)",
            log_data
        )
        db.execute("INSERT OR IGNORE INTO provenance_log (source, action, timestamp, details) VALUES ('null_gps_fix', 'updated', ?, ?)",
                   (now, f'Phase 2: Census batch geocoded {len(geocoded_results)} US records'))
        db.commit()

    print(f"  Census batch complete: {len(geocoded_results):,} geocoded / {len(p2_export):,} submitted")
elif not apply_fix:
    print("  (dry run)")

print()

# ════════════════════════════════════════════════════════════════
# PHASE 3: ZIP centroids for US records with ZIP only
# ════════════════════════════════════════════════════════════════
print("=" * 60)
print("PHASE 3: ZIP centroid geocoding (US records with ZIP, no city/state)")

zip_lookup = {}
t_zcta = time.time()
with open(ZCTA_PATH, encoding='utf-8') as f:
    reader = csv.DictReader(f, delimiter='\t')
    reader.fieldnames = [n.strip() for n in reader.fieldnames]
    all_rows = list(reader)
for ri, row in enumerate(all_rows):
    z = row['GEOID'].strip().zfill(5)
    try:
        lat = float(row['INTPTLAT'].strip())
        lng = float(row['INTPTLONG'].strip())
        zip_lookup[z] = (lat, lng)
    except ValueError:
        continue
    progress_bar(ri + 1, len(all_rows), t_zcta, f"| {len(zip_lookup):,} centroids")
print()
print(f"  Loaded {len(zip_lookup):,} ZIP centroids")

p3_zip_rows = db.execute("""
    SELECT rowid, id, zip
    FROM churches
    WHERE latitude IS NULL AND longitude IS NULL
    AND country = 'US'
    AND zip IS NOT NULL AND zip != ''
    AND (city IS NULL OR city = '')
    AND (address IS NULL OR address = '')
""").fetchall()

p3_geocodable = []
t_p3match = time.time()
for i, r in enumerate(p3_zip_rows):
    z5 = str(r[2]).strip().split('-')[0].zfill(5)
    if z5 in zip_lookup:
        lat, lng = zip_lookup[z5]
        p3_geocodable.append((r[0], r[1], r[2], z5, lat, lng))
    progress_bar(i + 1, len(p3_zip_rows), t_p3match, f"| {len(p3_geocodable):,} matched")
print()
print(f"  Records with ZIP only: {len(p3_zip_rows):,}")
print(f"  ZCTA-addressable: {len(p3_geocodable):,}")

if apply_fix and p3_geocodable:
    now = datetime.now().isoformat()
    db.execute("DROP TABLE IF EXISTS _zip_geo")
    db.execute("CREATE TEMP TABLE _zip_geo (rowid INTEGER PRIMARY KEY, latitude REAL, longitude REAL)")
    db.executemany("INSERT INTO _zip_geo (rowid, latitude, longitude) VALUES (?, ?, ?)",
                   [(r[0], r[4], r[5]) for r in p3_geocodable])
    db.execute("""
        UPDATE churches SET latitude=z.latitude, longitude=z.longitude, geocode_source='zip_centroid'
        FROM _zip_geo AS z WHERE churches.rowid=z.rowid AND churches.latitude IS NULL AND churches.longitude IS NULL
    """)
    db.execute("DROP TABLE IF EXISTS _zip_geo")

    log_data = []
    t_p3log = time.time()
    for i, r in enumerate(p3_geocodable):
        cid = r[1] or r[0]
        log_data.append((cid, 'latitude', 'NULL', str(r[4]), 'zip_centroid', now))
        log_data.append((cid, 'longitude', 'NULL', str(r[5]), 'zip_centroid', now))
        progress_bar(i + 1, len(p3_geocodable), t_p3log, "| logging provenance")
    print()
    db.executemany("INSERT INTO enrichment_change_log (church_id, field_name, old_value, new_value, change_source, changed_at) VALUES (?, ?, ?, ?, ?, ?)", log_data)
    db.execute("INSERT OR IGNORE INTO provenance_log (source, action, timestamp, details) VALUES ('null_gps_fix', 'updated', ?, ?)",
               (now, f'Phase 3: ZIP centroid geocoded {len(p3_geocodable)} records'))
    db.commit()
    print(f"  ZIP-geocoded: {len(p3_geocodable):,}")
elif not apply_fix:
    print("  (dry run)")

print()

# ════════════════════════════════════════════════════════════════
# PHASE 4: State centroids (last resort)
# ════════════════════════════════════════════════════════════════
print("=" * 60)
print("PHASE 4: State centroid fallback")

t_p4 = time.time()
state_rows = db.execute("""
    SELECT state, AVG(latitude), AVG(longitude), COUNT(1)
    FROM churches WHERE country='US' AND latitude IS NOT NULL AND longitude IS NOT NULL
    AND state IS NOT NULL AND state != ''
    GROUP BY state
""").fetchall()
state_centroids = {}
for i, r in enumerate(state_rows):
    if r[3] >= 10:
        state_centroids[r[0]] = (r[1], r[2])
    progress_bar(i + 1, len(state_rows), t_p4, f"| {len(state_centroids):,} centroids")
print()
print(f"  Computed {len(state_centroids):,} state centroids")

p4_state_rows = db.execute("""
    SELECT rowid, id, state
    FROM churches
    WHERE latitude IS NULL AND longitude IS NULL
    AND country = 'US'
    AND state IS NOT NULL AND state != ''
    AND (city IS NULL OR city = '')
    AND (zip IS NULL OR zip = '')
    AND (address IS NULL OR address = '')
""").fetchall()

p4_geocodable = [(r[0], r[1], r[2]) for r in p4_state_rows if r[2] in state_centroids]
print(f"  State-only remaining: {len(p4_state_rows):,}")
print(f"  State-addressable: {len(p4_geocodable):,}")

if apply_fix and p4_geocodable:
    now = datetime.now().isoformat()
    db.execute("DROP TABLE IF EXISTS _state_geo")
    db.execute("CREATE TEMP TABLE _state_geo (rowid INTEGER PRIMARY KEY, latitude REAL, longitude REAL)")
    db.executemany("INSERT INTO _state_geo (rowid, latitude, longitude) VALUES (?, ?, ?)",
                   [(r[0], state_centroids[r[2]][0], state_centroids[r[2]][1]) for r in p4_geocodable])
    db.execute("""
        UPDATE churches SET latitude=s.latitude, longitude=s.longitude, geocode_source='state_centroid'
        FROM _state_geo AS s WHERE churches.rowid=s.rowid AND churches.latitude IS NULL AND churches.longitude IS NULL
    """)
    db.execute("DROP TABLE IF EXISTS _state_geo")

    log_data = []
    t_p4log = time.time()
    for i, r in enumerate(p4_geocodable):
        cid = r[1] or r[0]
        lat, lng = state_centroids[r[2]]
        log_data.append((cid, 'latitude', 'NULL', str(lat), 'state_centroid', now))
        log_data.append((cid, 'longitude', 'NULL', str(lng), 'state_centroid', now))
        progress_bar(i + 1, len(p4_geocodable), t_p4log, "| logging provenance")
    print()
    db.executemany("INSERT INTO enrichment_change_log (church_id, field_name, old_value, new_value, change_source, changed_at) VALUES (?, ?, ?, ?, ?, ?)", log_data)
    db.execute("INSERT OR IGNORE INTO provenance_log (source, action, timestamp, details) VALUES ('null_gps_fix', 'updated', ?, ?)",
               (now, f'Phase 4: state centroid geocoded {len(p4_geocodable)} records'))
    db.commit()
    print(f"  State-centroided: {len(p4_geocodable):,}")
elif not apply_fix:
    print("  (dry run)")

print()

# ════════════════════════════════════════════════════════════════
# FINAL SUMMARY
# ════════════════════════════════════════════════════════════════
print("=" * 60)
remaining = db.execute("SELECT COUNT(1) FROM churches WHERE latitude IS NULL AND longitude IS NULL").fetchone()[0]
now_geo = db.execute("SELECT COUNT(1) FROM churches WHERE latitude IS NOT NULL AND longitude IS NOT NULL").fetchone()[0]
total = db.execute("SELECT COUNT(1) FROM churches").fetchone()[0]

print(f"FINAL SUMMARY:")
print(f"  Total records:       {total:,}")
print(f"  Now geocoded:        {now_geo:,} ({now_geo/total*100:.1f}%)")
print(f"  Still null GPS:      {remaining:,} ({remaining/total*100:.1f}%)")

if remaining > 0:
    print()
    print("Remaining breakdown (source):")
    for r in db.execute("""
        SELECT COALESCE(source,'NULL'), COUNT(1)
        FROM churches WHERE latitude IS NULL AND longitude IS NULL
        GROUP BY source ORDER BY COUNT(1) DESC LIMIT 10
    """).fetchall():
        print(f"  {r[0]:.45s} {r[1]:,}")
    print()
    print("Remaining breakdown (country):")
    for r in db.execute("""
        SELECT COALESCE(country,'NULL'), COUNT(1)
        FROM churches WHERE latitude IS NULL AND longitude IS NULL
        GROUP BY country ORDER BY COUNT(1) DESC LIMIT 15
    """).fetchall():
        print(f"  {r[0]:.10s} {r[1]:,}")
    print()
    print("Remaining address data:")
    rem_addr = db.execute("SELECT COUNT(1) FROM churches WHERE latitude IS NULL AND longitude IS NULL AND address IS NOT NULL AND address != ''").fetchone()[0]
    rem_zip = db.execute("SELECT COUNT(1) FROM churches WHERE latitude IS NULL AND longitude IS NULL AND zip IS NOT NULL AND zip != ''").fetchone()[0]
    print(f"  With street address: {rem_addr:,}")
    print(f"  With ZIP:            {rem_zip:,}")

db.close()
print(f"\nElapsed: {time.time()-t0:.1f}s")
