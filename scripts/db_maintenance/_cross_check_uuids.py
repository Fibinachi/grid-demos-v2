"""Cross-check UUID formats across application tables to find the bridge to facility_id"""
import zipfile, csv, io

z = zipfile.ZipFile('E:/grid/06-23-2026_LMS_Dump.zip')

# Collect FORMAT B UUIDs from application.dat (aapp_application_id)
print("=== application.dat FORMAT B IDs ===")
app_b_ids = set()
with z.open('application.dat') as f:
    reader = csv.reader(io.TextIOWrapper(f, 'latin-1'), delimiter='|')
    next(reader)
    for row in reader:
        if len(row) < 2: continue
        aid = row[1].strip()  # aapp_application_id
        if aid and len(aid) > 20:
            app_b_ids.add(aid)
print(f"  {len(app_b_ids):,} unique FORMAT B IDs")

# Collect auth IDs
print("=== assigned_authorization IDs ===")
auth_ids = set()
auth_fac_map = {}
with z.open('assigned_authorization.dat') as f:
    reader = csv.reader(io.TextIOWrapper(f, 'latin-1'), delimiter='|')
    next(reader)
    for row in reader:
        if len(row) < 8: continue
        aid = row[1].strip()  # application_id
        fid = row[7].strip()  # facility_id
        svc = row[12].strip() if len(row) > 12 else ''
        if aid and len(aid) > 20:
            auth_ids.add(aid)
            auth_fac_map[aid] = (fid, svc)
print(f"  {len(auth_ids):,} unique IDs")

# Collect application_facility IDs
print("=== application_facility IDs ===")
appfac_ids = set()
appfac_fac_map = {}
with z.open('application_facility.dat') as f:
    reader = csv.reader(io.TextIOWrapper(f, 'latin-1'), delimiter='|')
    next(reader)
    for row in reader:
        if len(row) < 6: continue
        aid = row[1].strip()  # afac_application_id
        fid = row[5].strip()  # afac_facility_id
        if aid and len(aid) > 20:
            appfac_ids.add(aid)
            appfac_fac_map[aid] = fid
print(f"  {len(appfac_ids):,} unique IDs")

# Cross-check 1: application_b ↔ auth
overlap_ba = app_b_ids & auth_ids
print(f"\n=== Cross checks ===")
print(f"1. application.dat ↔ assigned_authorization: {len(overlap_ba):,} / {len(auth_ids):,}")
if len(overlap_ba) > 0:
    sample = list(overlap_ba)[:3]
    for s in sample:
        fn, svc = auth_fac_map.get(s, ('?','?'))
        print(f"   {s[:30]}... -> facility_id={fn} svc={svc}")

# Cross-check 2: application_b ↔ application_facility
overlap_baf = app_b_ids & appfac_ids
print(f"2. application.dat ↔ application_facility: {len(overlap_baf):,}")

# Cross-check 3: auth ↔ application_facility
overlap_aaf = auth_ids & appfac_ids
print(f"3. assigned_authorization ↔ application_facility: {len(overlap_aaf):,}")
if len(overlap_aaf) > 0:
    sample = list(overlap_aaf)[:3]
    for s in sample:
        fn, svc = auth_fac_map.get(s, ('?','?'))
        afn = appfac_fac_map.get(s, '?')
        print(f"   {s[:30]}... -> auth.facility_id={fn} appfac.facility_id={afn} svc={svc}")

# Cross-check 4: Read FORMAT A UUIDs from app_mm_application (full 32-char)
print("\n4. Checking if FORMAT A and FORMAT B UUIDs are the same namespace...")
mm_full_ids = set()
with z.open('app_mm_application.dat') as f:
    reader = csv.reader(io.TextIOWrapper(f, 'latin-1'), delimiter='|')
    next(reader)
    for row in reader:
        if len(row) < 9: continue
        aid = row[8].strip()
        if aid and len(aid) > 20:
            mm_full_ids.add(aid)
print(f"   app_mm_application full IDs: {len(mm_full_ids):,}")
overlap_mm_b = mm_full_ids & app_b_ids
print(f"   mm ↔ application.dat: {len(overlap_mm_b):,}")
overlap_mm_auth = mm_full_ids & auth_ids  
print(f"   mm ↔ auth: {len(overlap_mm_auth):,}")

# Cross-check 5: application_facility ↔ auth (direct)
print(f"\n5. application_facility ↔ auth: {len(appfac_ids & auth_ids):,}")

# Quick sample of UUID formats
print(f"\n=== Sample FORMAT B IDs ===")
for label, id_set in [('application.dat', app_b_ids), ('auth', auth_ids), ('appfac', appfac_ids)]:
    sample = list(id_set)[:2]
    for s in sample:
        print(f"  {label}: {s}")

z.close()
