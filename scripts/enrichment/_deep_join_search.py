"""Full app_mm_application column scan and alternate join paths"""
import zipfile, os, csv, io

ZIP_PATH = os.path.join(os.path.dirname(__file__), '06-23-2026_LMS_Dump.zip')
z = zipfile.ZipFile(ZIP_PATH)

# 1. Full column listing of app_mm_application
with z.open('app_mm_application.dat') as f:
    cols = f.readline().decode('latin-1').split('|')
    print("=== app_mm_application: ALL columns ===")
    for j, c in enumerate(cols):
        if c.strip():
            print(f"  [{j:3d}] {c}")

print()

# 2. Check: does app_mm_application have any UUID-like fields that could be facility_uuid?
# Sample the first 10 data rows looking for any value that matches a facility UUID
with z.open('facility.dat') as f:
    reader = csv.DictReader(io.TextIOWrapper(f, 'latin-1'), delimiter='|')
    facility_uuids = set()
    for i, row in enumerate(reader):
        uuid = row.get('facility_uuid', '').strip()
        if uuid:
            facility_uuids.add(uuid)
        if i >= 1000:
            break
    print(f"  Sample of {len(facility_uuids):,} facility_uuids (first 1000 facilities)")

# Now check app_mm_application rows for any field matching a facility UUID
with z.open('app_mm_application.dat') as f:
    reader = csv.DictReader(io.TextIOWrapper(f, 'latin-1'), delimiter='|')
    matches = 0
    total = 0
    for i, row in enumerate(reader):
        if i >= 500:
            break
        for k, v in row.items():
            if v.strip() in facility_uuids:
                matches += 1
                if matches <= 5:
                    print(f"  MATCH in app_mm_application.{k}: {v.strip()}")
    print(f"  {matches} UUID matches found in {min(500,i+1)} rows")

z.close()

# 3. Try a completely different approach: look for a table that directly has facility_id + lat/lon
z2 = zipfile.ZipFile(ZIP_PATH)
print("\n=== Scanning ALL tables for both facility_id and lat/lon patterns ===")
for info in z2.infolist():
    name = info.filename.lower()
    # Skip massive tables
    skip_if_larger_mb = 50
    if info.file_size > skip_if_larger_mb * 1024 * 1024:
        continue
    if not name.endswith('.dat'):
        continue
    try:
        with z2.open(info.filename) as f:
            hdr = f.read(2000).decode('latin-1')
            cols_hdr = hdr.split('|')
            has_fac = any('facility_id' in c.lower() for c in cols_hdr)
            has_lat = any('lat' in c.lower() for c in cols_hdr)
            has_lon = any('lon' in c.lower() for c in cols_hdr)
            if has_fac and (has_lat or has_lon):
                print(f"  {info.filename:40s} | facility_id Y | lat:{has_lat} lon:{has_lon}")
    except:
        pass

z2.close()
