"""
Fix null GPS records in churches.db — comprehensive approach.

Phases:
  1. Copy existing lat/lon from church_addresses → churches (94 records)
  2. ZIP centroid geocoding via Census ZCTA data (for records with zip)
  3. State centroid fallback (for US records with only state)
  4. Summary report

Usage:
  python _fix_null_gps.py --apply   (actually apply)
  python _fix_null_gps.py           (dry run / report)
"""
import csv
import sqlite3
import sys
import time
from datetime import datetime

DB = 'E:/grid/churches.db'
ZCTA_PATH = 'E:/grid/data/Gaz_zcta_national.txt'

t0 = time.time()

def log(msg):
    print(f"[{time.time()-t0:6.1f}s] {msg}", flush=True)

apply_fix = '--apply' in sys.argv

db = sqlite3.connect(DB)
db.execute("PRAGMA synchronous=OFF")

total_null = db.execute("SELECT COUNT(1) FROM churches WHERE latitude IS NULL AND longitude IS NULL").fetchone()[0]
print(f"Total null-GPS records: {total_null:,}")
print(f"Mode: {'APPLY' if apply_fix else 'DRY RUN'}")
print()

# ════════════════════════════════════════════════════════════════
# PHASE 1: Copy lat/lon from church_addresses → churches
# ════════════════════════════════════════════════════════════════
print("═" * 60)
print("PHASE 1: Copy lat/lon from church_addresses")

phase1_records = db.execute("""
    SELECT DISTINCT c.rowid, c.id, ca.latitude, ca.longitude, ca.geocode_source,
           c.name, c.source, c.country
    FROM churches c
    JOIN church_addresses ca ON ca.church_rowid = c.rowid
    WHERE c.latitude IS NULL AND c.longitude IS NULL
    AND ca.latitude IS NOT NULL AND ca.longitude IS NOT NULL
""").fetchall()
print(f"  Found {len(phase1_records):,} records to copy")

if apply_fix and phase1_records:
    # Use UPDATE FROM pattern (SQLite 3.33+)
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
    phase1_updated = db.execute("""
        SELECT COUNT(1) FROM churches c
        JOIN church_addresses ca ON ca.church_rowid = c.rowid
        WHERE ca.latitude IS NOT NULL AND ca.longitude IS NOT NULL
        AND c.latitude IS NOT NULL AND c.longitude IS NOT NULL
    """).fetchone()[0]
    print(f"  Updated: {phase1_updated:,} records")

    # Log provenance - enrichment_change_log
    now = datetime.now().isoformat()
    log_data = []
    for r in phase1_records:
        log_data.append((r[1] or r[0], 'latitude', 'NULL', str(r[2]), 'address_copy', now))
        log_data.append((r[1] or r[0], 'longitude', 'NULL', str(r[3]), 'address_copy', now))
    if log_data:
        db.executemany(
            "INSERT INTO enrichment_change_log (church_id, field_name, old_value, new_value, change_source, changed_at) VALUES (?, ?, ?, ?, ?, ?)",
            log_data
        )
        print(f"  Logged {len(log_data):,} changes to enrichment_change_log")
    db.commit()
elif not apply_fix:
    print("  (dry run, --apply to execute)")

print()

# ════════════════════════════════════════════════════════════════
# PHASE 2: Load ZCTA and geocode by ZIP centroid
# ════════════════════════════════════════════════════════════════
print("═" * 60)
print("PHASE 2: ZIP centroid geocoding")

# Load ZCTA
zip_lookup = {}
with open(ZCTA_PATH, encoding='utf-8') as f:
    reader = csv.DictReader(f, delimiter='\t')
    reader.fieldnames = [n.strip() for n in reader.fieldnames]
    for row in reader:
        z = row['GEOID'].strip().zfill(5)
        try:
            lat = float(row['INTPTLAT'].strip())
            lng = float(row['INTPTLONG'].strip())
            zip_lookup[z] = (lat, lng)
        except ValueError:
            continue
print(f"  Loaded {len(zip_lookup):,} ZIP centroids")

