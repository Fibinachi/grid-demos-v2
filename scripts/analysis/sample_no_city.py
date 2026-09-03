import sqlite3, csv, os
from datetime import datetime

DB = "E:/grid/churches.db"
OUT = "E:/grid/reports/ungeocoded_no_city_state_100.csv"
os.makedirs("E:/grid/reports", exist_ok=True)

db = sqlite3.connect(DB)

# Top-level stats
total = db.execute("SELECT COUNT(1) FROM churches").fetchone()[0]
geo = db.execute("SELECT COUNT(1) FROM churches WHERE latitude IS NOT NULL AND latitude != 0").fetchone()[0]
need = db.execute("SELECT COUNT(1) FROM churches WHERE latitude IS NULL OR latitude = 0").fetchone()[0]
need_no_city = db.execute("SELECT COUNT(1) FROM churches WHERE (latitude IS NULL OR latitude = 0) AND (city IS NULL OR city = '' OR state IS NULL OR state = '')").fetchone()[0]
need_with_city = db.execute("SELECT COUNT(1) FROM churches WHERE (latitude IS NULL OR latitude = 0) AND city IS NOT NULL AND city != '' AND state IS NOT NULL AND state != ''").fetchone()[0]

# Sample 100 with no city/state
rows = db.execute("""
    SELECT id, name, address, city, state, zip, source, denomination, county_name, country
    FROM churches 
    WHERE (latitude IS NULL OR latitude = 0)
      AND (city IS NULL OR city = '' OR state IS NULL OR state = '')
    ORDER BY id
    LIMIT 100
""").fetchall()

cols = ["id", "name", "address", "city", "state", "zip", "source", "denomination", "county_name", "country"]
with open(OUT, "w", newline="", encoding="utf-8") as f:
    w = csv.writer(f)
    w.writerow(cols)
    for r in rows:
        w.writerow(r)

# Stats for the 100
sources = {}
denoms = {}
countries = {}
for r in rows:
    src = r[6] or "(none)"; sources[src] = sources.get(src, 0) + 1
    den = r[7] or "(none)"; denoms[den] = denoms.get(den, 0) + 1
    cty = r[9] or "(none)"; countries[cty] = countries.get(cty, 0) + 1

print(f"Report: {OUT}")
print(f"DB: {total:,} total | {geo:,} geocoded ({geo*100/total:.0f}%) | {need:,} remain")
print(f"  No city/state: {need_no_city:,}")
print(f"  Have city/state: {need_with_city:,}")
print(f"\nSample of 100 no-city/state rows:")
print(f"  Sources: {dict(sorted(sources.items(), key=lambda x:-x[1]))}")
print(f"  Top denominations: {dict(sorted(denoms.items(), key=lambda x:-x[1])[:8])}")
print(f"  Countries: {countries}")
print(f"\nFirst 15 rows:")
for r in rows[:15]:
    print(f"  [{r[0]}] {str(r[1])[:50]} | src={r[6]} | denom={r[7]} | country={r[9]}")
    print(f"         addr='{str(r[2])[:70]}' | city='{r[3]}' | state='{r[4]}' | zip='{r[5]}'")

db.close()
