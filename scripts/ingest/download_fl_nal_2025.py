"""Download all 67 Florida county 2025 Final NAL tax roll ZIP files."""
import urllib.request
import os
import time

DEST = r"E:\grid\data\sources\FL_2025_tax_rolls"
os.makedirs(DEST, exist_ok=True)

# All 67 Florida counties from FL DOR 2025F NAL page
COUNTIES = [
    ("Alachua", 11), ("Baker", 12), ("Bay", 13), ("Bradford", 14),
    ("Brevard", 15), ("Broward", 16), ("Calhoun", 17), ("Charlotte", 18),
    ("Citrus", 19), ("Clay", 20), ("Collier", 21), ("Columbia", 22),
    ("Dade", 23), ("Desoto", 24), ("Dixie", 25), ("Duval", 26),
    ("Escambia", 27), ("Flagler", 28), ("Franklin", 29), ("Gadsden", 30),
    ("Gilchrist", 31), ("Glades", 32), ("Gulf", 33), ("Hamilton", 34),
    ("Hardee", 35), ("Hendry", 36), ("Hernando", 37), ("Highlands", 38),
    ("Hillsborough", 39), ("Holmes", 40), ("Indin River", 41), ("Jackson", 42),
    ("Jefferson", 43), ("Lafayette", 44), ("Lake", 45), ("Lee", 46),
    ("Leon", 47), ("Levy", 48), ("Liberty", 49), ("Madison", 50),
    ("Manatee", 51), ("Marion", 52), ("Martin", 53), ("Monroe", 54),
    ("Nassau", 55), ("Okaloosa", 56), ("Okeechobee", 57), ("Orange", 58),
    ("Osceola", 59), ("Palm Beach", 60), ("Pasco", 61), ("Pinellas", 62),
    ("Polk", 63), ("Putnam", 64), ("St Johns", 65), ("St Lucie", 66),
    ("Santa Rosa", 67), ("Sarasota", 68), ("Seminole", 69), ("Sumter", 70),
    ("Suwannee", 71), ("Taylor", 72), ("Union", 73), ("Volusia", 74),
    ("Wakulla", 75), ("Walton", 76), ("Washington", 77),
]

BASE = "https://floridarevenue.com/property/dataportal/Documents/PTO%20Data%20Portal/Tax%20Roll%20Data%20Files/NAL/2025F"

total = len(COUNTIES)
for i, (name, num) in enumerate(COUNTIES, 1):
    filename = f"{name} {num} Final NAL 2025.zip"
    outpath = os.path.join(DEST, filename)
    
    if os.path.exists(outpath):
        size_mb = os.path.getsize(outpath) / (1024 * 1024)
        print(f"[{i:2d}/{total}] SKIP (exists, {size_mb:.1f} MB): {filename}")
        continue
    
    url = f"{BASE}/{name.replace(' ', '%20')}%20{num}%20Final%20NAL%202025.zip"
    print(f"[{i:2d}/{total}] Downloading: {filename} ...", flush=True)
    
    try:
        urllib.request.urlretrieve(url, outpath)
        size_mb = os.path.getsize(outpath) / (1024 * 1024)
        print(f"         OK: {size_mb:.1f} MB", flush=True)
    except Exception as e:
        print(f"         FAILED: {e}", flush=True)

print(f"\nDone. Files in: {DEST}")
