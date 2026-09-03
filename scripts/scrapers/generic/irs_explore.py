"""Explore IRS 990 S3 bucket with comprehensive path testing."""
import subprocess, json

BASE = "https://irs-form-990.s3.us-east-1.amazonaws.com"
EINS = ["521951681", "061547852", "237093598"]  # Casey, Buck, MacArthur

# Try many path patterns
patterns = []
for ein in EINS:
    for year in ["2023", "2022", "2021"]:
        patterns.extend([
            f"{ein}_{year}_990PF.xml",
            f"{ein}_{year}_990.xml",
            f"{ein}_{year}.xml",
            f"{ein}_990PF_{year}.xml",
            f"{ein}_{year}_public.xml",
            f"tax_year={year}/ein={ein}/return.xml",
            f"{year}/{ein}.xml",
            f"{year}/{ein}_990PF.xml",
            f"990PF/{year}/{ein}.xml",
            f"returns/{year}/{ein}.xml",
            f"{ein}/{year}_990PF.xml",
            f"{ein}/{year}/990PF.xml",
            f"{ein}/{year}/return.xml",
            f"{ein}/990PF_{year}.xml",
        ])

found = []
for path in patterns:
    url = f"{BASE}/{path}"
    result = subprocess.run(
        ["curl", "-sI", url], capture_output=True, text=True, timeout=10
    )
    status_line = result.stdout.split("\n")[0] if result.stdout else ""
    if "200" in status_line or "206" in status_line:
        found.append((path, status_line))
        print(f"  ✅ FOUND: {path}")

if not found:
    print("No files found with any pattern. Let me check the root directory listing...")
    # Try listing with prefix
    for ein in EINS[:1]:
        result = subprocess.run(
            ["curl", "-s", f"{BASE}/?prefix={ein}/&max-keys=5"],
            capture_output=True, text=True, timeout=15
        )
        print(f"\nPrefix listing for {ein}/:")
        print(result.stdout[:1000] if result.stdout else "Empty")
