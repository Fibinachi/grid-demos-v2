"""Scrape all COG (Anderson) churches from SLP API."""
import requests, sqlite3, json, time
from concurrent.futures import ThreadPoolExecutor, as_completed

DB = r'E:\grid\churches.db'
BASE = 'https://www.jesusisthesubject.org/wp-json/store-locator-plus/v2'

# Get all IDs
print('Getting IDs...')
r = requests.get(f'{BASE}/locations', timeout=15)
ids = [item['sl_id'] for item in r.json()]
print(f'  {len(ids)} churches to fetch')

# Fetch in parallel
def fetch_one(sid):
    for attempt in range(3):
        try:
            r = requests.get(f'{BASE}/locations/{sid}', timeout=30)
            if r.status_code == 201:
                data = r.json()
                if data.get('sl_store'):
                    return data
            return None
        except:
            if attempt < 2:
                time.sleep(0.5)
    return None

churches = []
print(f'Fetching with 5 workers...')
with ThreadPoolExecutor(max_workers=5) as ex:
    futures = {ex.submit(fetch_one, sid): sid for sid in ids}
    for i, f in enumerate(as_completed(futures)):
        data = f.result()
        if data and data.get('sl_store'):
            churches.append({
                'name': data['sl_store'].strip(),
                'address': data.get('sl_address', '').strip(),
                'city': data.get('sl_city', '').strip(),
                'state': data.get('sl_state', '').strip(),
                'zip': data.get('sl_zip', '').strip(),
                'phone': data.get('sl_phone', '').strip(),
                'lat': data.get('sl_latitude'),
                'lng': data.get('sl_longitude'),
                'url': data.get('sl_url', '').strip(),
            })
        if (i+1) % 500 == 0:
            print(f'  {i+1}/{len(ids)}...')

print(f'  Fetched {len(churches)} valid churches')

# Import
db = sqlite3.connect(DB)
db.execute('PRAGMA busy_timeout=60000')
c = db.cursor()

mov = c.execute("SELECT id FROM movement WHERE name='Church of God (Anderson)'").fetchone()
if not mov:
    mid = c.execute("SELECT MAX(id) FROM movement").fetchone()[0] + 1
    hog_id = c.execute("SELECT id FROM tradition WHERE name='Holiness'").fetchone()[0]
    c.execute("INSERT INTO movement (id, name, tradition_id) VALUES (?,?,?)", (mid, 'Church of God (Anderson)', hog_id))
    db.commit(); mov_id = mid
else: mov_id = mov[0]

prot_id = c.execute("SELECT id FROM legacy WHERE name='Protestant'").fetchone()[0]
hog_id = c.execute("SELECT id FROM tradition WHERE name='Holiness'").fetchone()[0]
nid = c.execute('SELECT MAX(id) FROM churches').fetchone()[0] + 1
imp = dup = 0

for ch in churches:
    if not ch['state']: continue
    ex = c.execute("SELECT id FROM churches WHERE name=? AND city=? AND state=? AND faith='Christian'",
                   (ch['name'], ch['city'], ch['state'])).fetchone()
    if ex:
        c.execute("UPDATE churches SET movement_id=?, tradition_id=?, legacy_id=? WHERE id=? AND movement_id IS NULL",
                  (mov_id, hog_id, prot_id, ex[0]))
        if c.rowcount > 0: dup += 1; continue
    
    c.execute("""INSERT INTO churches (id, name, city, state, country, address, latitude, longitude,
        faith, culture_id, legacy_id, tradition_id, movement_id, landmark_type, source)
        VALUES (?,?,?,?,'US',?,?,?,'Christian',555,?,?,?,'church','cog_anderson_api')""",
        (nid, ch['name'], ch['city'], ch['state'], ch['address'], ch['lat'], ch['lng'],
         prot_id, hog_id, mov_id))
    nid += 1; imp += 1

db.commit()
print(f'  New: {imp} | Updated: {dup}')
db.close()
print('DONE')
