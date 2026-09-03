"""Full scan: compute exact join counts between all three key tables."""
import zipfile, os, csv, io, sys

ZIP_PATH = os.path.join(os.path.dirname(__file__), '06-23-2026_LMS_Dump.zip')
z = zipfile.ZipFile(ZIP_PATH)

# Read headers
def find_col(headers, name):
    for i, col in enumerate(headers):
        if col.strip() == name:
            return i
    return None

with z.open('app_mm_application.dat') as f:
    h = f.readline().decode('latin-1').split('|')
idx_mm_app_id = find_col(h, 'aapp_application_id')
idx_main_station_filing_id = find_col(h, 'main_station_filing_id')
idx_aapp_rsou = find_col(h, 'aapp_rsou_source_code')
print(f"app_mm: app_id={idx_mm_app_id} filing_id={idx_main_station_filing_id} rsou={idx_aapp_rsou}")

with z.open('assigned_authorization.dat') as f:
    h = f.readline().decode('latin-1').split('|')
idx_auth_app_id = find_col(h, 'application_id')
idx_auth_fac_id = find_col(h, 'facility_id')
idx_auth_file_num = find_col(h, 'file_number')
print(f"auth: app_id={idx_auth_app_id} fac_id={idx_auth_fac_id} file_num={idx_auth_file_num}")

with z.open('app_location.dat') as f:
    h = f.readline().decode('latin-1').split('|')
idx_loc_app_id = find_col(h, 'aloc_aapp_application_id')
idx_loc_wkb = find_col(h, 'aloc_geo_coord')
print(f"loc: app_id={idx_loc_app_id} wkb={idx_loc_wkb}")

with z.open('facility.dat') as f:
    h = f.readline().decode('latin-1').split('|')
idx_fac_id = find_col(h, 'facility_id')
idx_fac_svc = find_col(h, 'service_code')
idx_fac_uuid = find_col(h, 'facility_uuid')
print(f"fac: fac_id={idx_fac_id} svc={idx_fac_svc} uuid={idx_fac_uuid}")

print("\n=== Collecting app_mm_application IDs ===")
sys.stdout.flush()
mm_ids = {}
with z.open('app_mm_application.dat') as f:
    reader = csv.reader(io.TextIOWrapper(f, 'latin-1'), delimiter='|')
    next(reader)
    for row in reader:
        if len(row) <= idx_mm_app_id: continue
        aid = row[idx_mm_app_id].strip()
        if not aid: continue
        fn = row[idx_main_station_filing_id].strip() if idx_main_station_filing_id is not None and len(row) > idx_main_station_filing_id else ''
        mm_ids[aid] = fn
print(f"  {len(mm_ids):,} IDs")

print("=== Collecting assigned_authorization ===")
sys.stdout.flush()
auth_info = {}
with z.open('assigned_authorization.dat') as f:
    reader = csv.reader(io.TextIOWrapper(f, 'latin-1'), delimiter='|')
    next(reader)
    for row in reader:
        if len(row) <= idx_auth_app_id: continue
        aid = row[idx_auth_app_id].strip()
        if not aid: continue
        fid = row[idx_auth_fac_id].strip() if len(row) > idx_auth_fac_id else ''
        fn = row[idx_auth_file_num].strip() if idx_auth_file_num is not None and len(row) > idx_auth_file_num else ''
        auth_info[aid] = (fid, fn)
print(f"  {len(auth_info):,} entries")

print("=== Collecting app_location coords ===")
sys.stdout.flush()
loc_ids = set()
loc_wkbs = {}
with z.open('app_location.dat') as f:
    reader = csv.reader(io.TextIOWrapper(f, 'latin-1'), delimiter='|')
    next(reader)
    for row in reader:
        if len(row) <= idx_loc_app_id: continue
        aid = row[idx_loc_app_id].strip()
        if not aid: continue
        wkb = row[idx_loc_wkb].strip() if idx_loc_wkb is not None and len(row) > idx_loc_wkb else ''
        if len(wkb) > 20:
            loc_ids.add(aid)
            loc_wkbs[aid] = wkb
print(f"  {len(loc_ids):,} with coords")

print("=== Collecting facility info ===")
sys.stdout.flush()
fac_info = {}
with z.open('facility.dat') as f:
    reader = csv.reader(io.TextIOWrapper(f, 'latin-1'), delimiter='|')
    next(reader)
    for row in reader:
        if len(row) <= idx_fac_id: continue
        fid = row[idx_fac_id].strip()
        if not fid: continue
        svc = row[idx_fac_svc].strip() if len(row) > idx_fac_svc else ''
        uuid = row[idx_fac_uuid].strip() if idx_fac_uuid is not None and len(row) > idx_fac_uuid else ''
        fac_info[fid] = (svc, uuid)
print(f"  {len(fac_info):,} facilities")

# === Compute join chain ===
print("\n=== JOIN CHAIN ===")
loc_mm_overlap = loc_ids & set(mm_ids.keys())
print(f"1. loc -> mm: {len(loc_mm_overlap):,}/{len(loc_ids):,}")

auth_keys_set = set(auth_info.keys())

# Full chain validation
full_chain = 0
full_by_svc = {}
for aid in loc_ids:
    if aid in auth_info:
        fid, fn = auth_info[aid]
        if fid in fac_info:
            full_chain += 1
            svc, uuid = fac_info[fid]
            full_by_svc[svc] = full_by_svc.get(svc, 0) + 1
print(f"2. Full chain (loc->auth->fac): {full_chain:,}")
for svc in sorted(full_by_svc.keys()):
    print(f"   {svc:6s}: {full_by_svc[svc]:,}")

# Direct loc->auth
direct = loc_ids & auth_keys_set
direct_by_svc = {}
for aid in direct:
    fid, fn = auth_info[aid]
    if fid in fac_info:
        svc, uuid = fac_info[fid]
        direct_by_svc[svc] = direct_by_svc.get(svc, 0) + 1
print(f"3. Direct loc->auth: {len(direct):,}")
for svc in sorted(direct_by_svc.keys()):
    print(f"   {svc:6s}: {direct_by_svc[svc]:,}")

# file_number overlap
auth_fn_map = {}
for aid, (fid, fn) in auth_info.items():
    if fn:
        auth_fn_map.setdefault(fn, set()).add((aid, fid))

mm_fn_map = {}
for aid, fn in mm_ids.items():
    if fn:
        mm_fn_map.setdefault(fn, set()).add(aid)

fn_overlap = set(auth_fn_map.keys()) & set(mm_fn_map.keys())
print(f"\n4. file_number overlap: {len(fn_overlap):,}")
fn_extra = set()
for aid in loc_ids:
    fn = mm_ids.get(aid, '')
    if fn and fn in auth_fn_map:
        fn_extra.add(aid)
print(f"   Locations reachable via file_number: {len(fn_extra):,}")
print(f"   New (not in direct): {len(fn_extra - direct):,}")

# Broadcast service codes quick scan
broadcast_svcs = {'FL', 'FM', 'AM', 'FX', 'FB', 'FS'}
print(f"\n5. Total facilities by broadcast service:")
for sc in broadcast_svcs:
    cnt = sum(1 for fid, (svc, uuid) in fac_info.items() if svc == sc)
    print(f"   {sc:6s}: {cnt:,}")

z.close()
