"""Download and analyze CA AG charity registry data on EC2."""
import subprocess, sys

# Step 1: Find all downloadable files
print("=== Downloadable files on CA AG site ===")
result = subprocess.run(
    ["curl", "-s", "https://oag.ca.gov/charities/reports"],
    capture_output=True, text=True, timeout=30
)
import re
matches = re.findall(r'href="([^"]*\.(csv|xls|xlsx|zip))"', result.stdout)
for url in set(m[0] for m in matches):
    if not url.startswith("http"):
        url = "https://oag.ca.gov" + url
    print(f"  {url}")

# Step 2: Download just the CSV that has EIN
print("\n=== Downloading charities-may-operate.csv (48MB) ===")
result = subprocess.run(
    ["curl", "-s", "-r", "0-200000",
     "https://oag.ca.gov/sites/all/files/agweb/pdfs/charities/reports/charities-may-operate.csv"],
    capture_output=True, text=True, timeout=30
)
lines = result.stdout.strip().split("\n")
print(f"Got {len(lines)} lines (first 200KB)")

# Parse CSV header
headers = lines[0].split(",")
print(f"Columns: {headers}")

# Check for email column
email_cols = [h for h in headers if "email" in h.lower()]
print(f"Email columns: {email_cols}")

# Check for FEIN/EIN column
fein_col = None
for i, h in enumerate(headers):
    if "fein" in h.lower() or "ein" in h.lower():
        fein_col = i
        break
print(f"FEIN column index: {fein_col} ({headers[fein_col] if fein_col is not None else 'NONE'})")

# Count how many have EINs matching our CA foundations
import csv
import io

reader = csv.DictReader(io.StringIO(result.stdout))
rows = list(reader)
print(f"\nRows in sample: {len(rows)}")

# Check for email data in any field
email_found = 0
for r in rows[:200]:
    for k, v in r.items():
        if v and "@" in v.strip():
            email_found += 1
            print(f"  EMAIL: [{k}] = {v.strip()[:80]}")

print(f"\nEmails found in sample: {email_found}")

# Step 3: Check for other CSV files that might have contact info
print("\n=== Looking for other charity CSV files ===")
other_csvs = [
    "https://oag.ca.gov/sites/all/files/agweb/pdfs/charities/reports/charities-charitable-orgs.csv",
]
for csv_url in other_csvs:
    try:
        result = subprocess.run(
            ["curl", "-s", "-r", "0-5000", csv_url],
            capture_output=True, text=True, timeout=15
        )
        if result.stdout.strip():
            print(f"  {csv_url}: {result.stdout[:200]}")
    except:
        pass
