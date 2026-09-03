"""Import all RCA churches from WP Store Locator API."""
import requests, re, sqlite3, time, json
from bs4 import BeautifulSoup

DB = r'E:\grid\churches.db'

def fetch_all_stores():
    """Fetch all wpsl_stores with pagination."""
    all_stores = []
    page = 1
    while True:
        r = requests.get('https://www.rca.org/wp-json/wp/v2/wpsl_stores',
                         params={'per_page': 100, 'page': page, '_fields': 'id,title,content,link,slug'}, 
                         timeout=15)
        if r.status_code != 200:
            break
        stores = r.json()
        if not stores:
            break
        all_stores.extend(stores)
        total = int(r.headers.get('X-WP-Total', 0))
        print(f'  Page {page}: {len(stores)} stores (total: {total}, fetched: {len(all_stores)})')
        if len(all_stores) >= total:
            break
        page += 1
        time.sleep(0.3)
    return all_stores

def parse_store(store):
    """Extract name, address, city, state, zip from store content."""
    title = store['title']['rendered'].strip()
    content = store['content']['rendered']
    soup = BeautifulSoup(content, 'html.parser')
    text = soup.get_text()
    
    # Parse address — usually: "Address\nCity, State ZIP"
    lines = [l.strip() for l in text.split('\n') if l.strip()]
    addr = city = state = zip_code = ''
    
    for line in lines:
        # Look for city, state zip pattern
        m = re.match(r'(.+),\s*([A-Z]{2})\s+(\d{5})', line)
        if m:
            city = m.group(1).strip()
            state = m.group(2)
            zip_code = m.group(3)
        elif re.match(r'\d+\s+\w+', line) and not addr:
            addr = line
    
    return {
        'name': title,
        'address': addr,
        'city': city,
        'state': state,
        'zip': zip_code,
    }

if __name__ == '__main__':
    print('=== RCA (Reformed Church in America) ===')
    stores = fetch_all_stores()
    print(f'\nFetched {len(stores)} stores')
    
    churches = [parse_store(s) for s in stores]
    valid = [c for c in churches if c['state']]
    print(f'Valid with state: {len(valid)}')
    
    # Import
    db = sqlite3.connect(DB)
    db.execute('PRAGMA busy_timeout=60000')
    c = db.cursor()
    
    mov = c.execute("SELECT id FROM movement WHERE name='Reformed Church in America'").fetchone()
    mov_id = mov[0] if mov else None
    ref_id = c.execute("SELECT id FROM tradition WHERE name='Reformed'").fetchone()[0]
    prot_id = c.execute("SELECT id FROM legacy WHERE name='Protestant'").fetchone()[0]
    max_ch = c.execute("SELECT MAX(id) FROM churches").fetchone()[0]
    nid = max_ch + 1
    imp = dup = 0
    
    for ch in valid:
        ex = c.execute("SELECT id FROM churches WHERE name=? AND city=? AND state=? AND faith='Christian'",
                       (ch['name'], ch['city'], ch['state'])).fetchone()
        if ex:
            if mov_id:
                c.execute("UPDATE churches SET movement_id=?, tradition_id=?, legacy_id=? WHERE id=? AND movement_id IS NULL",
                          (mov_id, ref_id, prot_id, ex[0]))
                if c.rowcount > 0: dup += 1
            continue
        
        c.execute("""INSERT INTO churches (id, name, city, state, country, address,
            faith, culture_id, legacy_id, tradition_id, movement_id, landmark_type, source)
            VALUES (?,?,?,?,'US',?,'Christian',555,?,?,?,'church','rca_api')""",
            (nid, ch['name'], ch['city'], ch['state'], ch['address'], prot_id, ref_id, mov_id))
        nid += 1; imp += 1
    
    db.commit()
    print(f'  New: {imp} | Updated: {dup}')
    db.close()
    print('DONE')
