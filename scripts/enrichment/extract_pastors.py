"""Extract pastor names from IRS ICO field."""
import csv, re, sqlite3

d = r'E:\grid'
irs = list(csv.DictReader(open(d + '/irs_churches.csv', encoding='utf-8-sig')))

title_pattern = re.compile(r'(pastor|rev|reverend|bishop|father|minister|dr\.?)', re.I)
name_pattern = re.compile(r'%?\s*([A-Z][A-Za-z.\s]+)$')

pastors = []
person_names = []

for r in irs:
    ico = (r.get('ICO','') or '').strip()
    if not ico:
        continue
    cleaned = ico.lstrip('%').strip()
    
    if title_pattern.search(cleaned):
        pastors.append({
            'church_name': r.get('NAME',''),
            'pastor_ico': cleaned,
            'ein': r.get('EIN',''),
            'street': r.get('STREET',''),
            'city': r.get('CITY',''),
            'state': r.get('STATE',''),
            'zip': r.get('ZIP',''),
        })

print('Pastor names with titles found:', len(pastors))
print()
print('Sample:')
for p in pastors[:10]:
    label = p['pastor_ico'][:45]
    church = p['church_name'][:40]
    loc = p['city'] + ', ' + p['state']
    print(f'  {label} | {church} | {loc}')

# Save CSV
out = d + '/irs_pastors.csv'
with open(out, 'w', newline='', encoding='utf-8') as f:
    w = csv.DictWriter(f, fieldnames=['church_name','pastor_ico','ein','street','city','state','zip'])
    w.writeheader()
    w.writerows(pastors)
print(f'\nSaved to: {out}')

# Update SQLite
conn = sqlite3.connect(d + '/churches.db')
cur = conn.cursor()
updated = 0
for p in pastors:
    cur.execute('''
        UPDATE churches SET pastor_name = ? WHERE ein = ? AND (pastor_name = '' OR pastor_name IS NULL)
    ''', (p['pastor_ico'], p['ein']))
    if cur.rowcount:
        updated += 1
conn.commit()
print(f'Updated SQLite: {updated} pastor_names added')

# Also update the target_group for pastor-known churches
cur.execute('SELECT COUNT(*) FROM churches WHERE pastor_name != ""')
known = cur.fetchone()[0]
print(f'Total churches with known pastor: {known}')

conn.close()