# Find null-GPS US records with zip5
rows_to_zip = db.execute("""
    SELECT rowid, id, zip, name, source, country
    FROM churches
    WHERE latitude IS NULL AND longitude IS NULL
    AND country = 'US'
    AND zip IS NOT NULL AND zip != ''
""").fetchall()
print(f"  Records with ZIP codes: {len(rows_to_zip):,}")

zipable = []
for r in rows_to_zip:
    z5 = str(r[2]).strip().split('-')[0].zfill(5)
    if z5 in zip_lookup:
        lat, lng = zip_lookup[z5]
        zipable.append((r[0], r[1], r[2], z5, lat, lng))

print(f"  ZIP-addressable (ZCTA match): {len(zipable):,}")

if apply_fix and zipable:
    now = datetime.now().isoformat()
    # Batch update via temp table
    db.execute("DROP TABLE IF EXISTS _zip_geo")
    db.execute("""
        CREATE TEMP TABLE _zip_geo (
            rowid INTEGER PRIMARY KEY,
            latitude REAL,
            longitude REAL
        )
    """)
    db.executemany(
        "INSERT INTO _zip_geo (rowid, latitude, longitude) VALUES (?, ?, ?)",
        [(r[0], r[4], r[5]) for r in zipable]
    )
    db.execute("""
        UPDATE churches SET
            latitude = z.latitude,
            longitude = z.longitude,
            geocode_source = 'zip_centroid'
        FROM _zip_geo AS z
        WHERE churches.rowid = z.rowid
        AND churches.latitude IS NULL AND churches.longitude IS NULL
    """)
    zip_updated = db.execute("""
        SELECT COUNT(1) FROM churches c
        JOIN _zip_geo z ON c.rowid = z.rowid
        WHERE c.latitude IS NOT NULL AND c.longitude IS NOT NULL
    """).fetchone()[0]
    db.execute("DROP TABLE IF EXISTS _zip_geo")
    print(f"  ZIP-geocoded: {zip_updated:,} records")

    # Log provenance
    log_data = []
    for r in zipable:
        church_id = r[1] or r[0]
        log_data.append((church_id, 'latitude', 'NULL', str(r[4]), 'zip_centroid', now))
        log_data.append((church_id, 'longitude', 'NULL', str(r[5]), 'zip_centroid', now))
    if log_data:
        db.executemany(
            "INSERT INTO enrichment_change_log (church_id, field_name, old_value, new_value, change_source, changed_at) VALUES (?, ?, ?, ?, ?, ?)",
            log_data
        )
        print(f"  Logged {len(log_data):,} changes to enrichment_change_log")
    db.commit()
elif not apply_fix:
    print("  (dry run, --apply to execute)")

# Show sample of unaddressed
remaining_after = db.execute("SELECT COUNT(1) FROM churches WHERE latitude IS NULL AND longitude IS NULL AND country='US' AND state IS NOT NULL AND state != '' AND (city IS NULL OR city = '')").fetchone()[0]
print(f"\n  US state-only remaining after: {remaining_after:,}")

print()

# ════════════════════════════════════════════════════════════════
# PHASE 3: State centroid fallback
# ════════════════════════════════════════════════════════════════
print("═" * 60)
print("PHASE 3: State centroid fallback (US only)")

# Compute state centroids from existing geocoded US churches
state_centroids = {}
for r in db.execute("""
    SELECT state, AVG(latitude), AVG(longitude), COUNT(1)
    FROM churches
    WHERE country = 'US'
    AND latitude IS NOT NULL AND longitude IS NOT NULL
    AND state IS NOT NULL AND state != ''
    GROUP BY state
""").fetchall():
    if r[3] >= 10:  # At least 10 records for a meaningful centroid
        state_centroids[r[0]] = (r[1], r[2], r[3])

print(f"  Computed centroids for {len(state_centroids):,} states (min 10 records)")

# Find null-GPS US records with state
state_rows = db.execute("""
    SELECT rowid, id, state, name, source
    FROM churches
    WHERE latitude IS NULL AND longitude IS NULL
    AND country = 'US'
    AND state IS NOT NULL AND state != ''
""").fetchall()

