"""
Link Catholic churches to dioceses by nearest bishop's seat (cathedral).
This is how real diocesan geography works — parishes cluster around the cathedral.
"""
import sqlite3
import numpy as np
from scipy.spatial import cKDTree

DB = "E:/grid/churches.db"
CHUNK_SIZE = 500

db = sqlite3.connect(DB)
db.row_factory = sqlite3.Row

# ── Step 1: Find bishop seats (cathedrals with GPS) ──
print("Finding bishop seats...")
seats = db.execute("""
    SELECT dio.id as diocese_id, dio.name as diocese_name, dio.cath_type,
           dio.archdiocese, cat.name as cathedral_name,
           c.latitude, c.longitude, c.country
    FROM catholic_hierarchy dio
    JOIN catholic_hierarchy cat ON cat.parent_id = dio.id AND cat.cath_type = 'cathedral'
    JOIN churches c ON cat.church_id = c.id
    WHERE dio.cath_type IN ('diocese', 'archdiocese')
      AND c.latitude IS NOT NULL AND c.longitude IS NOT NULL
""").fetchall()
print(f"Bishop seats with GPS: {len(seats)}")

# Build spatial index
coords = np.array([(s["latitude"], s["longitude"]) for s in seats])
lat_rad = np.radians(coords[:, 0])
lon_rad = np.radians(coords[:, 1])
cart = np.column_stack([
    np.cos(lat_rad) * np.cos(lon_rad),
    np.cos(lat_rad) * np.sin(lon_rad),
    np.sin(lat_rad)
])
tree = cKDTree(cart)
print(f"Spatial index built: {len(seats)} seats")

# ── Step 2: Get unlinked Catholic churches ──
print("Loading unlinked Catholic churches...")
unlinked = db.execute("""
    SELECT c.id, c.name, c.city, c.state, c.country, c.latitude, c.longitude
    FROM churches c
    WHERE c.taxonomy_id IN (14,86,92,100)
      AND c.id NOT IN (SELECT church_id FROM catholic_hierarchy WHERE church_id IS NOT NULL)
      AND c.latitude IS NOT NULL AND c.longitude IS NOT NULL
""").fetchall()
print(f"Unlinked: {len(unlinked):,}")

# ── Step 3: Nearest bishop seat for each church ──
print("Computing nearest bishop seats...")
inserts = []
too_far = 0
MAX_DIST_KM = 500  # max reasonable diocese radius

for ch in unlinked:
    lat_r = np.radians(ch["latitude"])
    lon_r = np.radians(ch["longitude"])
    x = np.cos(lat_r) * np.cos(lon_r)
    y = np.cos(lat_r) * np.sin(lon_r)
    z = np.sin(lat_r)
    
    dist, idx = tree.query([x, y, z], k=1)
    dist_km = dist * 6371
    
    if dist_km > MAX_DIST_KM:
        too_far += 1
        continue
    
    seat = seats[idx]
    pinfo = seat
    
    if pinfo["cath_type"] == "archdiocese":
        dname = aname = pinfo["diocese_name"]
    else:
        dname = pinfo["diocese_name"]
        aname = pinfo["archdiocese"] or pinfo["diocese_name"]
    
    inserts.append((
        seat["diocese_id"], ch["id"], ch["name"], ch["name"], "parish",
        dname, aname,
        ch["city"], ch["state"], ch["country"],
        ch["latitude"], ch["longitude"],
        seat["cath_type"], "belongs_to_diocese",
        f"spatial: {dist_km:.0f}km to {seat['cathedral_name']} ({seat['diocese_name']})"
    ))

print(f"Within {MAX_DIST_KM}km of a bishop seat: {len(inserts):,}")
print(f"Too far (> {MAX_DIST_KM}km): {too_far:,}")

if not inserts:
    print("Nothing to insert!")
    db.close()
    exit()

# ── Step 4: Insert ──
print(f"\nInserting {len(inserts):,} parish links...")
for i in range(0, len(inserts), CHUNK_SIZE):
    batch = inserts[i:i+CHUNK_SIZE]
    db.executemany("""
        INSERT INTO catholic_hierarchy 
        (parent_id, church_id, name, original_name, cath_type, diocese, archdiocese,
         city, state, country, lat, lon, parent_cath_type, relationship, notes)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, batch)
    db.commit()
    if (i + CHUNK_SIZE) % 10000 == 0:
        print(f"  {min(i+CHUNK_SIZE, len(inserts)):,}/{len(inserts):,}")

# ── Final stats ──
linked = db.execute("SELECT COUNT(DISTINCT church_id) FROM catholic_hierarchy WHERE cath_type='parish'").fetchone()[0]
total = db.execute("SELECT COUNT(1) FROM churches WHERE taxonomy_id IN (14,86,92,100)").fetchone()[0]
still = db.execute("""
    SELECT COUNT(1) FROM churches WHERE taxonomy_id IN (14,86,92,100)
      AND id NOT IN (SELECT church_id FROM catholic_hierarchy WHERE church_id IS NOT NULL)
""").fetchone()[0]

print(f"\n=== FINAL ===")
print(f"Linked: {linked:,} / {total:,} ({linked*100/max(total,1):.1f}%)")
print(f"Still unlinked: {still:,}")

# US
us_linked = db.execute("""
    SELECT COUNT(DISTINCT ch.church_id) FROM catholic_hierarchy ch
    JOIN churches c ON ch.church_id = c.id
    WHERE ch.cath_type='parish' AND c.country='US'
""").fetchone()[0]
us_total = db.execute("SELECT COUNT(1) FROM churches WHERE country='US' AND taxonomy_id IN (14,86,92,100)").fetchone()[0]
print(f"US: {us_linked:,} / {us_total:,} ({us_linked*100/max(us_total,1):.1f}%)")

db.close()
