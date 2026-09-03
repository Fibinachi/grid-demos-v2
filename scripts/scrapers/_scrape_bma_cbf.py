"""
Import BMA (Baptist Missionary Association) and CBF (Cooperative Baptist Fellowship) churches.
BMA: scrape HTML table from bmaamerica.org/directory/
CBF: parse JSON from api.storepoint.co
"""
import requests, re, sqlite3, csv, json
from bs4 import BeautifulSoup

DB = r'E:\grid\churches.db'

def scrape_bma():
    """Scrape BMA directory HTML table."""
    print('=== BMA ===')
    resp = requests.get('https://bmaamerica.org/directory/', timeout=30)
    soup = BeautifulSoup(resp.text, 'html.parser')
    
    # Find the table with rows
    churches = []
    table = soup.find('table')
    if not table:
        # Try finding by role
        table = soup.find(attrs={'role': 'grid'})
    
    if not table:
        print('  No table found!')
        return []
    
    rows = table.find_all('tr')[1:]  # Skip header
    for row in rows:
        cells = row.find_all('td')
        if len(cells) < 7:
            continue
        churches.append({
            'name': cells[0].get_text(strip=True),
            'address': cells[1].get_text(strip=True),
            'city': cells[2].get_text(strip=True),
            'state': cells[3].get_text(strip=True),
            'zip': cells[4].get_text(strip=True),
            'phone': cells[5].get_text(strip=True),
            'pastor': cells[6].get_text(strip=True),
        })
    
    print(f'  Scraped {len(churches)} churches')
    return churches

def scrape_cbf():
    """Fetch CBF churches from API."""
    print('=== CBF ===')
    resp = requests.get('https://api.storepoint.co/v1/165c29a25766da/locations', 
                        params={'rq': ''}, timeout=30)
    data = resp.json()
    
    if not data.get('success'):
        print('  API error')
        return []
    
    locations = data['results']['locations']
    churches = []
    for loc in locations:
        # Parse address — split into street, city, state, zip
        addr = loc.get('address', '') or ''
        street = city = state = zip_code = ''
        
        # Common format: "123 Main St, City, ST 12345"
        parts = addr.split(',')
        if len(parts) >= 2:
            street = parts[0].strip()
            last = parts[-1].strip()
            # Last part: "ST 12345"
            zm = re.match(r'([A-Z]{2})\s+(\d{5})', last)
            if zm:
                state = zm.group(1)
                zip_code = zm.group(2)
            if len(parts) >= 3:
                city = parts[1].strip()
        
        churches.append({
            'name': (loc.get('name') or '').strip(),
            'address': street,
            'city': city,
            'state': state,
            'zip': zip_code,
            'phone': (loc.get('phone') or '').strip(),
            'lat': loc.get('loc_lat'),
            'lon': loc.get('loc_long'),
        })
    
    print(f'  Fetched {len(churches)} churches')
    return churches

def import_churches(churches, source, movement_name, tradition_name='Baptist'):
    """Import into churches.db with dedup."""
    db = sqlite3.connect(DB)
    db.row_factory = sqlite3.Row
    db.execute('PRAGMA busy_timeout=60000')
    c = db.cursor()
    
    # Get taxonomy IDs
    mov = c.execute("SELECT id FROM movement WHERE name=?", (movement_name,)).fetchone()
    if mov:
        mov_id = mov[0]
    else:
        max_id = c.execute("SELECT MAX(id) FROM movement").fetchone()[0]
        mov_id = max_id + 1
        trad = c.execute("SELECT id FROM tradition WHERE name=?", (tradition_name,)).fetchone()
        if not trad:
            trad = c.execute("SELECT id FROM tradition WHERE name='Baptist'").fetchone()
        c.execute("INSERT INTO movement (id, name, tradition_id) VALUES (?,?,?)",
                  (mov_id, movement_name, trad[0]))
        db.commit()
    
    prot_id = c.execute("SELECT id FROM legacy WHERE name='Protestant'").fetchone()[0]
    bapt_id = c.execute("SELECT id FROM tradition WHERE name='Baptist'").fetchone()[0]
    
    max_ch = c.execute("SELECT MAX(id) FROM churches").fetchone()[0]
    new_id = max_ch + 1
    imported = deduped = 0
    
    for ch in churches:
        if not ch['name'] or not ch['state']:
            continue
        
        ex = c.execute("""SELECT id FROM churches 
            WHERE name=? AND city=? AND state=? AND faith='Christian'""",
            (ch['name'], ch['city'], ch['state'])).fetchone()
        
        if ex:
            c.execute("""UPDATE churches SET movement_id=?, tradition_id=?, legacy_id=? 
                WHERE id=? AND movement_id IS NULL""",
                (mov_id, bapt_id, prot_id, ex[0]))
            if c.rowcount > 0:
                deduped += 1
            continue
        
        lat = ch.get('lat')
        lon = ch.get('lon')
        
        c.execute("""INSERT INTO churches (id, name, city, state, country, latitude, longitude,
            faith, culture_id, legacy_id, tradition_id, movement_id, landmark_type, source, address)
            VALUES (?,?,?,?,'US',?,?,'Christian',555,?,?,?,'church',?,?)""",
            (new_id, ch['name'], ch['city'], ch['state'], lat, lon,
             prot_id, bapt_id, mov_id, source, ch.get('address', '')))
        
        new_id += 1
        imported += 1
    
    db.commit()
    print(f'  New: {imported}  |  Updated existing: {deduped}')
    
    # Also save CSV
    csv_path = rf'E:\grid\data\denom\{source}.csv'
    with open(csv_path, 'w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=['name','city','state','address','zip','phone','lat','lon'])
        w.writeheader()
        for ch in churches:
            w.writerow({k: ch.get(k, '') for k in ['name','city','state','address','zip','phone','lat','lon']})
    print(f'  CSV: {csv_path}')
    
    db.close()
    return imported, deduped

if __name__ == '__main__':
    # BMA
    bma = scrape_bma()
    if bma:
        import_churches(bma, 'bma_directory', 'Baptist Missionary Association of America')
    
    print()
    
    # CBF
    cbf = scrape_cbf()
    if cbf:
        import_churches(cbf, 'cbf_api', 'Cooperative Baptist Fellowship')
    
    print('\nDONE')
