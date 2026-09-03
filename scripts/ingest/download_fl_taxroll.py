"""Download all 67 Florida NAL 2025 county tax roll ZIP files."""
import os, urllib.request, time

DEST = r"E:\grid\data\fl_taxroll\2025"
os.makedirs(DEST, exist_ok=True)

URLS = [
    "Alachua 11 Final NAL 2025.zip", "Baker 12 Final NAL 2025.zip", "Bay 13 Final NAL 2025.zip",
    "Bradford 14 Final NAL 2025.zip", "Brevard 15 Final NAL 2025.zip", "Broward 16 Final NAL 2025.zip",
    "Calhoun 17 Final NAL 2025.zip", "Charlotte 18 Final NAL 2025.zip", "Citrus 19 Final NAL 2025.zip",
    "Clay 20 Final NAL 2025.zip", "Collier 21 Final NAL 2025.zip", "Columbia 22 Final NAL 2025.zip",
    "Dade 23 Final NAL 2025.zip", "Desoto 24 Final NAL 2025.zip", "Dixie 25 Final NAL 2025.zip",
    "Duval 26 Final NAL 2025.zip", "Escambia 27 Final NAL 2025.zip", "Flagler 28 Final NAL 2025.zip",
    "Franklin 29 Final NAL 2025.zip", "Gadsden 30 Final NAL 2025.zip", "Gilchrist 31 Final NAL 2025.zip",
    "Glades 32 Final NAL 2025.zip", "Gulf 33 Final NAL 2025.zip", "Hamilton 34 Final NAL 2025.zip",
    "Hardee 35 Final NAL 2025.zip", "Hendry 36 Final NAL 2025.zip", "Hernando 37 Final NAL 2025.zip",
    "Highlands 38 Final NAL 2025.zip", "Hillsborough 39 Final NAL 2025.zip", "Holmes 40 Final NAL 2025.zip",
    "Indian River 41 Final NAL 2025.zip", "Jackson 42 Final NAL 2025.zip", "Jefferson 43 Final NAL 2025.zip",
    "Lafayette 44 Final NAL 2025.zip", "Lake 45 Final NAL 2025.zip", "Lee 46 Final NAL 2025.zip",
    "Leon 47 Final NAL 2025.zip", "Levy 48 Final NAL 2025.zip", "Liberty 49 Final NAL 2025.zip",
    "Madison 50 Final NAL 2025.zip", "Manatee 51 Final NAL 2025.zip", "Marion 52 Final NAL 2025.zip",
    "Martin 53 Final NAL 2025.zip", "Monroe 54 Final NAL 2025.zip", "Nassau 55 Final NAL 2025.zip",
    "Okaloosa 56 Final NAL 2025.zip", "Okeechobee 57 Final NAL 2025.zip", "Orange 58 Final NAL 2025.zip",
    "Osceola 59 Final NAL 2025.zip", "Palm Beach 60 Final NAL 2025.zip", "Pasco 61 Final NAL 2025.zip",
    "Pinellas 62 Final NAL 2025.zip", "Polk 63 Final NAL 2025.zip", "Putnam 64 Final NAL 2025.zip",
    "Santa Rosa 65 Final NAL 2025.zip", "Sarasota 66 Final NAL 2025.zip", "Seminole 67 Final NAL 2025.zip",
    "St. Johns 68 Final NAL 2025.zip", "St. Lucie 69 Final NAL 2025.zip", "Sumter 70 Final NAL 2025.zip",
    "Suwannee 71 Final NAL 2025.zip", "Taylor 72 Final NAL 2025.zip", "Union 73 Final NAL 2025.zip",
    "Volusia 74 Final NAL 2025.zip", "Wakulla 75 Final NAL 2025.zip", "Walton 76 Final NAL 2025.zip",
    "Washington 77 Final NAL 2025.zip",
]

BASE = "https://floridarevenue.com/property/dataportal/Documents/PTO%20Data%20Portal/Tax%20Roll%20Data%20Files/NAL/2025F/"

downloaded = 0
failed = 0
skipped = 0

for i, fname in enumerate(URLS):
    outfile = os.path.join(DEST, fname)
    if os.path.exists(outfile):
        skipped += 1
        continue
    
    url = BASE + fname.replace(" ", "%20")
    print(f"[{i+1:2d}/{len(URLS)}] {fname[:40]:40s}", end=" ", flush=True)
    
    try:
        urllib.request.urlretrieve(url, outfile)
        size_mb = os.path.getsize(outfile) / (1024*1024)
        print(f"OK ({size_mb:.1f} MB)")
        downloaded += 1
    except Exception as e:
        print(f"FAIL: {e}")
        failed += 1
    
    time.sleep(0.3)  # Be polite

print(f"\nDone: {downloaded} downloaded, {skipped} skipped, {failed} failed")
print(f"Files in {DEST}: {len(os.listdir(DEST))}")
