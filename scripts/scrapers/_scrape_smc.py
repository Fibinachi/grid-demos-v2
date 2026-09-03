"""Scrape all SMC conference pages for Southern Methodist churches."""
import requests, re, sqlite3
from bs4 import BeautifulSoup

DB = r'E:\grid\churches.db'
BASE = 'https://thesmc.org'

conferences = [
    'eastern-conference',
    'mid-south-conference', 
    'south-west-conference',
    'afg-conference',
    'carolinas-conference',
    'florida-conference',
]

def scrape_conference(slug):
    url = f'{BASE}/{slug}/'
    print(f'  {slug}...', end=' ', flush=True)
    try:
        r = requests.get(url, timeout=15)
        r.raise_for_status()
    except Exception as e:
        print(f'ERR: {e}')
        return []
    
    soup = BeautifulSoup(r.text, 'html.parser')
    churches = []
    
    for h3 in soup.find_all('h3'):
        if 'Churches' not in h3.text:
            continue
        state_part = h3.text.replace('Churches', '').strip()
        
        # Get all content after this h3 until next h3
        el = h3.find_next_sibling()
        while el and el.name != 'h3':
            text = el.get_text().strip()
            if text and len(text) > 15:
                # Parse: "Church Name\nAddress\nCity, State ZIP"
                lines = [l.strip() for l in text.split('\n') if l.strip()]
                if len(lines) >= 2 and not any(x in lines[0] for x in ['Officers', 'Coordinator', 'President', 'Director']):
                    name = lines[0]
                    addr = lines[1] if len(lines) > 1 else ''
                    city_state = lines[2] if len(lines) > 2 else ''
                    cs_match = re.match(r'(.+),\s*([A-Z]{2})\s*(\d{5})?', city_state)
                    if cs_match:
                        city = cs_match.group(1).strip()
                        state = cs_match.group(2)
                        zip_code = cs_match.group(3) or ''
                    else:
                        city = city_state
                        state = state_part if len(state_part) == 2 else ''
                        zip_code = ''
                    churches.append({
                        'name': name,
                        'address': addr,
                        'city': city,
                        'state': state or state_part,
                        'zip': zip_code,
                    })
            el = el.find_next_sibling()
    
    print(f'{len(churches)} churches')
    return churches

if __name__ == '__main__':
    all_churches = []
    for conf in conferences:
        churches = scrape_conference(conf)
        all_churches.extend(churches)
    
    print(f'\nTotal: {len(all_churches)} churches')
    
    if not all_churches:
        print('Nothing to import')
        exit()
    
    # Import
    db = sqlite3.connect(DB)
    db.execute('PRAGMA busy_timeout=60000')
    c = db.cursor()
    
    # SMC = Southern Methodist Church — a Methodist denomination
    # Check if movement exists
    smc = c.execute("SELECT id FROM movement WHERE name='Southern Methodist Church'").fetchone()
    if smc:
        mov_id = smc[0]
    else:
        mid = c.execute("SELECT MAX(id) FROM movement").fetchone()[0] + 1
        meth_id = c.execute("SELECT id FROM tradition WHERE name='Methodist'").fetchone()[0]
        c.execute("INSERT INTO movement (id, name, tradition_id) VALUES (?,?,?)", (mid, 'Southern Methodist Church', meth_id))
        db.commit()
        mov_id = mid
    
    prot_id = c.execute("SELECT id FROM legacy WHERE name='Protestant'").fetchone()[0]
    meth_id = c.execute("SELECT id FROM tradition WHERE name='Methodist'").fetchone()[0]
    
    max_ch = c.execute("SELECT MAX(id) FROM churches").fetchone()[0]
    new_id = max_ch + 1
    imported = deduped = 0
    
    for ch in all_churches:
        if not ch['name'] or not ch['state']:
            continue
        ex = c.execute("SELECT id FROM churches WHERE name=? AND city=? AND state=? AND faith='Christian'",
                       (ch['name'], ch['city'], ch['state'])).fetchone()
        if ex:
            c.execute("UPDATE churches SET movement_id=?, tradition_id=?, legacy_id=? WHERE id=? AND movement_id IS NULL",
                      (mov_id, meth_id, prot_id, ex[0]))
            if c.rowcount > 0: deduped += 1
            continue
        
        c.execute("""INSERT INTO churches (id, name, city, state, country, address,
            faith, culture_id, legacy_id, tradition_id, movement_id, landmark_type, source)
            VALUES (?,?,?,?,'US',?,'Christian',555,?,?,?,'church','smc_scrape')""",
            (new_id, ch['name'], ch['city'], ch['state'], ch['address'], prot_id, meth_id, mov_id))
        new_id += 1
        imported += 1
    
    db.commit()
    print(f'  New: {imported} | Updated: {deduped}')
    db.close()
    print('DONE')
