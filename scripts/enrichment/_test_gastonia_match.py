"""Test full pipeline: parse Gastonia 1976, match against GRID."""
import sqlite3, re
from difflib import SequenceMatcher

text = open('E:/grid/data/directories/sample_gastonia_1976.txt', encoding='utf-8', errors='ignore').read()
m = re.search(r'CHURCHES\s+AND\s+SYNAGOGUES', text, re.IGNORECASE)
section = text[m.start():m.start()+60000]

# Block-based parse
blocks = []
cur = []
church_kw = re.compile(
    r'church|chapel|temple|synagogue|mosque|tabernacle|ministry|fellowship|'
    r'worship|assembly|congregation|cathedral|parish|baptist|methodist|'
    r'presbyterian|lutheran|episcopal|catholic|pentecostal|holiness|nazarene|'
    r'adventist|apostolic|gospel|first|calvary|bethel|bethlehem|zion|redeemer|'
    r'savior|christian', re.IGNORECASE)

for line in section.split('\n'):
    s = line.strip()
    if not s:
        if cur: blocks.append(' '.join(cur)); cur = []
        continue
    if re.match(r'^CHURCHES?\s+(AND\s+)?(SYNAGOGUES|CONTD|CIVIC)', s, re.IGNORECASE):
        continue
    if re.match(r'^\d{1,4}$', s):
        continue
    cur.append(s)
if cur:
    blocks.append(' '.join(cur))

churches = []
addr_pat = re.compile(
    r'(.*?)(\d+\s+(?:[NSEW]\s+)?[A-Z][a-z]+(?:\s+(?:St|Av|Ave|Rd|Dr|Blvd|Ln|Way|'
    r'Cir|Ct|Pl|Hwy|Pkwy|Trl|Ter|Run|Row|Al|Aly|Cres|Plz|Xing|Cv|Bnd|La))\.?)')

for b in blocks:
    if len(b) < 10 or not church_kw.search(b):
        continue
    if re.search(r'DRUG|WRECKER|AUTO REPAIR|BORING|PUMP|INSURANCE|PLUMBING|ELECTRIC|'
                 r'HEATING|CONTRACTOR|CONSTRUCTION|EXCAVAT|PAVING|ROOFING|PAINTING|'
                 r'FUNERAL HOME|CEMETERY|MONUMENT|MARKET|GROCERY|PHARMACY|'
                 r'LAUNDRY|DRY CLEAN|PRINTING|PUBLISHING|REAL ESTATE|'
                 r'ATTORNEY|LAWYER|ACCOUNTANT|DENTIST|PHYSICIAN|SURGEON|CLINIC', b):
        continue
    
    m = addr_pat.search(b)
    if m:
        name = m.group(1).strip().rstrip(',').rstrip('.')
        addr = m.group(2).strip()
        rest = b[m.end():].strip()
        if rest:
            addr += ' ' + rest
        addr = re.sub(r'\s+', ' ', addr).strip()
        addr = re.sub(r'\s*\([A-Z0-9\s,]+\)\s*', ' ', addr).strip()
    else:
        name = b
        addr = ''
    
    name = re.sub(r'\s+', ' ', name).strip()
    churches.append({'name': name, 'addr': addr})

print(f'{len(churches)} churches extracted\n')

# Match against GRID for Gastonia, NC
db = sqlite3.connect('e:/grid/churches.db')
matched = 0
for ch in churches:
    norm = re.sub(r'\bSt\.?\s', 'Saint ', ch['name'])
    norm = re.sub(r'^The\s+', '', norm)
    found = False
    for row in db.execute('SELECT id,name FROM churches WHERE city=? LIMIT 200', ('Gastonia',)):
        db_norm = re.sub(r'\bSt\.?\s', 'Saint ', row[1])
        db_norm = re.sub(r'^The\s+', '', db_norm)
        score = SequenceMatcher(None, norm.lower(), db_norm.lower()).ratio()
        if score >= 0.70:
            matched += 1
            marker = 'OK' if score >= 0.85 else ('~' if score >= 0.75 else '?')
            print(f'{marker} {ch["name"][:55]:55s} | {row[1][:50]:50s} | {score:.2f}')
            found = True
            break
    if not found:
        print(f'XX {ch["name"][:55]:55s} | {"NOT IN GRID":50s} | 0.00')

print(f'\n{matched}/{len(churches)} matched ({matched/len(churches)*100:.0f}%)')
db.close()
