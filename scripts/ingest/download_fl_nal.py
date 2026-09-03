"""
FL DOR NAL Downloader — Phase 1 of FL Religious Parcels Pipeline
Downloads all 67 county NAL ZIP files for the specified year.
Saves to E:\grid\data\fl_dor\nal\{year}\
"""
import requests, os, time, sys, re
from pathlib import Path
from urllib.parse import quote

# --- Config ---
YEAR = "2025"
OUT_DIR = Path(f"E:/grid/data/fl_dor/nal/{YEAR}")
BASE_URL = "https://floridarevenue.com/property/dataportal/Documents/PTO%20Data%20Portal/Tax%20Roll%20Data%20Files/NAL"

# All 67 Florida counties with their DOR code numbers
FL_COUNTIES = [
    ("Alachua", 11), ("Baker", 12), ("Bay", 13), ("Bradford", 14), ("Brevard", 15),
    ("Broward", 16), ("Calhoun", 17), ("Charlotte", 18), ("Citrus", 19), ("Clay", 20),
    ("Collier", 21), ("Columbia", 22), ("Miami-Dade", 23), ("DeSoto", 24), ("Dixie", 25),
    ("Duval", 26), ("Escambia", 27), ("Flagler", 28), ("Franklin", 29), ("Gadsden", 30),
    ("Gilchrist", 31), ("Glades", 32), ("Gulf", 33), ("Hamilton", 34), ("Hardee", 35),
    ("Hendry", 36), ("Hernando", 37), ("Highlands", 38), ("Hillsborough", 39), ("Holmes", 40),
    ("Indian River", 41), ("Jackson", 42), ("Jefferson", 43), ("Lafayette", 44), ("Lake", 45),
    ("Lee", 46), ("Leon", 47), ("Levy", 48), ("Liberty", 49), ("Madison", 50),
    ("Manatee", 51), ("Marion", 52), ("Martin", 53), ("Monroe", 54), ("Nassau", 55),
    ("Okaloosa", 56), ("Okeechobee", 57), ("Orange", 58), ("Osceola", 59), ("Palm Beach", 60),
    ("Pasco", 61), ("Pinellas", 62), ("Polk", 63), ("Putnam", 64), ("St. Johns", 65),
    ("St. Lucie", 66), ("Santa Rosa", 67), ("Sarasota", 68), ("Seminole", 69), ("Sumter", 70),
    ("Suwannee", 71), ("Taylor", 72), ("Union", 73), ("Volusia", 74), ("Wakulla", 75),
    ("Walton", 76), ("Washington", 77),
]

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept": "*/*",
}

OUT_DIR.mkdir(parents=True, exist_ok=True)

def progress_bar(current, total, width=50):
    """Simple ASCII progress bar."""
    pct = current / total if total else 0
    filled = int(width * pct)
    bar = "█" * filled + "░" * (width - filled)
    return f"[{bar}] {current}/{total} ({pct*100:.0f}%)"

def download_county(name, code, year_folder="2025F"):
    """Download a single county NAL ZIP. Returns True on success."""
    # URL-encode the space in filename
    fname = f"{name} {code} Final NAL 2025.zip"
    url = f"{BASE_URL}/{year_folder}/{quote(fname)}"
    out_path = OUT_DIR / fname
    
    if out_path.exists() and out_path.stat().st_size > 1000:
        return "exists"
    
    try:
        r = requests.get(url, headers=HEADERS, timeout=120, stream=True)
        if r.status_code != 200:
            return f"HTTP {r.status_code}"
        
        with open(out_path, "wb") as f:
            for chunk in r.iter_content(8192):
                f.write(chunk)
        
        size_mb = out_path.stat().st_size / (1024 * 1024)
        return f"OK ({size_mb:.1f} MB)"
    except Exception as e:
        return str(e)[:60]

print(f"=== FL DOR NAL Downloader — {len(FL_COUNTIES)} counties ===")
print(f"Target: {OUT_DIR}")
print(f"Year: {YEAR}")
print()

results = {}
for i, (county_name, county_code) in enumerate(FL_COUNTIES):
    result = download_county(county_name, county_code)
    results[county_name] = result
    bar = progress_bar(i + 1, len(FL_COUNTIES), 40)
    status = result[:50]
    print(f"  {bar}  {county_name:20s} → {status}", flush=True)
    if "HTTP" not in result and "Error" not in result:
        time.sleep(0.3)  # Be polite

# Summary
print()
ok = sum(1 for v in results.values() if "OK" in v or v == "exists")
fail = sum(1 for v in results.values() if "HTTP" in v or "Error" in v)
exists = sum(1 for v in results.values() if v == "exists")
print(f"Done: {ok} downloaded, {exists} already existed, {fail} failed, {len(FL_COUNTIES)} total")
print(f"Files in: {OUT_DIR}")
