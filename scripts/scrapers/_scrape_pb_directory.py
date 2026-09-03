"""
Scrape pbdirectory.org for all Primitive Baptist churches and import into churches.db.
"""
import requests, re, sqlite3, time, csv

DB = r'E:\grid\churches.db'
BASE = 'https://www.pbdirectory.org'
STATES = ['AL','AR','AZ','CA','CO','DE','FL','GA','IA','IL','IN','KS','KY',
          'LA','MD','MI','MO','MS','NC','NE','NM','NY','OH','OK','OR','PA',
          'SC','TN','TX','VA','WA','WI','WV']

def scrape_state(state):
    from bs4 import BeautifulSoup
    url = f'{BASE}/states/state.php?state={state}'
    try:
        resp = requests.get(url, timeout=30)
        resp.raise_for_status()
    except Exception as e:
        print(f'    ERROR: {e}')
        return []
    soup = BeautifulSoup(resp.text, 'html.parser')
    churches = []
    for p in soup.find_all('p'):
        strong = p.find('strong')
        if not strong or 'Address:' not in strong.text:
            continue
        addr_raw = p.get_text(strip=True).replace('Address:', '').strip()
        zip_match = re.search(r'(\d{5})', addr_raw)
        zip_code = zip_match.group(1) if zip_match else None
        addr_clean = re.sub(r'\s*\d{5}(?:-\d{4})?\s*', '', addr_raw)
        addr_clean = addr_clean.replace('\U0001f7e2', '').strip().rstrip(',').strip()
        name = None; city_state = None
        prev = p.find_previous_sibling(); count = 0
        while prev and count < 5:
            text = prev.get_text(strip=True)
            if text and len(text) > 3:
                if re.search(rf',\s*{state}', text):
                    city_state = text
                elif 'Address' not in text and not re.match(r'^\d+', text) and not name:
                    name = text
            prev = prev.find_previous_sibling(); count += 1
        if name and city_state:
            cm = re.match(r'^(.+),\s*[A-Z]{2}', city_state)
            churches.append({
                'name': name.strip(), 'city': (cm.group(1).strip() if cm else city_state),
                'state': state, 'address': addr_clean, 'zip': zip_code,
            })
    return churches

if __name__ == '__main__':
    all_churches = []
    for st in STATES:
        churches = scrape_state(st)
        all_churches.extend(churches)
        print(f'  {st}: {len(churches)}')
        if churches: time.sleep(0.3)
    
    print(f'\nTotal scraped: {len(all_churches)}')
    
    # Save CSV
    csv_path = r'E:\grid\data\denom\primitive_baptist_directory.csv'
    with open(csv_path, 'w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=['name','city','state','address','zip'])
        w.writeheader(); w.writerows(all_churches)
    print(f'Saved CSV: {csv_path}')
    
    # Import into DB (without geocoding for now — addresses are good enough)
    print('\nImporting into churches.db...')
    db = sqlite3.connect(DB)
    db.row_factory = sqlite3.Row
    db.execute('PRAGMA busy_timeout=60000')
    c = db.cursor()
    
    pb_mov = c.execute("SELECT id FROM movement WHERE name='Primitive Baptist'").fetchone()
    if pb_mov:
        pb_mov_id = pb_mov[0]
    else:
        max_id = c.execute("SELECT MAX(id) FROM movement").fetchone()[0]
        pb_mov_id = max_id + 1
        bt = c.execute("SELECT id FROM tradition WHERE name='Baptist'").fetchone()[0]
        c.execute("INSERT INTO movement (id, name, tradition_id) VALUES (?, 'Primitive Baptist', ?)", (pb_mov_id, bt))
    
    prot_id = c.execute("SELECT id FROM legacy WHERE name='Protestant'").fetchone()[0]
    bapt_id = c.execute("SELECT id FROM tradition WHERE name='Baptist'").fetchone()[0]
    
    max_ch = c.execute("SELECT MAX(id) FROM churches").fetchone()[0]
    new_id = max_ch + 1
    imported = 0; deduped = 0
    
    for ch in all_churches:
        ex = c.execute("SELECT id FROM churches WHERE name=? AND city=? AND state=? AND faith='Christian'",
                       (ch['name'], ch['city'], ch['state'])).fetchone()
        if ex:
            c.execute("UPDATE churches SET movement_id=?, tradition_id=?, legacy_id=? WHERE id=? AND movement_id IS NULL",
                      (pb_mov_id, bapt_id, prot_id, ex[0]))
            if c.rowcount > 0: deduped += 1
            continue
        
        c.execute("""INSERT INTO churches (id, name, city, state, country, faith, culture_id,
            legacy_id, tradition_id, movement_id, landmark_type, source, address)
            VALUES (?,?,?,?,'US','Christian',555,?,?,?,'church','pb_directory_import',?)""",
            (new_id, ch['name'], ch['city'], ch['state'], prot_id, bapt_id, pb_mov_id, ch['address']))
        new_id += 1; imported += 1
        if imported % 200 == 0:
            db.commit(); print(f'  {imported} imported...')
    
    db.commit()
    print(f'\n  New: {imported}  |  Updated existing: {deduped}')
    db.close()
    print('DONE')
