"""
Reverse-geocode ALL churches globally missing city using NE 1:10m cities.
Uses temp table for fast bulk UPDATE.
"""
import sqlite3, numpy as np, geopandas as gpd
from scipy.spatial import KDTree
from tqdm import tqdm

print('=== Loading Natural Earth 1:10m Populated Places ===')
gdf = gpd.read_file('data/natural_earth/ne_10m_populated_places.shp')
print(f'Total cities: {len(gdf):,}')

cities = [(str(r.get('NAME','') or '').strip(), r.geometry.y, r.geometry.x) 
          for _, r in gdf.iterrows() if r.geometry and str(r.get('NAME','') or '').strip()]
print(f'Loaded {len(cities):,} cities')

print('\n=== Building KD-tree ===')
coords = np.radians([(c[1], c[2]) for c in cities])
tree = KDTree(coords)

def nc(lat, lon, max_km=15):
    d, i = tree.query(np.radians([[lat, lon]]), k=1)
    d_km = float(d[0]) * 6371
    return cities[i[0]][0] if d_km <= max_km else None

print('\n=== Connecting to DB ===')
db = sqlite3.connect('churches.db')
cur = db.cursor()

# Create temp table
cur.execute("DROP TABLE IF EXISTS _tmp_city_fix")
cur.execute("CREATE TABLE _tmp_city_fix (id INTEGER PRIMARY KEY, city TEXT)")
db.commit()

cur.execute("SELECT COUNT(*) FROM churches WHERE (city IS NULL OR city='') AND latitude IS NOT NULL")
total = cur.fetchone()[0]
print(f'Churches needing city: {total:,}')

CHUNK = 10000
offset = 0
assigned = 0
nocities = 0
batch = []

while offset < total:
    cur.execute("SELECT id, latitude, longitude FROM churches WHERE (city IS NULL OR city='') AND latitude IS NOT NULL LIMIT ? OFFSET ?", (CHUNK, offset))
    rows = cur.fetchall()
    if not rows: break
    for r in rows:
        cn = nc(r[1], r[2])
        if cn:
            batch.append((r[0], cn))
            assigned += 1
        else:
            nocities += 1
    if len(batch) >= 5000:
        cur.executemany("INSERT OR REPLACE INTO _tmp_city_fix VALUES (?,?)", batch)
        db.commit()
        batch = []
    offset += len(rows)
    print(f'  {offset:,}/{total:,} - {assigned:,} assigned ({assigned/(assigned+nocities)*100:.0f}%)')

if batch:
    cur.executemany("INSERT OR REPLACE INTO _tmp_city_fix VALUES (?,?)", batch)
    db.commit()

print(f'\n=== Bulk UPDATE ===')
cur.execute("""UPDATE churches SET city = (SELECT city FROM _tmp_city_fix WHERE _tmp_city_fix.id = churches.id) 
               WHERE EXISTS (SELECT 1 FROM _tmp_city_fix WHERE _tmp_city_fix.id = churches.id)""")
updated = cur.rowcount
db.commit()
print(f'Updated {updated:,} churches')

cur.execute("DROP TABLE IF EXISTS _tmp_city_fix")
db.commit()

cur.execute("SELECT COUNT(*) FROM churches WHERE city IS NOT NULL AND city != ''")
wc = cur.fetchone()[0]
cur.execute("SELECT COUNT(*) FROM churches")
ta = cur.fetchone()[0]
print(f'\nFinal: {wc:,}/{ta:,} with city ({wc/ta*100:.1f}%)')
print(f'Assigned: {assigned:,} | No match: {nocities:,}')

db.close()
