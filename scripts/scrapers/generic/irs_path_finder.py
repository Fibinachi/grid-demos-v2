"""Find correct IRS 990 S3 paths by trying all known patterns."""
import subprocess, sys

BASE = "https://irs-form-990.s3.us-east-1.amazonaws.com"
EINS = ["521951681", "061547852", "237093598"]
YEARS = ["2024", "2023", "2022", "2021", "2020"]
TYPES = ["990PF", "990", "990EZ"]
SUFFIXES = ["", "_1", "_01", "_0", "_public", ""]

patterns = []
for ein in EINS:
    for yr in YEARS:
        for t in TYPES:
            for suf in SUFFIXES:
                if suf and not suf.startswith("_"):
                    continue
                # Pattern: /EIN/EIN_YYYY_TYPEsuf.xml  
                patterns.append(f"{ein}/{ein}_{yr}_{t}{suf}.xml")
                # Pattern: /EIN_YYYY_TYPEsuf.xml
                patterns.append(f"{ein}_{yr}_{t}{suf}.xml")
                # Pattern: /YYYY/EIN_YYYY_TYPEsuf.xml
                patterns.append(f"{yr}/{ein}_{yr}_{t}{suf}.xml")

found = []
tested = set()
for path in patterns:
    if path in tested:
        continue
    tested.add(path)
    url = f"{BASE}/{path}"
    result = subprocess.run(
        ["curl", "-sI", url], capture_output=True, text=True, timeout=10
    )
    for line in result.stdout.split("\n"):
        if "200 OK" in line or "206 Partial" in line or "403" in line:
            found.append((path, line.strip()))
            print(f"  {line.strip()}: {path[:80]}")
            break

if not found:
    print("No files found with standard patterns.")
    print("\nTrying index files...")
    for name in ["index.json", "index.csv", "Index.csv", "returns.json"]:
        url = f"{BASE}/{name}"
        result = subprocess.run(
            ["curl", "-sI", url], capture_output=True, text=True, timeout=10
        )
        for line in result.stdout.split("\n"):
            if "200" in line or "206" in line:
                print(f"  ✅ {line.strip()}: {name}")
                break
            elif "404" not in line and line.strip():
                pass

print(f"\nTested {len(tested)} patterns, found {len(found)} matches")
