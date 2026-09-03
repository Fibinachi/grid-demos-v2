"""
Download and import CRA 2011 charities Identification data.
The "Identification" CSV has: BN, Legal Name, Operating Name, Address, City, Province, Postal Code, etc.
We filter for religious charities and import into churches.db.
"""
import urllib.request, os, sqlite3, pandas as pd, io, time, json

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data", "cra")
os.makedirs(DATA_DIR, exist_ok=True)

# 2011 Identification CSV - 12MB
RESOURCE_ID = "5e58be8c-8d58-4b99-b643-88852ae2f98f"
DATASET_ID = "8e4fbdda-f73e-4c49-b0f3-79b86d4a81fb"
CSV_PATH = os.path.join(DATA_DIR, "cra_2011_identification.csv")

# --- Step 1: Download if needed ---
if not os.path.exists(CSV_PATH):
    # Try CKAN direct download URL
    url = f"https://open.canada.ca/data/dataset/{DATASET_ID}/resource/{RESOURCE_ID}/download/identification.csv"
    print(f"Downloading: {url}")
    for attempt in range(3):
        time.sleep(2 ** attempt)  # rate limiting
        req = urllib.request.Request(url, headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        })
        try:
            resp = urllib.request.urlopen(req, timeout=60)
            data = resp.read()
            with open(CSV_PATH, "wb") as f:
                f.write(data)
            print(f"  Downloaded {len(data):,} bytes -> {CSV_PATH}")
            break
        except Exception as e:
            print(f"  Attempt {attempt+1}: {type(e).__name__}: {e}")
            if attempt == 2:
                # Try alternate: CKAN datastore dump
                print("  Trying datastore API...")
                alt_url = f"https://open.canada.ca/data/api/action/datastore_search?resource_id={RESOURCE_ID}&limit=1"
                resp = urllib.request.urlopen(urllib.request.Request(alt_url, headers={
                    "User-Agent": "Mozilla/5.0"
                }), timeout=30)
                print(f"  Datastore response: {resp.status}")
else:
    size = os.path.getsize(CSV_PATH)
    print(f"Already downloaded: {CSV_PATH} ({size:,} bytes)")

# --- Step 2: Read and inspect ---
print("\nReading CSV...")
df = pd.read_csv(CSV_PATH, encoding="latin-1", low_memory=False)
print(f"Columns: {list(df.columns)}")
print(f"Rows: {len(df):,}")
print(f"\nFirst 3 rows:")
print(df.head(3).to_string())
print(f"\nDtypes:\n{df.dtypes}")
