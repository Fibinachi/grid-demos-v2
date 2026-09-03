"""Import BMA and CBF churches from extracted data."""
import json, sqlite3, csv

DB = r'E:\grid\churches.db'

def load_bma():
    # Read the BMA JSON extracted from browser
    with open(r'E:\grid\data\denom\bma_extracted.json', 'r', encoding='utf-8') as f:
        return json.load(f)

def load_cbf():
    import requests
    resp = requests.get('https://api.storepoint.co/v1/165c29a25766da/locations', 
                        params={'rq': ''}, timeout=30)
    data = resp.json()
    churches = []
    for loc in data['results']['locations']:
        lat = loc.get('loc_lat')
        lng = loc.get('loc_long')
        if not lat or not lng:
            continue
        churches.append({
            'name': (loc.get('name') or '').strip(),
            'phone': (loc.get('phone') or '').strip(),
            'lat': lat,
            'lon': lng,
            'city': '', 'state': '', 'zip': '', 'address': '',
        })
    return churches

def import_churches(churches, source, movement_name):
    db = sqlite3.connect(DB)
    db.row_factory = sqlite3.Row
    db.execute('PRAGMA busy_timeout=60000')
    c = db.cursor()
    
    mov = c.execute("SELECT id FROM movement WHERE name=?", (movement_name,)).fetchone()
    if mov:
        mov_id = mov[0]
    else:
        max_id = c.execute("SELECT MAX(id) FROM movement").fetchone()[0]
        mov_id = max_id + 1
        trad = c.execute("SELECT id FROM tradition WHERE name='Baptist'").fetchone()
        c.execute("INSERT INTO movement (id, name, tradition_id) VALUES (?,?,?)",
                  (mov_id, movement_name, trad[0] if trad else None))
        db.commit()
    
    prot_id = c.execute("SELECT id FROM legacy WHERE name='Protestant'").fetchone()[0]
    bapt_id = c.execute("SELECT id FROM tradition WHERE name='Baptist'").fetchone()[0]
    
    max_ch = c.execute("SELECT MAX(id) FROM churches").fetchone()[0]
    new_id = max_ch + 1
    imported = deduped = 0
    
    for ch in churches:
        if not ch['name']:
            continue
        
        ex = c.execute("""SELECT id FROM churches 
            WHERE name=? AND (city=? OR (city='' AND ?='')) AND (state=? OR (state='' AND ?=''))
            AND faith='Christian'""",
            (ch['name'], ch.get('city',''), ch.get('city',''), 
             ch.get('state',''), ch.get('state',''))).fetchone()
        
        if ex:
            c.execute("""UPDATE churches SET movement_id=?, tradition_id=?, legacy_id=? 
                WHERE id=? AND movement_id IS NULL""",
                (mov_id, bapt_id, prot_id, ex[0]))
            if c.rowcount > 0:
                deduped += 1
            continue
        
        c.execute("""INSERT INTO churches (id, name, city, state, country, latitude, longitude,
            faith, culture_id, legacy_id, tradition_id, movement_id, landmark_type, source, address)
            VALUES (?,?,?,?,'US',?,?,'Christian',555,?,?,?,'church',?,?)""",
            (new_id, ch['name'], ch.get('city',''), ch.get('state',''),
             ch.get('lat'), ch.get('lon'),
             prot_id, bapt_id, mov_id, source, ch.get('address', '')))
        
        new_id += 1
        imported += 1
        if imported % 300 == 0:
            db.commit()
            print(f'  {imported} imported...')
    
    db.commit()
    print(f'  {source}: {imported} new, {deduped} updated existing')
    db.close()
    return imported, deduped

if __name__ == '__main__':
    # BMA
    print('=== BMA ===')
    bma = load_bma()
    print(f'  Loaded {len(bma)} churches')
    import_churches(bma, 'bma_directory', 'Baptist Missionary Association of America')
    
    # CBF
    print('\n=== CBF ===')
    cbf = load_cbf()
    print(f'  Loaded {len(cbf)} churches')
    import_churches(cbf, 'cbf_api', 'Cooperative Baptist Fellowship')
    
    print('\nDONE')
