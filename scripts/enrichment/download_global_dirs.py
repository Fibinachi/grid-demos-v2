"""
download_global_dirs.py — Download OCR text from all available non-US city directories on IA
=============================================================================================
Just downloads — no parsing, no matching. Saves to data/directories/global/ for batch processing later.
"""

import os, time, requests

DATA_DIR = 'e:/grid/data/directories/global'
os.makedirs(DATA_DIR, exist_ok=True)

IA_URL = 'https://archive.org/advancedsearch.php'
DL_TMPL = 'https://archive.org/download/{0}/{0}_djvu.txt'

# ── Search queries ────────────────────────────────────────────────────
QUERIES = {
    'UK': [
        ('kelly', 'identifier:(kellyspostoffice) AND year:[1950 TO 1980]'),
        ('london_po', 'title:(post office london directory) AND year:[1950 TO 1980]'),
    ],
    'CA': [
        ('toronto', 'identifier:(torontocitydirectory) AND year:[1950 TO 1980]'),
        ('hamilton', 'title:(vernon hamilton city directory) AND year:[1950 TO 1980]'),
        ('ontario', 'collection:WindsorOntarioCityDirectories'),
    ],
}

def search_ia(query):
    r = requests.get(IA_URL, params={'q': query, 'output': 'json', 'rows': 200}, timeout=30)
    r.raise_for_status()
    return r.json()['response']['docs']

def download(identifier, label=''):
    path = os.path.join(DATA_DIR, f'{identifier}.txt')
    if os.path.exists(path) and os.path.getsize(path) > 10000:
        return path  # Already downloaded
    
    url = DL_TMPL.format(identifier)
    try:
        r = requests.get(url, timeout=120)
        if r.status_code == 200 and '<html' not in r.text[:200].lower():
            with open(path, 'w', encoding='utf-8') as f:
                f.write(r.text)
            return path
    except:
        pass
    return None

# ── Download all ──────────────────────────────────────────────────────
total_downloaded = 0
total_skipped = 0

for region, search_queries in QUERIES.items():
    print(f'\n{"="*60}')
    print(f'REGION: {region}')
    
    for label, query in search_queries:
        docs = search_ia(query)
        print(f'\n  [{label}] {len(docs)} results')
        
        for i, doc in enumerate(docs):
            ident = doc.get('identifier', '')
            title = doc.get('title', '')[:80]
            year = doc.get('year', '?')
            
            path = os.path.join(DATA_DIR, f'{ident}.txt')
            if os.path.exists(path) and os.path.getsize(path) > 10000:
                total_skipped += 1
                continue
            
            result = download(ident, label)
            if result:
                size_kb = os.path.getsize(result) // 1024
                total_downloaded += 1
                print(f'    {total_downloaded:3d}. [{year}] {title[:60]} ({size_kb:,} KB)')
            
            time.sleep(0.5)  # Be nice to IA
    
    print(f'\n  {region} done: {total_downloaded} downloaded, {total_skipped} skipped')

print(f'\n{"="*60}')
print(f'TOTAL: {total_downloaded} downloaded, {total_skipped} skipped')
print(f'Files in: {DATA_DIR}')
