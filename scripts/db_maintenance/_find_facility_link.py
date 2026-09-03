"""Find how app_mm_application connects to facility_id or facility_uuid"""
import zipfile, os, csv, io

ZIP_PATH = os.path.join(os.path.dirname(__file__), '06-23-2026_LMS_Dump.zip')
z = zipfile.ZipFile(ZIP_PATH)

# 1. Check if app_mm_application has any 'facility' or 'uuid' columns
with z.open('app_mm_application.dat') as f:
    cols = f.readline().decode('latin-1').split('|')
    print("=== app_mm_application: facility/uuid columns ===")
    for j, c in enumerate(cols):
        if any(x in c.lower() for x in ['facility', 'fac', 'uuid', 'fcc_party', 'frn', 'legal_name']):
            print(f"  [{j}] {c}")

print()

# 2. Check how facility connects to facility_applicant (via facility_uuid)
# Build facility_id -> facility_uuid from facility.dat
print("=== Building facility_id -> facility_uuid map ===")
fac_id_to_uuid = {}
with z.open('facility.dat') as f:
    reader = csv.DictReader(io.TextIOWrapper(f, 'latin-1'), delimiter='|')
    for i, row in enumerate(reader):
        fac_id = row.get('facility_id', '').strip()
        fac_uuid = row.get('facility_uuid', '').strip()
        if fac_id and fac_uuid:
            fac_id_to_uuid[fac_id] = fac_uuid
        if i >= 10000:
            break
print(f"  {len(fac_id_to_uuid):,} facility_id -> uuid (from first 10K rows)")

# 3. Check if app_mm_application has aloc_loc_id or something linking to app_location
# app_location has: aloc_aapp_application_id (matches aapp_application_id)
# app_location also has: aloc_loc_id, aloc_loc_record_id, aloc_loc_seq_id

# 4. Check license_filing.dat - might link app to facility
with z.open('license_filing.dat') as f:
    cols = f.readline().decode('latin-1').split('|')
    print("\n=== license_filing.dat columns ===")
    for j, c in enumerate(cols):
        if c.strip():
            print(f"  [{j}] {c}")

print()

# 5. Check license_filing_version_history.dat
with z.open('license_filing_version_history.dat') as f:
    cols = f.readline().decode('latin-1').split('|')
    print("=== license_filing_version_history.dat columns ===")
    for j, c in enumerate(cols):
        if c.strip() and j < 30:  # Just first 30
            print(f"  [{j}] {c}")
    print(f"  ... ({len(cols)} total columns)" if len(cols) > 30 else "")

z.close()
