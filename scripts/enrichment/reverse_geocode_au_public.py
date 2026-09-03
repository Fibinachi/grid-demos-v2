"""Reverse-geocode Australian churches using public Nominatim API at 1/sec.
Per-record live output. Runs standalone — let it chug."""
import sqlite3, requests, time, sys, os
from datetime import datetime, timezone

DB = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), 'churches.db')
NOMINATIM_URL = 'https://nominatim.openstreetmap.org/reverse'
HEADERS = {'User-Agent': 'GRID-Project/1.0 (charlesaprescottjr@gmail.com)'}
CHUNK_SIZE = 50
RATE_LIMIT = 1.2  # seconds between requests

def build_street(addr):
    parts = []
    hn = addr.get('house_number', '')
    road = addr.get('road', '') or addr.get('pedestrian', '') or addr.get('footway', '') or addr.get('path', '')
    if hn and road:
        parts.append(f'{hn} {road}')
    elif road:
        parts.append(road)
    return ', '.join(parts) if parts else ''

def extract_city(addr):
    """Extract and validate city name from Nominatim address dict.
    Returns '' if the value looks scrambled (coordinates, HTML, too long, etc.)."""
    import html, re
    raw = (addr.get('city') or addr.get('town') or addr.get('village') or
           addr.get('hamlet') or addr.get('suburb') or addr.get('municipality') or '')
    if not raw:
        return ''
    if re.search(r'&#\d+;|&#x[0-9a-f]+;|&lt;|&gt;|&amp;|&quot;', raw):
        return ''
    try:
        raw = html.unescape(raw)
    except Exception:
        pass
    raw = raw.strip()
    if not raw:
        return ''
    if re.search(r'[\u00b0\u2032\u2033]', raw):
        return ''
    if re.search(r'\d+\.\d+[\u00b0]', raw):
        return ''
    if len(raw) > 80:
        return ''
    if raw.count(',') >= 3:
        return ''
    if re.search(r'\b(is one|is a|located in|directly subject|under the)\b', raw, re.IGNORECASE):
        return ''
    return raw

db = sqlite3.connect(DB)
db.execute("PRAGMA journal_mode=WAL")
c = db.cursor()

c.execute("""SELECT c.id, c.latitude, c.longitude, c.name, c.city 
    FROM churches c WHERE c.country='AU' AND (c.address IS NULL OR c.address='') 
    AND c.latitude IS NOT NULL ORDER BY c.id""")
rows = c.fetchall()
total = len(rows)
print(f"AU missing address: {total:,}")
print(f"Rate: 1 per {RATE_LIMIT}s | ETA: {total * RATE_LIMIT / 3600:.1f} hours")
print()

batch = []
updated = 0
filled = 0
filled_city = 0
skipped = 0
no_street = 0
start = time.time()

for i, (chid, lat, lon, name, city) in enumerate(rows):
    try:
        resp = requests.get(NOMINATIM_URL, 
            params={'lat': lat, 'lon': lon, 'format': 'json', 'addressdetails': 1, 'accept-language': 'en'},
            headers=HEADERS, timeout=15)
        if resp.status_code == 200:
            data = resp.json()
            addr = data.get('address', {})
            street = build_street(addr)
            postcode = addr.get('postcode', '')
            state = addr.get('state', '')
            nom_city = extract_city(addr)
            if street:
                batch.append((street, postcode, state, nom_city, chid))
                filled += 1
                if nom_city:
                    filled_city += 1
                print(f"  [#{chid}] ({lat:.4f},{lon:.4f}) '{name[:50] if name else 'N/A'}' -> {nom_city or 'no_city'}, {state} | {street[:50]}")
            else:
                no_street += 1
                print(f"  [#{chid}] ({lat:.4f},{lon:.4f}) '{name[:50] if name else 'N/A'}' -> [no_street] {nom_city or 'no_city'}, {state}")
                # Still update city/state even without street
                if nom_city:
                    batch.append((None, postcode, state, nom_city, chid))
        elif resp.status_code == 429:
            print(f"  [#{chid}] RATE LIMITED (429) — pausing 30s...")
            time.sleep(30)
            skipped += 1
        else:
            print(f"  [#{chid}] HTTP {resp.status_code}")
            skipped += 1
    except requests.exceptions.ReadTimeout:
        print(f"  [#{chid}] TIMEOUT (15s) — skipping")
        skipped += 1
    except Exception as e:
        print(f"  [#{chid}] ERROR: {type(e).__name__}: {e}")
        skipped += 1
    
    if len(batch) >= CHUNK_SIZE:
        for b in batch:
            street_val, postcode_val, state_val, city_val, chid_val = b
            if street_val is not None:
                c.execute(
                    """UPDATE churches SET address=?, zip=?, 
                       state=CASE WHEN state IS NULL OR state='' THEN ? ELSE state END,
                       city=CASE WHEN city IS NULL OR city='' THEN ? ELSE city END
                       WHERE id=?""",
                    (street_val, postcode_val, state_val, city_val, chid_val))
            else:
                c.execute(
                    """UPDATE churches SET zip=?,
                       state=CASE WHEN state IS NULL OR state='' THEN ? ELSE state END,
                       city=CASE WHEN city IS NULL OR city='' THEN ? ELSE city END
                       WHERE id=?""",
                    (postcode_val, state_val, city_val, chid_val))
        db.commit()
        updated += len(batch)
        batch = []
    
    if (i + 1) % 50 == 0:
        elapsed = time.time() - start
        rate = (i + 1) / elapsed
        eta = (total - i - 1) / rate / 60
        pct = (i + 1) / total * 100
        print(f"  --- {i+1:,}/{total:,} ({pct:.1f}%) | filled: {filled:,} | city: {filled_city:,} | no_street: {no_street:,} | skipped: {skipped:,} | {rate:.1f}/s | ETA {eta:.0f}m ---")
    
    time.sleep(RATE_LIMIT)

# Final flush
if batch:
    for b in batch:
        street_val, postcode_val, state_val, city_val, chid_val = b
        if street_val is not None:
            c.execute(
                """UPDATE churches SET address=?, zip=?,
                   state=CASE WHEN state IS NULL OR state='' THEN ? ELSE state END,
                   city=CASE WHEN city IS NULL OR city='' THEN ? ELSE city END
                   WHERE id=?""",
                (street_val, postcode_val, state_val, city_val, chid_val))
        else:
            c.execute(
                """UPDATE churches SET zip=?,
                   state=CASE WHEN state IS NULL OR state='' THEN ? ELSE state END,
                   city=CASE WHEN city IS NULL OR city='' THEN ? ELSE city END
                   WHERE id=?""",
                (postcode_val, state_val, city_val, chid_val))
    db.commit()
    updated += len(batch)

elapsed = time.time() - start
print(f"\nDone: {updated:,} updated, {filled:,} address filled, {filled_city:,} city filled, {no_street:,} no-street, {skipped:,} skipped in {elapsed/60:.0f}m")
db.close()
