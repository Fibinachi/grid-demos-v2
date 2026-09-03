"""Proof-of-concept: join facility -> authorization -> location for coordinates"""
import zipfile, os, csv, io

ZIP_PATH = os.path.join(os.path.dirname(__file__), '06-23-2026_LMS_Dump.zip')
z = zipfile.ZipFile(ZIP_PATH)

# Build index: application_id -> facility_id from assigned_authorization
print("Indexing assigned_authorization (application_id -> facility_id)...")
app_to_facility = {}
with z.open('assigned_authorization.dat') as f:
    reader = csv.DictReader(io.TextIOWrapper(f, 'latin-1'), delimiter='|')
    for row in reader:
        app_id = row.get('application_id', '').strip()
        fac_id = row.get('facility_id', '').strip()
        if app_id and fac_id:
            # Keep the first mapping (could add preference for active later)
            if app_id not in app_to_facility:
                app_to_facility[app_id] = fac_id

print(f"  {len(app_to_facility):,} application->facility mappings")

# Collect facility_id -> location (WKB coords)
print("\nJoining app_location -> facility...")
facility_locations = {}
no_facility = 0
joined = 0

with z.open('app_location.dat') as f:
    reader = csv.DictReader(io.TextIOWrapper(f, 'latin-1'), delimiter='|')
    for row in reader:
        app_id = row.get('aloc_aapp_application_id', '').strip()
        wkb = row.get('aloc_geo_coord', '').strip()
        if not app_id or not wkb or len(wkb) < 20:
            continue
        fac_id = app_to_facility.get(app_id)
        if not fac_id:
            no_facility += 1
            continue
        if fac_id not in facility_locations:
            facility_locations[fac_id] = wkb
            joined += 1

print(f"  {joined:,} facilities have GPS coordinates from app_location")
print(f"  {no_facility:,} app_locations had no matching authorization")

# Show sample: FM facilities with coords
print("\n=== Sample FM/LPFM facilities with coordinates ===")
count = 0
with z.open('facility.dat') as f:
    reader = csv.DictReader(io.TextIOWrapper(f, 'latin-1'), delimiter='|')
    for row in reader:
        fac_id = row.get('facility_id', '').strip()
        sc = row.get('service_code', '').strip()
        if sc in ('FM', 'FL', 'AM', 'FX') and fac_id in facility_locations:
            if count < 5:
                wkb = facility_locations[fac_id]
                callsign = row.get('callsign', '').strip()
                city = row.get('community_served_city', '').strip()
                st = row.get('community_served_state', '').strip()
                print(f"  {callsign:10s} | {sc:3s} | {fac_id:>8s} | {wkb[:60]}... | {city}, {st}")
            count += 1

# Summarize by service
print("\n=== Facility coordinates by service code ===")
svc_counts = {}
with z.open('facility.dat') as f:
    reader = csv.DictReader(io.TextIOWrapper(f, 'latin-1'), delimiter='|')
    for row in reader:
        fac_id = row.get('facility_id', '').strip()
        sc = row.get('service_code', '').strip()
        if fac_id in facility_locations:
            svc_counts[sc] = svc_counts.get(sc, 0) + 1

total_facilities = {'FL': 7828, 'FM': 24446, 'AM': 15282, 'FX': 23374, 'FB': 950, 'FS': 0}
for sc in ['FL', 'FM', 'AM', 'FX', 'FB', 'FS']:
    c = svc_counts.get(sc, 0)
    t = total_facilities.get(sc, 0)
    pct = c / t * 100 if t > 0 else 0
    print(f"  {sc:5s}: {c:>6,} / {t:>6,} ({pct:.1f}%) with coordinates")

z.close()
