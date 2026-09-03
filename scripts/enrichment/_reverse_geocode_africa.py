"""
Reverse-geocode ALL African churches without city using Natural Earth 1:10m.
"""
import sqlite3, os, zipfile, io, numpy as np
from scipy.spatial import KDTree
from tqdm import tqdm

print('=== Step 1: Natural Earth 1:10m Populated Places ===')
ne_zip = 'data/natural_earth/ne_10m_populated_places.zip'
ne_shp = 'data/natural_earth/ne_10m_populated_places.shp'

if not os.path.exists(ne_shp):
    if not os.path.exists(ne_zip):
        import requests
        url = 'https://naciscdn.org/naturalearth/10m/cultural/ne_10m_populated_places.zip'
        print(f'Downloading...')
        r = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'}, timeout=120)
        with open(ne_zip, 'wb') as f: f.write(r.content)
        print(f'Downloaded {len(r.content):,} bytes')
    with zipfile.ZipFile(ne_zip) as z: z.extractall('data/natural_earth/')
    for f in os.listdir('data/natural_earth/'):
        if f.startswith('ne_10m_populated_places') and not f.startswith('ne_10m_populated_places.'):
            src = os.path.join('data/natural_earth', f)
            ext = os.path.splitext(f)[1]
            dst = os.path.join('data/natural_earth', f'ne_10m_populated_places{ext}')
            if src != dst: os.replace(src, dst)
    print('Extracted')

print('\n=== Step 2: Loading African cities ===')
import geopandas as gpd
gdf = gpd.read_file(ne_shp)
print(f'Total cities worldwide: {len(gdf):,}')

africa_iso = {'DZ','LY','TN','MA','EH','EG','SD','SS','ER','DJ','SO','ET','KE','UG','RW','BI','TZ',
              'ZM','ZW','MW','MZ','AO','NA','BW','ZA','LS','SZ','KM','MG','MU','SC','CV','GM','SH',
              'MR','SN','ML','NE','TD','CF','NG','BJ','TG','GH','BF','CI','LR','SL','GN','GW','CM',
              'GA','GQ','CG','CD','ST'}

africa = gdf[gdf['ISO_A2'].isin(africa_iso)].copy()
print(f'African cities: {len(africa):,}')

cities = []
for _, row in africa.iterrows():
    name = str(row.get('NAME', '') or '').strip()
    if row.geometry and name:
        cities.append((name, row.geometry.y, row.geometry.x, row.get('ISO_A2','')))
print(f'Loaded {len(cities):,} African cities')

print('\n=== Step 3: Building KD-tree ===')
coords = np.radians([(c[1], c[2]) for c in cities])
tree = KDTree(coords)

def nearest_city(lat, lon, max_km=25):
    dist, idx = tree.query(np.radians([[lat, lon]]), k=1)
    dist_km = float(dist[0]) * 6371
    if dist_km <= max_km:
        return cities[idx[0]][0], dist_km
    return None, dist_km

print('\n=== Step 4: Reverse geocoding ===')
db = sqlite3.connect('churches.db')
cur = db.cursor()

africa_list = list(africa_iso)
ph = ','.join(['?'] * len(africa_list))

cur.execute(f"""
    SELECT id, name, latitude, longitude, country FROM churches 
    WHERE country IN ({ph}) 
    AND faith='Christian' AND LOWER(denomination) LIKE '%catholic%'
    AND latitude IS NOT NULL AND longitude IS NOT NULL
    AND (city IS NULL OR city = '')
    ORDER BY id
""", africa_list)
churches = cur.fetchall()
print(f'Churches needing city: {len(churches):,}')

updates, no_match = [], []
for row in tqdm(churches):
    cid, cname, lat, lon, country = row
    city_name, dist = nearest_city(lat, lon)
    if city_name:
        updates.append((city_name, cid))
    else:
        no_match.append((cid, country, lat, lon, dist))

print(f'\n  Assigned city: {len(updates):,}')
print(f'  No match: {len(no_match):,}')

if updates:
    print('\n=== Step 5: Writing to DB ===')
    for i in range(0, len(updates), 500):
        for city_name, cid in updates[i:i+500]:
            cur.execute("UPDATE churches SET city=? WHERE id=?", (city_name, cid))
        db.commit()
        print(f'  Written {min(i+500, len(updates))}/{len(updates)}')

print('\n=== Coverage by country ===')
cur.execute(f"""
    SELECT country, COUNT(*) AS total,
           SUM(CASE WHEN city IS NOT NULL AND city != '' THEN 1 ELSE 0 END) AS with_city
    FROM churches WHERE country IN ({ph})
    AND faith='Christian' AND LOWER(denomination) LIKE '%catholic%'
    GROUP BY country ORDER BY total DESC
""", africa_list)
total, wc = 0, 0
for r in cur.fetchall():
    total += r[1]; wc += r[2]
    print(f'  {r[0]}: {r[1]} churches, {r[2]} city ({r[2]/r[1]*100:.0f}%)')
print(f'\n  TOTAL: {total} churches, {wc} with city ({wc/total*100:.1f}%)')

if no_match:
    no_match.sort(key=lambda x: -x[4])
    print(f'\nFarthest no-match (n={len(no_match)}):')
    for cid, country, lat, lon, dist in no_match[:5]:
        print(f'  id={cid} in {country} at {lat:.4f},{lon:.4f} ({dist:.0f}km)')

db.close()
print('\nDone!')
