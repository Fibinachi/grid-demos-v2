"""
Scrape Wikipedia's List of Catholic dioceses to build a global
diocese -> ecclesiastical province mapping.

Output: data/diocese_mapper/diocese_province_global.csv
"""
import re, csv, os, requests, html
from collections import defaultdict

def process_block(block, province, country, mappings):
    metro = None
    dioceses = []
    for line in block:
        line = line.strip()
        if not line:
            continue
        clean = re.sub(r"''+", '', line)
        clean = re.sub(r'\[\[([^\]|]+)\|([^\]]+)\]\]', r'\2', clean)
        clean = re.sub(r'\[\[([^\]]+)\]\]', r'\1', clean)
        clean = re.sub(r'\([^)]*\d{4}[^)]*\)', '', clean)
        clean = clean.strip(';:* ')

        if 'Metropolitan' in clean and ('Archdiocese' in clean or 'Archdiocese' in clean):
            name = clean.replace('Metropolitan ', '').strip()
            if name and not metro:
                metro = name
                continue
        if 'Patriarchate of' in clean and not metro:
            metro = clean
            continue

        suff = re.match(r'(?:Roman\s+)?(?:Diocese|Archdiocese|Eparchy|Archeparchy|Territorial\s+Prelature|Apostolic\s+Vicariate|Apostolic\s+Administration|Apostolic\s+Prefecture|Mission\s+Sui\s+Iuris|Territorial\s+Abbacy|Territorial\s+Abbey)\s+of\s+(.+)', clean)
        if suff:
            dioceses.append(suff.group(1).strip())

    if metro:
        mappings.append((metro, province, country or '', 'yes'))
    for d in dioceses:
        mappings.append((d, province, country or '', 'no'))


print("Fetching Wikipedia...")
headers = {'User-Agent': 'GRID-Project/1.0 (academic research)'}
r = requests.get('https://en.wikipedia.org/w/index.php',
    params={'title': 'List_of_Catholic_dioceses', 'action': 'raw'},
    headers=headers, timeout=30)
r.raise_for_status()
text = html.unescape(r.text)
print(f"  Got {len(text):,} chars")

lines = text.split('\n')
mappings = []
current_province = None
current_country = None
in_block = False
block = []

for line in lines:
    cm = re.match(r"^=+\s*(?:Episcopal|Ecclesiastical)\s+Conference\s+of\s+(.+?)\s*=+", line)
    if not cm:
        cm = re.match(r"^=+\s*Assembly\s+of\s+Catholic\s+Ordinaries\s+of\s+(.+?)\s*=+", line)
    if not cm:
        cm = re.match(r"^=+\s*Ecclesiastical\s+[Cc]onference\s+of\s+(.+?)\s*=+", line)
    if cm:
        current_country = re.sub(r'\s*\(.*?\)\s*', '', cm.group(1).strip()).strip()
        if 'United States of America' in current_country:
            current_country = 'United States'
        continue

    pm = re.match(r"^(?:'{2,3}|;)\s*Ecclesiastical\s+[Pp]rovince\s+of\s+(.+?)(?:'{2,3})?\s*(?:,|\.|$|<!--)", line)
    if pm:
        if block:
            process_block(block, current_province, current_country, mappings)
        current_province = pm.group(1).strip()
        current_province = re.sub(r"'{2,3}\s*$", '', current_province).strip()
        current_province = re.sub(r',\s*covering.*$', '', current_province).strip()
        block = []
        in_block = True
        continue

    if in_block:
        if line.startswith('=== ') or line.startswith('== '):
            process_block(block, current_province, current_country, mappings)
            in_block = False; block = []
            continue
        if re.match(r"^(?:'{2,3}|;)\s*(?:Ecclesiastical\s+[Pp]rovince|Exempt|Other|Eastern)", line):
            process_block(block, current_province, current_country, mappings)
            pm2 = re.match(r"^(?:'{2,3}|;)\s*Ecclesiastical\s+[Pp]rovince\s+of\s+(.+?)(?:'{2,3})?\s*(?:,|\.|$)", line)
            if pm2:
                current_province = re.sub(r"'{2,3}\s*$", '', pm2.group(1).strip()).strip()
            block = []
            continue
        block.append(line)

if block:
    process_block(block, current_province, current_country, mappings)

print(f"\nExtracted {len(mappings)} mappings")

seen = set()
unique = []
for d, p, c, m in mappings:
    key = (d.lower().strip(), p.lower().strip())
    if key not in seen:
        seen.add(key)
        unique.append((d.strip(), p.strip(), c, m))

print(f"  Unique: {len(unique)}")

by_country = defaultdict(set)
for d, p, c, m in unique:
    by_country[c or 'Unknown'].add(p)

print(f"\n  Countries: {len(by_country)}")
for country in sorted(by_country.keys()):
    n = len(by_country[country])
    print(f"    {country}: {n} province(s)")

out_path = 'data/diocese_mapper/diocese_province_global.csv'
os.makedirs(os.path.dirname(out_path), exist_ok=True)
with open(out_path, 'w', newline='', encoding='utf-8') as f:
    w = csv.writer(f)
    w.writerow(['Diocese', 'Province', 'Country', 'Is_Metropolitan'])
    w.writerows(unique)

print(f"\nSaved: {out_path}")
print(f"Total: {len(unique)} diocese->province mappings across {len(by_country)} countries")
