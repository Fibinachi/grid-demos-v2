"""
Parse 2020 Official Catholic Directory — extract parishes with addresses and phones.
Match to GRID and enrich.
"""
import sqlite3, re, json
from collections import Counter

# ── Parse 2020 directory ───────────────────────────────────────────
with open('E:/grid/data/directories/catholic_dir_2020_formatted.txt', encoding='utf-8', errors='replace') as f:
    text = f.read()

# Find parish entries: "Parish Name, Address, City, State ZIP. Tel: phone;"
# Pattern: Name starting with "St." or "Holy" or "Our Lady" or "Sacred Heart" etc.
# followed by street address, city, state (optional), ZIP, phone

# Catholic parish name patterns
parish_start = r'(?:St\.|Saint|Holy|Our Lady|Sacred Heart|Immaculate|Blessed|Christ the|Good Shepherd|Divine|Holy Family|Sts\.|SS\.|Most Holy|Precious Blood|Queen of|Our Mother|Mother of|Holy Cross|Holy Spirit|Holy Trinity|Holy Name|Holy Rosary|Our Lady of|St\.\s+\w+)'

# Full pattern: Parish Name, Address, City, [State] ZIP[. Tel: phone[; Fax: fax][; Email: email]]
entry_pattern = re.compile(
    r'(' + parish_start + r'[^.]*?),'  # parish name (ends at first comma)
    r'\s*(.+?),'                         # address
    r'\s*([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*),?'  # city
    r'\s*(?:([A-Z]{2})\s+)?'            # optional state
    r'(\d{5}(?:-\d{4})?)'               # ZIP
    r'(?:[.\s]+Tel:\s*([^;]+))?'        # optional phone
    r'(?:[;\s]+Fax:\s*([^;]+))?'        # optional fax
    r'(?:[;\s]+Email:\s*([^;\s.]+@[^;\s.]+))?'  # optional email
)

# Simpler approach: find lines with church names + addresses + zip
parishes = []
lines = text.split('\n')

# Pattern for "Name, Address, City, ST ZIP" or "Name, Address, City, ZIP"
addr_re = re.compile(
    r'^(.+?),'                          # name
    r'\s*(\d+.+?),'                      # address (starts with number)
    r'\s*([A-Z][a-zA-Z\s]+?),'           # city
    r'\s*(?:([A-Z]{2})\s+)?'             # optional state
    r'(\d{5}(?:-\d{4})?)'               # ZIP
    r'\s*(?:[.;]\s*Tel:\s*(.+?))?'       # optional phone
    r'\s*(?:[;\s]+(?:Fax|Email|Web|E-mail):\s*(.+?))?'  # optional contact
    r'\s*$'
)

# Also match entries without leading number in address: "St. Mary, Church St., Town, ST 12345"
name_only_re = re.compile(
    r'^((?:St\.|Saint|Holy|Our Lady|Sacred Heart|Immaculate|Blessed|Christ the|Good Shepherd|Divine|Holy Family|Sts\.|SS\.|Most Holy|Precious Blood|Queen of|Our Mother|Mother of|Holy Cross|Holy Spirit|Holy Trinity|Holy Name|Holy Rosary|Our Lady of|St\.)\s*.+?),'
    r'\s*(.+?,)\s*'                      # address
    r'([A-Z][a-zA-Z\s]+?),?\s*'          # city
    r'(?:([A-Z]{2})\s+)?'               # optional state
    r'(\d{5}(?:-\d{4})?)'               # ZIP
    r'\s*(?:[.;]\s*Tel:\s*(.+?))?'       # optional phone
)

print("Extracting parish entries from 2020 directory...")

# Try name_only pattern first
for i, line in enumerate(lines):
    line = line.strip()
    if not line or len(line) < 20:
        continue
    
    m = name_only_re.match(line)
    if not m:
        # Try addr_re
        m = addr_re.match(line)
    
    if m:
        groups = m.groups()
        name = groups[0].strip()
        if len(name) < 5 or len(name) > 80:
            continue
        # Filter out non-parish entries
        skip_words = ['diocese', 'archdiocese', 'chancery', 'office of', 'catholic schools',
                     'conference', 'seminary', 'cemetery', 'hospital', 'catholic charities']
        if any(w in name.lower() for w in skip_words):
            continue
        
        parishes.append({
            'name': name,
            'address': groups[1].strip() if len(groups) > 1 and groups[1] else '',
            'city': groups[2].strip() if len(groups) > 2 and groups[2] else '',
            'state': groups[3].strip() if len(groups) > 3 and groups[3] else '',
            'zip': groups[4] if len(groups) > 4 and groups[4] else '',
            'phone': groups[5].strip(' ;.') if len(groups) > 5 and groups[5] else '',
            'source_line': i,
        })

