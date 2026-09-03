"""Import EFCA churches from API."""
import requests, sqlite3, json

r = requests.get('https://data.efca.org/api/v1/churches',
    params={'bounds[n]':'49','bounds[s]':'24','bounds[e]':'-66','bounds[w]':'-125'},
    timeout=15)
data = r.json()['data']
print(f'{len(data)} churches')

db = sqlite3.connect(r'E:\grid\churches.db')
db.execute('PRAGMA busy_timeout=60000')
c = db.cursor()

mov = c.execute("SELECT id FROM movement WHERE name='Evangelical Free Church of America'").fetchone()
if not mov:
    mid = c.execute("SELECT MAX(id) FROM movement").fetchone()[0] + 1
    ev_id = c.execute("SELECT id FROM tradition WHERE name='Evangelical'").fetchone()[0]
    c.execute("INSERT INTO movement (id, name, tradition_id) VALUES (?,?,?)", (mid, 'Evangelical Free Church of America', ev_id))
    db.commit(); mov_id = mid
else: mov_id = mov[0]

prot_id = c.execute("SELECT id FROM legacy WHERE name='Protestant'").fetchone()[0]
ev_id = c.execute("SELECT id FROM tradition WHERE name='Evangelical'").fetchone()[0]
nid = c.execute('SELECT MAX(id) FROM churches').fetchone()[0] + 1
imp = dup = 0

for ch in data:
    addr = ch.get('address', {}) or {}
    state = addr.get('stateCode', '')
    city = addr.get('city', '')
    if not state: continue
    
    ex = c.execute("SELECT id FROM churches WHERE name=? AND city=? AND state=? AND faith='Christian'",
                   (ch['name'], city, state)).fetchone()
    if ex:
        c.execute("UPDATE churches SET movement_id=?, tradition_id=?, legacy_id=? WHERE id=? AND movement_id IS NULL",
                  (mov_id, ev_id, prot_id, ex[0]))
        if c.rowcount > 0: dup += 1; continue
    
    c.execute("""INSERT INTO churches (id, name, city, state, country, address,
        faith, culture_id, legacy_id, tradition_id, movement_id, landmark_type, source)
        VALUES (?,?,?,?,'US',?,'Christian',555,?,?,?,'church','efca_api')""",
        (nid, ch['name'], city, state, addr.get('street',''), prot_id, ev_id, mov_id))
    nid += 1; imp += 1

db.commit()
print(f'  New: {imp} | Updated: {dup}')
db.close()
