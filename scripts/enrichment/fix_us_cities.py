"""
Fix US church cities via direct ZIP match against zip_lookup_us.
"""
import sqlite3

DB = "E:/grid/churches.db"
CHUNK_SIZE = 500

db = sqlite3.connect(DB)
db.row_factory = sqlite3.Row

# Load zip→city map
print("Loading zip_lookup_us...", end=" ", flush=True)
zips = db.execute("SELECT zip, city, state_code FROM zip_lookup_us").fetchall()
zip_to_city = {}
for z in zips:
    if z["zip"]:
        zip_to_city[z["zip"].strip()] = (z["city"], z["state_code"])
print(f"{len(zip_to_city):,} ZIPs loaded")

# Get US churches with a postal_code
print("Loading US churches...", end=" ", flush=True)
churches = db.execute("""
    SELECT id, name, city, state, zip5 as postal_code, latitude, longitude
    FROM churches
    WHERE country='US' AND zip5 IS NOT NULL AND zip5 != ''
""").fetchall()
print(f"{len(churches):,} churches")

# Match
fixes = []
no_zip_match = 0
already_ok = 0

for ch in churches:
    zc = (ch["postal_code"] or "").strip()[:5]
    if zc in zip_to_city:
        zcity, zstate = zip_to_city[zc]
        if ch["city"] != zcity:
            fixes.append((zcity, zstate, ch["id"]))
        else:
            already_ok += 1
    else:
        no_zip_match += 1

print(f"\nAlready correct: {already_ok:,}")
print(f"ZIP match fixes:  {len(fixes):,}")
print(f"No ZIP in lookup: {no_zip_match:,}")

if not fixes:
    print("Nothing to fix!")
    db.close()
    exit()

# Sample
print(f"\n=== SAMPLE FIXES ===")
id_to_ch = {c["id"]: c for c in churches}
for nc, ns, cid in fixes[:20]:
    ch = id_to_ch[cid]
    print(f"  {ch['id']} | {ch['name'][:45]} | {ch['city']} → {nc}, {ns}")

# Commit
print(f"\nCommitting {len(fixes):,} fixes...")
for i in range(0, len(fixes), CHUNK_SIZE):
    batch = fixes[i:i+CHUNK_SIZE]
    db.executemany("UPDATE churches SET city=?, state=?, last_updated=datetime('now') WHERE id=?",
                   [(nc, ns, cid) for nc, ns, cid in batch])
    db.commit()

print(f"Done! {len(fixes):,} city names fixed.")
db.close()
