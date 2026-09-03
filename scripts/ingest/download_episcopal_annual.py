#!/usr/bin/env python3
"""
Download Episcopal Church Annual yearbooks - focused search for directory-style volumes.
"""
import json, time, requests
from pathlib import Path
from datetime import datetime, timezone

DATA_DIR = Path('e:/grid/data/episcopal_annual')
DATA_DIR.mkdir(parents=True, exist_ok=True)
IA_DOWNLOAD = 'https://archive.org/download/{0}/{0}_djvu.txt'

def main():
    # Search specifically for volumes listing congregations/churches
    queries = [
        'title:(episcopal) AND (congregation OR parish OR church) AND year:[1880 TO 1950] AND format:texts',
        'title:(protestant episcopal) AND (church OR congregation) AND year:[1880 TO 1950]',
    ]
    
    all_docs = []
    for q in queries:
        r = requests.get('https://archive.org/advancedsearch.php', params={
            'q': q, 'output': 'json', 'rows': 100
        }, timeout=30)
        r.raise_for_status()
        all_docs.extend(r.json()['response']['docs'])
    
    # Filter to years with church listings
    years_found = sorted(set(d.get('year') for d in all_docs if d.get('year') and d.get('year') != '?'))
    print(f"Years found: {years_found}")
    
    manifest_path = DATA_DIR / 'manifest.json'
    existing = set()
    if manifest_path.exists():
        existing = {d['identifier'] for d in json.loads(manifest_path.read_text())}
    
    manifest = list(json.loads(manifest_path.read_text())) if manifest_path.exists() else []
    
    downloaded = 0
    for doc in all_docs:
        ident = doc.get('identifier', '')
        title = doc.get('title', 'N/A')
        year = doc.get('year', '?')
        
        if 'Methodist' in title:
            continue
        if ident in existing:
            continue
            
        print(f"  {year}: {title[:60].encode('ascii', errors='replace').decode()}...", end=' ', flush=True)
        
        url = IA_DOWNLOAD.format(ident)
        try:
            r = requests.get(url, timeout=120)
            if r.status_code == 200 and '<html' not in r.text[:200].lower():
                filepath = DATA_DIR / f'{year}_{ident}.txt'
                filepath.write_text(r.text, encoding='utf-8')
                size_mb = len(r.text) / (1024 * 1024)
                print(f"{size_mb:.1f}MB")
                manifest.append({
                    'identifier': ident,
                    'title': title,
                    'year': year,
                    'file': str(filepath.name),
                    'size_mb': round(size_mb, 2),
                    'downloaded': datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
                })
                downloaded += 1
            else:
                print('no OCR')
        except Exception as e:
            print(f'error: {e}')
        time.sleep(1.0)
    
    manifest_path.write_text(json.dumps(manifest, indent=2))
    print(f"\nDownloaded {downloaded} new volumes, {len(manifest)} total")

if __name__ == "__main__":
    main()