"""Check pastor names across both databases"""
import sqlite3, os

# Local DB
local_db = os.path.join(os.path.dirname(os.path.abspath(__file__)), "churches.db")
conn = sqlite3.connect(local_db)
cur = conn.cursor()
cur.execute("SELECT COUNT(*) FROM churches WHERE pastors != '' AND pastors IS NOT NULL")
local_pastors = cur.fetchone()[0]
cur.execute("SELECT COUNT(*) FROM churches")
local_total = cur.fetchone()[0]
print(f"Local DB: {local_total:,} total, {local_pastors:,} with pastor names")
cur.execute("SELECT pastors FROM churches WHERE pastors != '' LIMIT 3")
for r in cur.fetchall():
    print(f"  e.g.: {r[0][:60]}")
conn.close()

# Also check the extracted pastors file
irs_pastors = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "irs", "irs_pastors.csv")
if os.path.exists(irs_pastors):
    import csv
    with open(irs_pastors) as f:
        pastors = list(csv.DictReader(f))
    print(f"\nIRS pastors file: {len(pastors):,} records")
    if pastors:
        print(f"  e.g.: {pastors[0].get('pastor_ico','')[:60]}")
else:
    print(f"\nNo irs_pastors.csv found at {irs_pastors}")
