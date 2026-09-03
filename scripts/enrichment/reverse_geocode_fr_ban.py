"""
Reverse-geocode French churches using api-adresse.data.gouv.fr (BAN).
Free government API, 2 req/sec, full street addresses.

Fills: address (street), city, postcode for FR churches missing addresses.
"""
import sqlite3, requests, time
from datetime import datetime, timezone
from pathlib import Path
from tqdm import tqdm

DB = Path('E:/grid/churches.db')
BAN_URL = 'https://api-adresse.data.gouv.fr/reverse/'
HEADERS = {'User-Agent': 'GRID/1.0 (research)'}
CHUNK = 200
RATE = 0.5  # 2/sec max
NOW = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')

db = sqlite3.connect(DB)
db.execute("PRAGMA journal_mode=WAL")

# Fetch FR churches needing addresses
rows = db.execute("""
    SELECT id, latitude, longitude, name FROM churches 
    WHERE country='FR' AND (address IS NULL OR address='') 
    AND latitude IS NOT NULL ORDER BY id
""").fetchall()
db.close()

total = len(rows)
print(f"FR missing address: {total:,}")
print(f"Rate: {1/RATE:.0f}/sec | ETA: ~{total * RATE / 3600:.1f}h")
print()

batch = []
filled = 0
no_result = 0
errors = 0
start = time.time()

for i, (chid, lat, lon, name) in enumerate(tqdm(rows, desc="FR geocoding", unit='rec')):
    try:
        r = requests.get(BAN_URL, params={'lat': lat, 'lon': lon, 'limit': 1}, 
                        headers=HEADERS, timeout=10)
        if r.ok:
            feats = r.json().get('features', [])
            if feats:
                props = feats[0]['properties']
                street = props.get('name', '')
                city = props.get('city', '')
                postcode = props.get('postcode', '')
                
                tqdm.write(f"  [#{chid}] ({lat:.4f},{lon:.4f}) '{name[:45] if name else 'N/A'}' "
                          f"-> {street[:40]} | {city} | {postcode}")
                
                batch.append((street, city, postcode, chid))
                filled += 1
            else:
                no_result += 1
        else:
            errors += 1
    except Exception as e:
        errors += 1
    
    if len(batch) >= CHUNK:
        wdb = sqlite3.connect(DB)
        wdb.execute("PRAGMA journal_mode=WAL")
        for street, city, postcode, chid in batch:
            wdb.execute("""UPDATE churches SET 
                address=CASE WHEN address IS NULL OR address='' THEN ? ELSE address END,
                city=CASE WHEN city IS NULL OR city='' THEN ? ELSE city END,
                zip=CASE WHEN zip IS NULL OR zip='' THEN ? ELSE zip END
                WHERE id=?""", (street, city, postcode, chid))
        wdb.commit()
        wdb.close()
        batch = []
    
    time.sleep(RATE)

# Final flush
if batch:
    wdb = sqlite3.connect(DB)
    wdb.execute("PRAGMA journal_mode=WAL")
    for street, city, postcode, chid in batch:
        wdb.execute("""UPDATE churches SET 
            address=CASE WHEN address IS NULL OR address='' THEN ? ELSE address END,
            city=CASE WHEN city IS NULL OR city='' THEN ? ELSE city END,
            zip=CASE WHEN zip IS NULL OR zip='' THEN ? ELSE zip END
            WHERE id=?""", (street, city, postcode, chid))
    wdb.commit()
    wdb.close()

elapsed = time.time() - start

# Verify
db = sqlite3.connect(DB)
remaining = db.execute("SELECT COUNT(*) FROM churches WHERE country='FR' AND (address IS NULL OR address='') AND latitude IS NOT NULL").fetchone()[0]
db.execute("""INSERT INTO provenance_log (source, script_name, started_at, completed_at, status, notes)
    VALUES ('ban_france','reverse_geocode_fr_ban.py',?,datetime('now'),'completed',
    'FR BAN: '||?||' filled, '||?||' no-result, '||?||' errors, '||?||' remaining in '||?||'s')""",
    (NOW, filled, no_result, errors, remaining, f"{elapsed:.0f}"))
db.commit()
db.close()

print(f"\nDone in {elapsed/60:.0f}m — {filled:,} filled, {no_result:,} no-result, {errors:,} errors, {remaining:,} remaining")
