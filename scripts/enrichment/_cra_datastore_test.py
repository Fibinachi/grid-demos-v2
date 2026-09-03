"""
Download CRA 2011 charities Identification via CKAN Datastore API.
Filter for religious charities, import into churches.db.
"""
import urllib.request, json, sqlite3, time, os, io

DB_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "..", "churches.db")
db_path = os.path.abspath(DB_PATH)
DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "..", "data", "cra")
os.makedirs(DATA_DIR, exist_ok=True)

RESOURCE_ID = "5e58be8c-8d58-4b99-b643-88852ae2f98f"
CSV_PATH = os.path.join(DATA_DIR, "cra_2011_identification.csv")

# --- Step 1: Check if datastore has the data ---
print("Testing CKAN datastore...")
url = f"https://open.canada.ca/data/api/action/datastore_search?resource_id={RESOURCE_ID}&limit=1"
time.sleep(2)
req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
resp = json.loads(urllib.request.urlopen(req, timeout=30).read())
total = resp["result"]["total"]
fields = [f["id"] for f in resp["result"]["fields"]]
print(f"Total records: {total:,}")
print(f"Fields ({len(fields)}): {fields}")
print(f"\nSample record:")
record = resp["result"]["records"][0]
for k, v in record.items():
    print(f"  {k}: {v}")
