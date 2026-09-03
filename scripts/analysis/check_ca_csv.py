"""Download and analyze CA AG charity registry CSV."""
import csv, urllib.request, re

url = "https://oag.ca.gov/sites/all/files/agweb/pdfs/charities/reports/charities-may-operate.csv"
req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})

with urllib.request.urlopen(req, timeout=30) as r:
    content = r.read().decode("utf-8", errors="replace")

lines = content.split("\n")
print(f"File size: {len(content):,} bytes")
print(f"Total lines: {len(lines):,}")
print()

reader = csv.DictReader(lines)
rows = list(reader)
print(f"Parsed rows: {len(rows):,}")

keys = list(rows[0].keys()) if rows else []
print(f"Columns ({len(keys)}):")
for k in keys:
    print(f"  - {k}")
print()

# Show first 3 rows
for i, r in enumerate(rows[:3]):
    print(f"Row {i+1}:")
    for k, v in r.items():
        if v.strip():
            print(f"  {k}: {v[:150]}")
    print()

# Check for emails anywhere
print("=== Checking for email addresses across all rows ===")
email_count = 0
for r in rows[:500]:
    for k, v in r.items():
        if v and "@" in v:
            email_count += 1
            print(f"  [{k}] = {v}")

print(f"\nEmails found in first 500 rows: {email_count}")

# Check if there's an EIN column to match against our data
ein_col = None
for k in keys:
    if "ein" in k.lower() or "fein" in k.lower() or "tax" in k.lower():
        ein_col = k
        break
print(f"\nEIN column: {ein_col}")
