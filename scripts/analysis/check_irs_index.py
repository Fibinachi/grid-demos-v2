"""Investigate IRS e-file structure and available indexes."""
import subprocess, json, re, sys

# Step 1: Check the IRS e-file directory listing
print("=== IRS e-file directory ===")
result = subprocess.run(
    ["curl", "-s", "https://www.irs.gov/pub/irs-efile/"],
    capture_output=True, text=True, timeout=30
)
# Find links
links = re.findall(r'href="([^"]+)"', result.stdout)
index_files = [l for l in links if 'index' in l.lower() and ('.json' in l.lower() or '.csv' in l.lower())]
print(f"Index files found: {len(index_files)}")
for f in index_files[:10]:
    print(f"  {f}")

# Also look for year directories
year_dirs = [l for l in links if re.match(r'^\d{4}/$', l)]
print(f"\nYear directories: {len(year_dirs)}")
for d in year_dirs[:20]:
    print(f"  {d}")

# Check for available index formats
print("\n=== Checking index.json ===")
if 'index.json' in links:
    result = subprocess.run(
        ["curl", "-s", "https://www.irs.gov/pub/irs-efile/index.json"],
        capture_output=True, text=True, timeout=30
    )
    if result.stdout.strip():
        try:
            data = json.loads(result.stdout)
            print(f"index.json: {len(data)} entries" if isinstance(data, list) else f"Type: {type(data)}")
            if isinstance(data, list) and len(data) > 0:
                print(f"First entry keys: {list(data[0].keys()) if isinstance(data[0], dict) else data[0]}")
        except:
            print(f"Raw: {result.stdout[:200]}")
    else:
        print("Empty response")

print("\n=== Checking index_2025.json ===")
for year in ['2025', '2024', '2023']:
    url = f"https://www.irs.gov/pub/irs-efile/index_{year}.json"
    result = subprocess.run(
        ["curl", "-s", "-r", "0-5000", url],
        capture_output=True, text=True, timeout=15
    )
    if result.stdout.strip():
        print(f"  [{year}] Available: {result.stdout[:200]}")
    else:
        print(f"  [{year}] Not found")

print("\n=== Checking for CSV index ===")
for name in ['index.csv', 'index.txt', 'index_2025.csv']:
    url = f"https://www.irs.gov/pub/irs-efile/{name}"
    result = subprocess.run(
        ["curl", "-s", "-r", "0-5000", url],
        capture_output=True, text=True, timeout=15
    )
    if result.stdout.strip():
        print(f"  [{name}] Available: {result.stdout[:200]}")
    else:
        print(f"  [{name}] Not found")