print(f"Extracted {len(parishes):,} parish entries")

# Show samples
for p in parishes[:10]:
    print(f"  {p['name'][:40]:40s} | {p['address'][:30]:30s} | {p['city'][:15]:15s} {p['state']} {p['zip']} | {p['phone'][:20]}")

# ── Match to GRID ──────────────────────────────────────────────────
ch = sqlite3.connect('E:/grid/churches.db')
ch.execute('PRAGMA busy_timeout=30000')

def norm(s):
    if not s: return ''
    return re.sub(r'[^\w\s]', '', s.lower().strip())
    return re.sub(r'\s+', ' ', s)

# Build index of US Catholic churches
grid_idx = {}
for row in ch.execute("""
    SELECT rowid, name, city, state, address, phone, taxonomy_id
    FROM churches WHERE country='US'
""").fetchall():
    key = (norm(row[1]), norm(row[2] or ''), (row[3] or '').upper())
    if key not in grid_idx:
        grid_idx[key] = (row[0], row[4], row[5], row[6])

print(f"Grid index: {len(grid_idx):,} US churches")

# Match and enrich
stats = Counter()
updates = []  # (rowid, phone)

for p in parishes:
    key = (norm(p['name']), norm(p['city']), p['state'].upper())
    result = grid_idx.get(key)
    
    if not result:
        stats['no_match'] += 1
        continue
    
    rowid, cur_addr, cur_phone, cur_tax = result
    stats['matched'] += 1
    
    # Enrich phone
    phone = p['phone']
    if phone and not cur_phone:
        updates.append((rowid, phone))
        stats['phone_added'] += 1

print(f"Matched: {stats['matched']:,} | no_match: {stats['no_match']:,}")
print(f"Phones to add: {stats['phone_added']:,}")

# ── Push phone updates ─────────────────────────────────────────────
if updates:
    ch.execute("CREATE TEMP TABLE IF NOT EXISTS _cd_phone (rowid INTEGER PRIMARY KEY, phone TEXT)")
    ch.execute("DELETE FROM _cd_phone")
    ch.executemany("INSERT OR REPLACE INTO _cd_phone VALUES (?,?)", updates)
    ch.execute("UPDATE churches SET phone=(SELECT phone FROM _cd_phone WHERE _cd_phone.rowid=churches.rowid) WHERE rowid IN (SELECT rowid FROM _cd_phone)")
    ch.commit()
    n = ch.execute("SELECT COUNT(*) FROM churches WHERE rowid IN (SELECT rowid FROM _cd_phone) AND phone IS NOT NULL").fetchone()[0]
    print(f"Phones updated: {n:,}")

# Save unmatched for review
unmatched = [p for p in parishes if (norm(p['name']), norm(p['city']), p['state'].upper()) not in grid_idx]
print(f"Unmatched parishes: {len(unmatched):,}")

with open('E:/grid/data/directories/catholic_2020_unmatched.json', 'w') as f:
    json.dump(unmatched[:500], f, indent=2)

# ── Provenance ────────────────────────────────────────────────────
ch.execute("INSERT INTO provenance_log (source,script_name,churches_updated,records_matched,fields_populated,notes,status) VALUES ('catholic_dir_2020','parse_catholic_dir.py',?,?,'phone','Parsed 2020 Official Catholic Directory','complete')", (len(updates), stats['matched']))
ch.commit()
ch.close()

# Save all parish data for future use
with open('E:/grid/data/directories/catholic_2020_parishes.json', 'w') as f:
    json.dump(parishes, f, indent=1)
print(f"Saved {len(parishes):,} parishes to catholic_2020_parishes.json")
print("Done.")
