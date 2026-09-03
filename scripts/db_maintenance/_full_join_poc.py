"""Proof of concept: join app_location coordinates to facility_id via application_facility.
Checks if app_mm_application.aapp_application_id overlaps with application_facility.afac_application_id."""
import zipfile, csv, io

z = zipfile.ZipFile('E:/grid/06-23-2026_LMS_Dump.zip')

# Sample check: overlap between mm_application and application_facility
print("=== Checking overlap: app_mm_application ↔ application_facility ===")
mm_ids = set()
with z.open('app_mm_application.dat') as f:
    reader = csv.reader(io.TextIOWrapper(f, 'latin-1'), delimiter='|')
    next(reader)
    for i, row in enumerate(reader):
        if i >= 20000:
            break
        if len(row) < 9: continue
        aid = row[8].strip()
        if aid:
            mm_ids.add(aid)
print(f"  Sampled {len(mm_ids):,} mm IDs")

overlap_count = 0
fac_ids_found = set()
with z.open('application_facility.dat') as f:
    reader = csv.reader(io.TextIOWrapper(f, 'latin-1'), delimiter='|')
    next(reader)
    for row in reader:
        if len(row) < 6: continue
        aid = row[1].strip()
        fid = row[5].strip()
        if aid in mm_ids:
            overlap_count += 1
            if fid:
                fac_ids_found.add(fid)
print(f"  Overlap in sample: {overlap_count:,}")
print(f"  Unique facility_ids from overlap: {len(fac_ids_found):,}")

# Now do the FULL join: app_location → application_facility → facility
# Strategy: load application_facility into dict (app_id → facility_id)
print("\n=== Loading full application_facility mapping ===")
app_to_fac = {}
with z.open('application_facility.dat') as f:
    reader = csv.reader(io.TextIOWrapper(f, 'latin-1'), delimiter='|')
    next(reader)
    for row in reader:
        if len(row) < 6: continue
        aid = row[1].strip()
        fid = row[5].strip()
        if aid and fid and aid not in app_to_fac:
            app_to_fac[aid] = fid
print(f"  {len(app_to_fac):,} app_id → facility_id mappings")

# Load facility service codes
print("=== Loading facility service codes ===")
fac_service = {}
with z.open('facility.dat') as f:
    reader = csv.reader(io.TextIOWrapper(f, 'latin-1'), delimiter='|')
    next(reader)
    for row in reader:
        if len(row) < 13: continue
        fid = row[12].strip()  # facility_id at col 12 (verified earlier)
        svc = row[25].strip() if len(row) > 25 else ''
        if fid:
            fac_service[fid] = svc
print(f"  {len(fac_service):,} facilities with service codes")

# Now scan app_location, join to facility
print("\n=== Scanning app_location and joining to facility ===")
total_locs = 0
matched = 0
by_svc = {}
with z.open('app_location.dat') as f:
    reader = csv.reader(io.TextIOWrapper(f, 'latin-1'), delimiter='|')
    next(reader)
    for row in reader:
        if len(row) < 15: continue
        aid = row[8].strip()   # aloc_aapp_application_id
        wkb = row[14].strip()  # aloc_geo_coord
        if not aid or len(wkb) < 20:
            continue
        total_locs += 1
        if aid in app_to_fac:
            fid = app_to_fac[aid]
            svc = fac_service.get(fid, '?')
            matched += 1
            by_svc[svc] = by_svc.get(svc, 0) + 1

broadcast_svcs = {'FL', 'FM', 'AM', 'FX', 'FB', 'FS'}
print(f"\n  Total locations with coords: {total_locs:,}")
print(f"  Matched to facility: {matched:,}")
print(f"  Coverage: {100*matched/total_locs:.1f}%")
if matched > 0:
    print(f"\n  By service code:")
    for svc in sorted(by_svc.keys()):
        label = svc if svc else '(empty)'
        print(f"    {label:6s}: {by_svc[svc]:,}")
    for sc in broadcast_svcs:
        print(f"    {sc:6s}: {by_svc.get(sc, 0):,}")

z.close()
print("\nDone!")
