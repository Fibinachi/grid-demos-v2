"""Scrape RCA church addresses from individual pages."""
import requests, re, sqlite3, json, time
from concurrent.futures import ThreadPoolExecutor, as_completed

DB = r'E:\grid\churches.db'

# Get all RCA slugs
print('Getting RCA slugs...')
all_slugs = []
page = 1
while True:
    r = requests.get('https://www.rca.org/wp-json/wp/v2/wpsl_stores',
                     params={'per_page': 100, 'page': page, '_fields': 'slug,title'},
                     timeout=15)
    stores = r.json()
    if not stores: break
    all_slugs.extend([(s['slug'], s['title']['rendered']) for s in stores])
    if len(all_slugs) >= int(r.headers.get('X-WP-Total', 0)): break
    page += 1
    time.sleep(0.2)

print(f'  {len(all_slugs)} churches')

# Scrape individual pages for address/city/state
def scrape_church(slug, title):
    try:
        r = requests.get(f'https://www.rca.org/churches/{slug}/', timeout=15)
        text = r.text
        # Look for address pattern: street address, city, state zip
        # Common patterns in RCA pages
        addr_match = re.search(r'(\d+\s+[^,]+),\s*([^,]+),\s*([A-Z]{2})\s+(\d{5})', text)
        if addr_match:
            return {
                'name': title,
                'address': addr_match.group(1).strip(),
                'city': addr_match.group(2).strip(),
                'state': addr_match.group(3),
                'zip': addr_match.group(4),
            }
        # Try JSON-LD
        ld_match = re.search(r'application/ld\+json[^>]*>({.+?})</script', text, re.DOTALL)
        if ld_match:
            ld = json.loads(ld_match.group(1))
            if isinstance(ld, dict) and '@graph' in ld:
                for item in ld['@graph']:
                    if item.get('@type') == 'LocalBusiness' or item.get('@type') == 'Place':
                        addr = item.get('address', {})
                        if addr:
                            return {
                                'name': title,
                                'address': addr.get('streetAddress', ''),
                                'city': addr.get('addressLocality', ''),
                                'state': addr.get('addressRegion', ''),
                                'zip': addr.get('postalCode', ''),
                            }
        return None
    except:
        return None

churches = []
print(f'Scraping with 5 workers...')
with ThreadPoolExecutor(max_workers=5) as ex:
    futures = {ex.submit(scrape_church, slug, title): slug for slug, title in all_slugs}
    for i, f in enumerate(as_completed(futures)):
        data = f.result()
        if data and data['state']:
            churches.append(data)
        if (i+1) % 200 == 0:
            print(f'  {i+1}/{len(all_slugs)} — found {len(churches)} so far')

print(f'  Found addresses for {len(churches)}/{len(all_slugs)}')

# Import
if churches:
    db = sqlite3.connect(DB)
    db.execute('PRAGMA busy_timeout=60000')
    c = db.cursor()
    
    mov = c.execute("SELECT id FROM movement WHERE name='Reformed Church in America'").fetchone()
    mov_id = mov[0] if mov else None
    ref_id = c.execute("SELECT id FROM tradition WHERE name='Reformed'").fetchone()[0]
    prot_id = c.execute("SELECT id FROM legacy WHERE name='Protestant'").fetchone()[0]
    nid = c.execute('SELECT MAX(id) FROM churches').fetchone()[0] + 1
    imp = dup = 0
    
    for ch in churches:
        ex = c.execute("SELECT id FROM churches WHERE name=? AND city=? AND state=? AND faith='Christian'",
                       (ch['name'], ch['city'], ch['state'])).fetchone()
        if ex:
            c.execute("UPDATE churches SET movement_id=?, tradition_id=?, legacy_id=? WHERE id=? AND movement_id IS NULL",
                      (mov_id, ref_id, prot_id, ex[0]))
            if c.rowcount > 0: dup += 1; continue
        
        c.execute("""INSERT INTO churches (id, name, city, state, country, address,
            faith, culture_id, legacy_id, tradition_id, movement_id, landmark_type, source)
            VALUES (?,?,?,?,'US',?,'Christian',555,?,?,?,'church','rca_scrape')""",
            (nid, ch['name'], ch['city'], ch['state'], ch['address'], prot_id, ref_id, mov_id))
        nid += 1; imp += 1
    
    db.commit()
    print(f'  New: {imp} | Updated: {dup}')
    db.close()

print('DONE')
