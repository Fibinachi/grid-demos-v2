"""Explore LMS dump schema - phase 2"""
import zipfile
import os

ZIP_PATH = os.path.join(os.path.dirname(__file__), '06-23-2026_LMS_Dump.zip')
z = zipfile.ZipFile(ZIP_PATH)

# 1. Find all facility-related tables with size info
print("=== All facility-related tables ===")
for info in z.infolist():
    if 'facility' in info.filename.lower():
        ratio = info.file_size / info.compress_size if info.compress_size > 0 else 1
        print(f"  {info.compress_size:>10,} -> {info.file_size:>10,}  {info.filename}")

print()

# 2. assigned_authorization.dat - this likely links facility_id to licensee
with z.open('assigned_authorization.dat') as f:
    raw = f.read().decode('latin-1')
    lines = raw.split('\n')
    print(f"=== assigned_authorization.dat ===")
    cols = lines[0].split('|')
    print(f"Columns ({len(cols)}):")
    for j, c in enumerate(cols):
        print(f"  [{j}] {c}")
    for i in range(1, min(4, len(lines)-1)):
        print(f"  Row {i}: {lines[i]}")

print()

# 3. facility_applicant.dat - links facilities to applicants
with z.open('facility_applicant.dat') as f:
    raw = f.read().decode('latin-1')
    lines = raw.split('\n')
    print(f"=== facility_applicant.dat ===")
    cols = lines[0].split('|')
    print(f"Columns ({len(cols)}):")
    for j, c in enumerate(cols):
        print(f"  [{j}] {c}")
    for i in range(1, min(4, len(lines)-1)):
        print(f"  Row {i}: {lines[i]}")

print()

# 4. app_location.dat
with z.open('app_location.dat') as f:
    raw = f.read().decode('latin-1')
    lines = raw.split('\n')
    print(f"=== app_location.dat ===")
    cols = lines[0].split('|')
    print(f"Columns ({len(cols)}):")
    for j, c in enumerate(cols):
        print(f"  [{j}] {c}")
    for i in range(1, min(4, len(lines)-1)):
        print(f"  Row {i}: {lines[i]}")

print()

# 5. contact_information.dat
with z.open('contact_information.dat') as f:
    raw = f.read().decode('latin-1')
    lines = raw.split('\n')
    print(f"=== contact_information.dat ===")
    cols = lines[0].split('|')
    print(f"Columns ({len(cols)}):")
    for j, c in enumerate(cols):
        print(f"  [{j}] {c}")
    for i in range(1, min(4, len(lines)-1)):
        print(f"  Row {i}: {lines[i]}")

print()

# 6. app_contact_rep.dat
with z.open('app_contact_rep.dat') as f:
    raw = f.read().decode('latin-1')
    lines = raw.split('\n')
    print(f"=== app_contact_rep.dat ===")
    cols = lines[0].split('|')
    print(f"Columns ({len(cols)}):")
    for j, c in enumerate(cols):
        print(f"  [{j}] {c}")
    for i in range(1, min(4, len(lines)-1)):
        print(f"  Row {i}: {lines[i]}")

print()

# 7. lkp_facility_status.dat
print("=== lkp_facility_status.dat ===")
with z.open('lkp_facility_status.dat') as f:
    for line in f.read().decode('latin-1').split('\n'):
        print(f"  {line}")

print()

# 8. lkp_application_status.dat
print("=== lkp_application_status.dat ===")
with z.open('lkp_application_status.dat') as f:
    for line in f.read().decode('latin-1').split('\n'):
        print(f"  {line}")

z.close()
