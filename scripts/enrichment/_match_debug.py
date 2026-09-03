"""Isolated match test with granular timing."""
import sqlite3, time, sys, re
from difflib import SequenceMatcher

sys.path.insert(0, 'e:/grid/scripts/enrichment')
from ia_city_directory_scraper import parse_church_entries, extract_churches_section, download_ocr, normalize_name

# Load entries
print('Loading OCR...', flush=True)
text = download_ocr('gloucesteressexc1960unse')
section = extract_churches_section(text)
entries = parse_church_entries(section)
print(f'{len(entries)} entries', flush=True)

# Open DB
db = sqlite3.connect('e:/grid/churches.db')
db.execute('PRAGMA journal_mode=WAL')

# Preload city
print('Preloading city...', flush=True)
t0 = time.time()
city_churches = list(db.execute("SELECT id, name FROM churches WHERE city='Gloucester'"))
print(f'  {len(city_churches)} rows in {time.time()-t0:.2f}s', flush=True)

# Match first entry
entry = entries[0]
norm = normalize_name(entry['name'])
print(f'\nEntry: {entry["name"]}', flush=True)
print(f'Norm:  {norm}', flush=True)

# Try exact match
t0 = time.time()
for cid, cname in city_churches:
    if cname == entry['name']:
        print(f'  Exact match: {cname}', flush=True)
        break
else:
    print(f'  No exact match', flush=True)
print(f'  Exact scan: {time.time()-t0:.2f}s', flush=True)

# Try fuzzy
t0 = time.time()
best_score, best_id, best_name = 0, None, None
for cid, cname in city_churches:
    score = SequenceMatcher(None, norm.lower(), normalize_name(cname).lower()).ratio()
    if score > best_score and score >= 0.75:
        best_score, best_id, best_name = score, cid, cname
print(f'  Best fuzzy: {best_name} ({best_score:.2f})', flush=True)
print(f'  Fuzzy scan: {time.time()-t0:.2f}s', flush=True)

# Try LIKE query
print('\nLIKE query...', flush=True)
t0 = time.time()
rows = list(db.execute(
    "SELECT id, name, city, state FROM churches WHERE name LIKE ? LIMIT 30",
    (f'%{entry["name"][:40]}%',)
))
print(f'  {len(rows)} rows in {time.time()-t0:.2f}s', flush=True)
for r in rows[:5]:
    print(f'    {r[1][:60]} ({r[2]}, {r[3]})', flush=True)

print('\nAll good - no hangs!', flush=True)
db.close()
