"""Analyze broadcast facility counts and coordinate availability in LMS dump"""
import zipfile, os, csv, io

ZIP_PATH = os.path.join(os.path.dirname(__file__), '06-23-2026_LMS_Dump.zip')
z = zipfile.ZipFile(ZIP_PATH)

BROADCAST_SERVICES = ['FL', 'FM', 'AM', 'FX', 'FB', 'FS', 'FA', 'FR']

# 1. Count facilities by service_code
print("=== Facility counts by service_code (top 20) ===")
facility_service_counts = {}
total_facilities = 0
with z.open('facility.dat') as f:
    reader = csv.DictReader(io.TextIOWrapper(f, 'latin-1'), delimiter='|')
    for row in reader:
        sc = row.get('service_code', '').strip()
        facility_service_counts[sc] = facility_service_counts.get(sc, 0) + 1
        total_facilities += 1

for sc in sorted(facility_service_counts, key=facility_service_counts.get, reverse=True)[:20]:
    marker = ' <<<' if sc in BROADCAST_SERVICES else ''
    print(f"  {sc:5s}: {facility_service_counts[sc]:>8,}{marker}")
print(f"  TOTAL: {total_facilities:,}")

# Broadcast totals
for grp in ['FL (LPFM)', 'FM (Full)', 'AM', 'FX (Translator)', 'FB (Booster)', 'FS (Aux)', 'FA (Allot)', 'FR (Rulemaking)']:
    sc = grp.split(' ')[0]
    if sc in facility_service_counts:
        print(f"\n  Broadcast: {grp}: {facility_service_counts[sc]:,}")

# 2. Count assigned_authorization by service (active + granted)
print("\n=== Assigned authorizations by service ===")
auth_service_counts = {}
total_auth = 0
with z.open('assigned_authorization.dat') as f:
    reader = csv.DictReader(io.TextIOWrapper(f, 'latin-1'), delimiter='|')
    for row in reader:
        sc = row.get('service_code', '').strip()
        auth_service_counts[sc] = auth_service_counts.get(sc, 0) + 1
        total_auth += 1

for sc in sorted(auth_service_counts, key=auth_service_counts.get, reverse=True)[:20]:
    marker = ' <<<' if sc in BROADCAST_SERVICES else ''
    print(f"  {sc:5s}: {auth_service_counts[sc]:>8,}{marker}")
print(f"  TOTAL: {total_auth:,}")

# 3. Count app_location rows with valid WKB coords
print("\n=== App location coordinates availability ===")
total_locs = 0
with_wkb = 0
with_dms = 0
coords_usable = 0
sample_rows = []

with z.open('app_location.dat') as f:
    reader = csv.DictReader(io.TextIOWrapper(f, 'latin-1'), delimiter='|')
    for i, row in enumerate(reader):
        total_locs += 1
        aloc_geo_coord = row.get('aloc_geo_coord', '').strip()
        if aloc_geo_coord and len(aloc_geo_coord) > 10:
            with_wkb += 1
        # Check DMS
        lat_deg = row.get('aloc_lat_deg', '').strip()
        lon_deg = row.get('aloc_long_deg', '').strip()
        if lat_deg and lon_deg:
            with_dms += 1
        if i < 3:
            sample_rows.append((aloc_geo_coord[:50], lat_deg, lon_deg))

print(f"  Total app_locations: {total_locs:,}")
print(f"  With valid WKB:      {with_wkb:,} ({with_wkb/max(total_locs,1)*100:.1f}%)")
print(f"  With DMS lat/lon:    {with_dms:,} ({with_dms/max(total_locs,1)*100:.1f}%)")

z.close()
