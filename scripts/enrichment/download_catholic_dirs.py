"""
Download all available Catholic directory OCR text from Internet Archive.
Skips years we already have in data/directories/.
"""
import requests, json, os, re, time, sys

DIR_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), 'data', 'directories')
IA_LIST = os.path.join(DIR_DIR, 'ia_catholic_dirs.json')
DRY_RUN = '--dry-run' in sys.argv

# Load search results
with open(IA_LIST, encoding='utf-8') as f:
    items = json.load(f)

# Deduplicate by year — prefer identifiers with "officialcatholic" or "catholic-directory" pattern
by_year = {}
for item in items:
    year = item['year']
    ident = item['identifier']
    if year not in by_year:
        by_year[year] = item
    else:
        # Prefer cleaner identifiers
        old = by_year[year]['identifier']
        if 'officialcatholic' in ident and 'officialcatholic' not in old:
            by_year[year] = item
        elif 'catholic-directory' in ident and 'catholic-directory' not in old:
            by_year[year] = item

# Check what we already have
have = set()
for f in os.listdir(DIR_DIR):
    if f.startswith('catholic_dir_') and f.endswith('.txt'):
        m = re.search(r'(\d{4})', f)
        if m:
            have.add(int(m.group(1)))

# Filter to missing years
to_download = [(y, item) for y, item in sorted(by_year.items()) if y not in have]
print(f"Total unique years on IA: {len(by_year)}")
print(f"Already have: {len(have)}")
print(f"To download: {len(to_download)}")
if DRY_RUN:
    print("DRY RUN — showing what would download:")
    for year, item in to_download[:20]:
        print(f"  {year}: {item['identifier']}")
    sys.exit(0)

# Download OCR text
session = requests.Session()
session.headers.update({'User-Agent': 'GRID-Project/1.0 (academic research; charlesaprescottjr@gmail.com)'})

downloaded = 0
failed = 0
for i, (year, item) in enumerate(to_download):
    ident = item['identifier']
    out_path = os.path.join(DIR_DIR, f'catholic_dir_{year}.txt')
    
    # IA OCR text URL pattern
    url = f'https://archive.org/download/{ident}/{ident}_djvu.txt'
    
    print(f"[{i+1}/{len(to_download)}] {year}: {ident}...", end=' ', flush=True)
    
    try:
        r = session.get(url, timeout=60)
        if r.status_code == 200 and len(r.text) > 10000:
            with open(out_path, 'w', encoding='utf-8') as f:
                f.write(r.text)
            size_mb = len(r.text) / (1024 * 1024)
            downloaded += 1
            print(f"OK ({size_mb:.1f}MB)")
        else:
            # Try alternate URL pattern
            url2 = f'https://archive.org/download/{ident}/{ident}_djvu.txt'
            r2 = session.get(url2, timeout=60)
            if r2.status_code == 200 and len(r2.text) > 10000:
                with open(out_path, 'w', encoding='utf-8') as f:
                    f.write(r2.text)
                size_mb = len(r2.text) / (1024 * 1024)
                downloaded += 1
                print(f"OK alt ({size_mb:.1f}MB)")
            else:
                failed += 1
                print(f"FAIL (HTTP {r.status_code}, {len(r.text)} chars)")
    except Exception as e:
        failed += 1
        print(f"ERROR: {e}")
    
    # Rate limit: 1 request per second to be polite
    time.sleep(1)

print(f"\nDone: {downloaded} downloaded, {failed} failed")
