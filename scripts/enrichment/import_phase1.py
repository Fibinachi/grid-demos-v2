"""Import Phase 1 chunk 0 emails into SQLite."""
import csv, sqlite3, re

d = r'E:\grid'
results = list(csv.DictReader(open(d + '/scraped_chunk_0.csv', encoding='utf-8')))
print(f'Phase 1 chunk 0: {len(results)} rows')

conn = sqlite3.connect(d + '/churches.db')
cur = conn.cursor()

updated = 0
new_contacts = 0
with_email_count = 0

for r in results:
    church = (r.get('church_name','') or '').strip()
    email = (r.get('email','') or '').strip().lower()
    website = (r.get('website','') or '').strip()
    phone = (r.get('phone','') or '').strip()
    city_state = (r.get('city_state','') or '').strip()
    
    state = ''
    if ',' in city_state:
        state = city_state.split(',')[-1].strip().upper()[:2]
    
    if not church:
        continue
    
    if email:
        with_email_count += 1
    
    nname = re.sub(r'[^A-Z0-9 ]', ' ', church.upper()).strip()
    nname = re.sub(r'\s+', ' ', nname)
    
    existing = cur.execute('SELECT id, email FROM churches WHERE name = ? AND state = ?', (nname, state)).fetchone()
    
    if existing:
        if email and (not existing[1] or existing[1] == ''):
            cur.execute('UPDATE churches SET email = ?, phone = CASE WHEN ? != "" THEN ? ELSE phone END, has_website = 1, email_validated = CASE WHEN ? != "" THEN 1 ELSE email_validated END, last_updated = datetime("now") WHERE id = ?',
                       (email, phone, phone, email, existing[0]))
            updated += 1
    else:
        cur.execute('INSERT INTO churches (name, website, email, phone, state, source, has_website, email_validated) VALUES (?, ?, ?, ?, ?, "scraped", ?, ?)',
                   (nname, website, email, phone, state, 1 if website else 0, 1 if email else 0))
        new_contacts += 1

conn.commit()

cur.execute('SELECT COUNT(*) FROM churches WHERE email != ""')
total_email = cur.fetchone()[0]
conn.close()

print(f'Rows with email in CSV: {with_email_count}')
print(f'Updated existing records: {updated}')
print(f'New records inserted: {new_contacts}')
print(f'Total churches with email in DB: {total_email}')
