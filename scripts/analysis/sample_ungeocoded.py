import sqlite3, csv

DB = "E:/grid/churches.db"
OUT = "E:/grid/data/ungeocoded_sample_500.csv"

db = sqlite3.connect(DB)
rows = db.execute("""
    SELECT id, name, address, city, state, zip, county_name
    FROM churches 
    WHERE source='churchunion_scraper' 
      AND (latitude IS NULL OR latitude = 0)
    ORDER BY id
    LIMIT 500
""").fetchall()

with open(OUT, "w", newline="", encoding="utf-8") as f:
    w = csv.writer(f)
    w.writerow(["id", "name", "address", "city", "state", "zip", "county_name"])
    for r in rows:
        w.writerow(r)

db.close()

# Show first 20 in terminal
print(f"Exported {len(rows):,} rows to {OUT}")
print(f"\nFirst 20 rows:")
for r in rows[:20]:
    print(f"  [{r[0]}] {r[1][:50] if r[1] else '(no name)'}")
    print(f"         {r[2] or '(no addr)'} | {r[3] or '(no city)'}, {r[4] or '(no state)'} {r[5] or ''}")
    if r[6]: print(f"         county: {r[6]}")

# Stats
print(f"\n--- Quick stats ---")
no_addr = sum(1 for r in rows if not r[2])
no_city = sum(1 for r in rows if not r[3])
no_state = sum(1 for r in rows if not r[4])
no_zip = sum(1 for r in rows if not r[5])
po_box = sum(1 for r in rows if r[2] and 'po box' in r[2].lower())
has_united = sum(1 for r in rows if r[2] and 'united states' in r[2].lower())
has_country = sum(1 for r in rows if r[2] and (', us' in r[2].lower() or ', united' in r[2].lower() or ', canada' in r[2].lower()))
has_rr = sum(1 for r in rows if r[2] and ('rr ' in r[2].lower() or 'rural route' in r[2].lower()))
has_hcr = sum(1 for r in rows if r[2] and 'hcr' in r[2].lower())
addr_len = [len(r[2]) for r in rows if r[2]]
print(f"No address: {no_addr}")
print(f"No city: {no_city}")
print(f"No state: {no_state}")
print(f"No zip: {no_zip}")
print(f"PO Box: {po_box}")
print(f"Contains 'United States': {has_united}")
print(f"Contains country suffix: {has_country}")
print(f"Rural Route (RR): {has_rr}")
print(f"HCR (Highway Contract): {has_hcr}")
if addr_len:
    print(f"Avg address length: {sum(addr_len)/len(addr_len):.0f} chars")
    print(f"Max address length: {max(addr_len)} chars")
