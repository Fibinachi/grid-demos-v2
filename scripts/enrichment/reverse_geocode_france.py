"""Fix French postal codes via pgeocode KD-tree nearest-neighbor."""
import sqlite3, sys, os, numpy as np
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from gw_db import connect
import pgeocode
from scipy.spatial import KDTree
from datetime import datetime

db = connect()
cur = db.cursor()

# Find FR records without postal codes
cur.execute("""
    SELECT id, latitude, longitude, city, state
    FROM churches WHERE country='FR'
      AND (zip5 IS NULL OR zip5='')
      AND latitude IS NOT NULL AND latitude!=0
""")
rows = cur.fetchall()
print(f"FR records to fix: {len(rows):,}")

if not rows:
    print("Nothing to do!"); db.close(); exit()

# Load French postal code data
print("Loading French postal codes...")
nomi = pgeocode.Nominatim('fr')
fr_data = nomi._data
fr_data = fr_data[fr_data['latitude'].notna() & fr_data['longitude'].notna()]
print(f"  {len(fr_data):,} entries loaded")

# Build KD-tree
coords = np.column_stack([fr_data['latitude'].values, fr_data['longitude'].values])
tree = KDTree(coords)

# Extract lookup arrays
pcs = fr_data['postal_code'].values
places = fr_data['place_name'].values
regions = fr_data['state_name'].values

now = datetime.now().isoformat()
CHUNK = 500
batch = []
fixed = 0

for i, (cid, lat, lon, old_city, old_state) in enumerate(rows):
    dist, idx = tree.query([lat, lon])
    idx = int(idx)
    
    zip5 = str(pcs[idx])
    city = str(places[idx]) if places[idx] and str(places[idx]) != 'nan' else None
    region = str(regions[idx]) if regions[idx] and str(regions[idx]) != 'nan' else None
    
    batch.append((zip5, city, region, cid))
    
    if len(batch) >= CHUNK:
        for z, ct, rg, cid2 in batch:
            cur.execute("UPDATE churches SET zip5=?, last_updated=? WHERE id=?", (z, now, cid2))
            if ct:
                cur.execute("UPDATE churches SET city=?, last_updated=? WHERE id=?", (ct, now, cid2))
            if rg:
                cur.execute("UPDATE churches SET state=?, last_updated=? WHERE id=?", (rg, now, cid2))
        db.commit()
        fixed += len(batch)
        print(f"  {fixed:,} / {len(rows):,}")
        batch = []

# Final
if batch:
    for z, ct, rg, cid2 in batch:
        cur.execute("UPDATE churches SET zip5=?, last_updated=? WHERE id=?", (z, now, cid2))
        if ct:
            cur.execute("UPDATE churches SET city=?, last_updated=? WHERE id=?", (ct, now, cid2))
        if rg:
            cur.execute("UPDATE churches SET state=?, last_updated=? WHERE id=?", (rg, now, cid2))
    db.commit()
    fixed += len(batch)

cur.execute("SELECT COUNT(*) FROM churches WHERE country='FR' AND (zip5 IS NULL OR zip5='')")
remaining = cur.fetchone()[0]
print(f"\nFixed: {fixed:,}  |  Still missing ZIP: {remaining:,}")
db.close()
print("Done.")