states_with_data = set(state_centroids.keys())
state_geocodable = [(r[0], r[1], r[2], r[3], r[4])
                     for r in state_rows
                     if r[2] in states_with_data]
print(f"  State-addressable: {len(state_geocodable):,}")

if apply_fix and state_geocodable:
    now = datetime.now().isoformat()
    db.execute("DROP TABLE IF EXISTS _state_geo")
    db.execute("""
        CREATE TEMP TABLE _state_geo (
            rowid INTEGER PRIMARY KEY,
            latitude REAL,
            longitude REAL,
            state TEXT
        )
    """)
    db.executemany(
        "INSERT INTO _state_geo (rowid, latitude, longitude, state) VALUES (?, ?, ?, ?)",
        [(r[0], state_centroids[r[2]][0], state_centroids[r[2]][1], r[2])
         for r in state_geocodable]
    )
    db.execute("""
        UPDATE churches SET
            latitude = s.latitude,
            longitude = s.longitude,
            geocode_source = 'state_centroid'
        FROM _state_geo AS s
        WHERE churches.rowid = s.rowid
        AND churches.latitude IS NULL AND churches.longitude IS NULL
    """)
    state_updated = db.execute("""
        SELECT COUNT(1) FROM churches c
        JOIN _state_geo s ON c.rowid = s.rowid
        WHERE c.latitude IS NOT NULL AND c.longitude IS NOT NULL
    """).fetchone()[0]
    db.execute("DROP TABLE IF EXISTS _state_geo")
    print(f"  State-centroided: {state_updated:,} records")

    # Log provenance
    log_data = []
    for r in state_geocodable:
        church_id = r[1] or r[0]
        lat, lng, _ = state_centroids[r[2]]
        log_data.append((church_id, 'latitude', 'NULL', str(lat), 'state_centroid', now))
        log_data.append((church_id, 'longitude', 'NULL', str(lng), 'state_centroid', now))
    if log_data:
        db.executemany(
            "INSERT INTO enrichment_change_log (church_id, field_name, old_value, new_value, change_source, changed_at) VALUES (?, ?, ?, ?, ?, ?)",
            log_data
        )
        print(f"  Logged {len(log_data):,} changes to enrichment_change_log")
    db.commit()
elif not apply_fix:
    print("  (dry run, --apply to execute)")

print()

# ════════════════════════════════════════════════════════════════
# FINAL SUMMARY
# ════════════════════════════════════════════════════════════════
print("═" * 60)
remaining = db.execute("SELECT COUNT(1) FROM churches WHERE latitude IS NULL AND longitude IS NULL").fetchone()[0]
now_geocoded = db.execute("SELECT COUNT(1) FROM churches WHERE latitude IS NOT NULL AND longitude IS NOT NULL").fetchone()[0]
total = db.execute("SELECT COUNT(1) FROM churches").fetchone()[0]

print(f"FINAL SUMMARY:")
print(f"  Total records:       {total:,}")
print(f"  Now geocoded:        {now_geocoded:,} ({now_geocoded/total*100:.1f}%)")
print(f"  Still null GPS:      {remaining:,} ({remaining/total*100:.1f}%)")

if remaining > 0:
    print()
    print("Remaining breakdown:")
    for r in db.execute("""
        SELECT COALESCE(country,'NULL'), COALESCE(source,'NULL'), COUNT(1)
        FROM churches WHERE latitude IS NULL AND longitude IS NULL
        GROUP BY country, source ORDER BY COUNT(1) DESC
        LIMIT 15
    """).fetchall():
        print(f"  {r[0]} | {r[1]:.35s} | {r[2]:,}")

    # Check what address data remaining records have
    rem_addr = db.execute("SELECT COUNT(1) FROM churches WHERE latitude IS NULL AND longitude IS NULL AND address IS NOT NULL AND address != ''").fetchone()[0]
    print(f"\n  Remaining with street addresses: {rem_addr:,}")

db.close()
print(f"\nElapsed: {time.time()-t0:.1f}s")
