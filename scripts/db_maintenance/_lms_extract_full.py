"""Full FCC LMS extraction pipeline.

1. Parse app_location + application_facility → facility_id + coords + callsign
2. Decode WKB to lat/lon
3. Write staging CSV
4. Import to churches.db staging table
"""
import zipfile, csv, io, struct, os

ZIP = 'E:/grid/06-23-2026_LMS_Dump.zip'
STAGING_CSV = 'E:/grid/data/fcc_lms_facilities.csv'
DB = 'E:/grid/churches.db'

# === STEP 1: Load application_facility mapping ===
print("=== Loading application_facility: app_id → facility_id ===")
app_to_fac = {}
with zipfile.ZipFile(ZIP) as z:
    with z.open('application_facility.dat') as f:
        reader = csv.reader(io.TextIOWrapper(f, 'latin-1'), delimiter='|')
        next(reader)  # header
        for row in reader:
            if len(row) < 6: continue
            aid = row[1].strip()
            fid = row[5].strip()
            if aid and fid and aid not in app_to_fac:
                app_to_fac[aid] = fid
print(f"  {len(app_to_fac):,} mappings loaded")

# === STEP 2: Load facility details ===
print("=== Loading facility: facility_id → (callsign, service_code) ===")
fac_info = {}
with zipfile.ZipFile(ZIP) as z:
    with z.open('facility.dat') as f:
        reader = csv.reader(io.TextIOWrapper(f, 'latin-1'), delimiter='|')
        next(reader)
        for row in reader:
            if len(row) < 26: continue
            fid = row[12].strip()
            callsign = row[3].strip() if len(row) > 3 else ''
            svc = row[25].strip() if len(row) > 25 else ''
            if fid:
                fac_info[fid] = (callsign, svc)
print(f"  {len(fac_info):,} facilities loaded")

# === STEP 3: Scan app_location, decode WKB, group by facility ===
print("=== Scanning app_location with WKB decoding ===")

def decode_wkb(wkb_hex):
    """Decode EWKB hex to (lon, lat). SRID 4326 = 9-byte prefix + 8B lon + 8B lat = 25 bytes."""
    if len(wkb_hex) < 50:
        return None, None
    # Skip 9 bytes (18 hex chars) of SRID prefix (0101000020E6100000)
    # Then 8 bytes longitude (16 hex chars) + 8 bytes latitude (16 hex chars)
    try:
        lon = struct.unpack('<d', bytes.fromhex(wkb_hex[18:34]))[0]
        lat = struct.unpack('<d', bytes.fromhex(wkb_hex[34:50]))[0]
    except:
        return None, None
    return lon, lat

# facility_id → list of (lon, lat, count) for averaging
from collections import defaultdict
fac_locations = defaultdict(list)

with zipfile.ZipFile(ZIP) as z:
    with z.open('app_location.dat') as f:
        reader = csv.reader(io.TextIOWrapper(f, 'latin-1'), delimiter='|')
        next(reader)
        count = 0
        for row in reader:
            if len(row) < 15: continue
            aid = row[8].strip()
            wkb = row[14].strip()
            if not aid or not wkb:
                continue
            fid = app_to_fac.get(aid)
            if not fid:
                continue
            lon, lat = decode_wkb(wkb)
            if lon is not None:
                fac_locations[fid].append((lon, lat))
                count += 1
                if count % 50000 == 0:
                    print(f"    Processed {count:,} locations...")

print(f"  Total locations processed: {count:,}")
print(f"  Unique facilities with coords: {len(fac_locations):,}")

# === STEP 4: Write staging CSV with best coords per facility ===
print(f"\n=== Writing staging CSV: {STAGING_CSV} ===")
os.makedirs('E:/grid/data', exist_ok=True)

svc_counts = defaultdict(int)
written = 0
with open(STAGING_CSV, 'w', newline='', encoding='utf-8') as f:
    w = csv.writer(f)
    w.writerow(['facility_id', 'callsign', 'service_code', 'lat', 'lon', 'location_count'])
    for fid, coords in fac_locations.items():
        callsign, svc = fac_info.get(fid, ('', ''))
        # Average all coordinates for this facility
        n = len(coords)
        avg_lon = sum(c[0] for c in coords) / n
        avg_lat = sum(c[1] for c in coords) / n
        w.writerow([fid, callsign, svc, round(avg_lat, 6), round(avg_lon, 6), n])
        svc_counts[svc] += 1
        written += 1

print(f"  Written: {written:,} facilities")

print(f"\n=== Service Code Breakdown ===")
for svc in sorted(svc_counts.keys()):
    label = svc if svc else '(empty)'
    print(f"  {label:6s}: {svc_counts[svc]:,}")

# LPFM specifically
print(f"\n  === LPFM (FL) specifically: {svc_counts.get('FL', 0):,} ===")

# Religious broadcast estimate (by callsign)
religious_callsigns = set()
religious_kw = ['GOSPEL', 'CHRIST', 'FAITH', 'BIBLE', 'PRAISE', 'WORSHIP', 'TRINITY',
                'CALVARY', 'GRACE', 'HOPE', 'MERCY', 'SALVATION', 'REDEEMER',
                'KINGDOM', 'MINISTRY', 'CHURCH', 'CATHOLIC', 'BAPTIST',
                'METHODIST', 'LUTHERAN', 'PRESBYTERIAN', 'PENTECOSTAL']
for fid, coords in fac_locations.items():
    callsign, svc = fac_info.get(fid, ('', ''))
    cs_upper = callsign.upper()
    if any(kw in cs_upper for kw in religious_kw):
        religious_callsigns.add(fid)

print(f"\n=== Religious-sounding callsigns (any keyword): {len(religious_callsigns):,} ===")
by_svc_rel = {}
for fid in religious_callsigns:
    cs, svc = fac_info.get(fid, ('', ''))
    by_svc_rel[svc] = by_svc_rel.get(svc, 0) + 1
for svc in sorted(by_svc_rel.keys()):
    print(f"  {svc:6s}: {by_svc_rel[svc]:,}")

print("\nDone!")
