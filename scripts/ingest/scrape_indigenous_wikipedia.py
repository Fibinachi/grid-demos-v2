"""Scrape remaining indigenous datasets: Maya sites (Wikipedia), South American sites."""
import urllib.request
import json
import os
import csv
import re

DEST = r'E:\grid\data\sources\indigenous'
os.makedirs(DEST, exist_ok=True)

def save_file(content, fname, desc, binary=False):
    fp = os.path.join(DEST, fname)
    mode = 'wb' if binary else 'w'
    enc = None if binary else 'utf-8'
    with open(fp, mode, encoding=enc) as f:
        f.write(content)
    print(f'  OK ({os.path.getsize(fp)/1024:.0f}KB): {desc}')

# ========================================
# 1. Wikipedia list of Maya sites
# ========================================
print('=== MAYA SITES (Wikipedia) ===')
try:
    req = urllib.request.Request(
        'https://en.wikipedia.org/w/api.php?action=parse&page=List_of_Maya_sites&prop=wikitext&format=json',
        headers={'User-Agent': 'GRID-Project/1.0'}
    )
    data = json.loads(urllib.request.urlopen(req, timeout=30).read().decode())
    text = data['parse']['wikitext']['*']

    # Extract table rows from wikitext
    sites = []
    in_table = False
    for line in text.split('\n'):
        if line.startswith('{|') and 'wikitable' in line:
            in_table = True
            continue
        if in_table and line.startswith('|}'):
            in_table = False
        elif in_table and line.startswith('|') and not line.startswith('|-') and not line.startswith('|!'):
            parts = [p.strip() for p in line[1:].split('||')]
            # Clean wiki markup
            clean = [re.sub(r'<[^>]+>', '', re.sub(r'\[\[([^|\]]+)(?:\|[^\]]+)?\]\]', r'\1', p)).strip() 
                     for p in parts]
            if len(clean) >= 2 and clean[0] and not clean[0].startswith('!'):
                sites.append(clean[:4])

    csv_path = os.path.join(DEST, 'maya_sites_wikipedia.csv')
    with open(csv_path, 'w', encoding='utf-8', newline='') as f:
        w = csv.writer(f)
        w.writerow(['site_name', 'location', 'notes', 'extra'])
        w.writerows(sites)
    print(f'  OK: {len(sites)} Maya sites scraped from Wikipedia')
except Exception as e:
    print(f'  FAIL: {e}')

# ========================================
# 2. Also try Mesoamerican sites via Wikipedia category
# ========================================
print()
print('=== MESOAMERICAN SITES (Wikipedia category) ===')
try:
    # Get pages in "Mesoamerican sites" category
    req = urllib.request.Request(
        'https://en.wikipedia.org/w/api.php?action=query&list=categorymembers&cmtitle=Category:Mesoamerican_sites&cmlimit=500&format=json',
        headers={'User-Agent': 'GRID-Project/1.0'}
    )
    data = json.loads(urllib.request.urlopen(req, timeout=30).read().decode())
    pages = [(m['pageid'], m['title']) for m in data['data']['categorymembers']]
    
    csv_path = os.path.join(DEST, 'mesoamerican_sites_wikipedia.csv')
    with open(csv_path, 'w', encoding='utf-8', newline='') as f:
        w = csv.writer(f)
        w.writerow(['page_id', 'title'])
        w.writerows(pages)
    print(f'  OK: {len(pages)} Mesoamerican sites from Wikipedia category')
except Exception as e:
    print(f'  FAIL: {e}')

# ========================================
# 3. Pre-Columbian archaeological sites (broader)
# ========================================
print()
print('=== PRE-COLUMBIAN SITES ===')
try:
    req = urllib.request.Request(
        'https://en.wikipedia.org/w/api.php?action=query&list=categorymembers&cmtitle=Category:Pre-Columbian_archaeological_sites&cmlimit=500&format=json',
        headers={'User-Agent': 'GRID-Project/1.0'}
    )
    data = json.loads(urllib.request.urlopen(req, timeout=30).read().decode())
    pages = [(m['pageid'], m['title']) for m in data['data']['categorymembers']]

    csv_path = os.path.join(DEST, 'precolumbian_sites_wikipedia.csv')
    with open(csv_path, 'w', encoding='utf-8', newline='') as f:
        w = csv.writer(f)
        w.writerow(['page_id', 'title'])
        w.writerows(pages)
    print(f'  OK: {len(pages)} Pre-Columbian sites from Wikipedia')
except Exception as e:
    print(f'  FAIL: {e}')

# ========================================
# 4. Also try Inca/Aztec sites
# ========================================
print()
print('=== INCA & AZTEC SITES ===')
for cat, fname in [
    ('Category:Inca_sites', 'inca_sites_wikipedia.csv'),
    ('Category:Aztec_sites', 'aztec_sites_wikipedia.csv'),
    ('Category:Andean_preceramic', 'andean_sites_wikipedia.csv'),
]:
    try:
        req = urllib.request.Request(
            f'https://en.wikipedia.org/w/api.php?action=query&list=categorymembers&cmtitle={cat}&cmlimit=500&format=json',
            headers={'User-Agent': 'GRID-Project/1.0'}
        )
        data = json.loads(urllib.request.urlopen(req, timeout=30).read().decode())
        pages = [(m['pageid'], m['title']) for m in data.get('query', {}).get('categorymembers', [])]
        
        csv_path = os.path.join(DEST, fname)
        with open(csv_path, 'w', encoding='utf-8', newline='') as f:
            w = csv.writer(f)
            w.writerow(['page_id', 'title'])
            w.writerows(pages)
        print(f'  OK: {len(pages)} sites — {fname}')
    except Exception as e:
        print(f'  FAIL ({fname}): {e}')

# ========================================
# FINAL SUMMARY
# ========================================
print()
print('=' * 60)
print('FINAL FILE LIST')
print('=' * 60)
total = 0
for f in sorted(os.listdir(DEST)):
    fp = os.path.join(DEST, f)
    if os.path.isfile(fp):
        sz = os.path.getsize(fp) / (1024 * 1024)
        total += sz
        print(f'  {sz:8.1f} MB  {f}')
print(f'\n  Total: {total:.1f} MB  |  {len(os.listdir(DEST))} files')
