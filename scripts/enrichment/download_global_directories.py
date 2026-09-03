"""
download_global_directories.py — Download OCR text from global city directories on Internet Archive
======================================================================================================

Searches IA for city directories across the Anglosphere (UK, Canada, Australia, NZ),
downloads the DJVU OCR text, and saves to data/directories/pending/ for later batch processing.

No parsing, no matching — just raw text + metadata JSON.

Usage:
  python download_global_directories.py          # Download all
  python download_global_directories.py --dry-run # Show what's available
"""

import json, os, re, sys, time, requests
from datetime import datetime, timezone
from pathlib import Path

# ── Config ──────────────────────────────────────────────────────────
DATA_DIR = Path('e:/grid/data/directories/pending')
DATA_DIR.mkdir(parents=True, exist_ok=True)
IA_DOWNLOAD = 'https://archive.org/download/{0}/{0}_djvu.txt'
DELAY = 1.0
MAX_RESULTS = 200

# ── Region queries ───────────────────────────────────────────────────
REGIONS = {
    'UK_London': 'title:(kelly post office london directory) AND year:[1950 TO 1980]',
    'UK_London_PO': 'title:(post office london directory) AND year:[1950 TO 1980]',
    'CA_Toronto': 'title:(toronto city directory) AND year:[1950 TO 1980]',
    'CA_Hamilton': 'title:(hamilton city directory) AND year:[1950 TO 1980]',
    'CA_Ontario_general': 'title:(city directory) AND year:[1950 TO 1980] AND collection:(toronto_public_library OR toronto)',
    'CA_Windsor': 'title:(windsor city directory) AND year:[1950 TO 1980]',
    'CA_Montreal': 'title:(montreal directory lovell) AND year:[1950 TO 1980]',
    'AU_Sydney': 'title:(sydney directory) AND year:[1950 TO 1980]',
    'AU_Melbourne': 'title:(melbourne directory) AND year:[1950 TO 1980]',
    'AU_general': 'title:(sands directory OR sands mcdougall) AND year:[1900 TO 1980]',
    'NZ_general': 'title:(stones directory OR wises directory OR auckland directory) AND year:[1900 TO 1980]',
    'IN_India': 'title:(times of india directory) AND year:[1950 TO 1980]',
}


def search_ia(query, rows=MAX_RESULTS):
    r = requests.get('https://archive.org/advancedsearch.php', params={
        'q': query, 'output': 'json', 'rows': rows, 'sort': 'date'
    }, timeout=30)
    r.raise_for_status()
    return r.json()['response']['docs']


def download_ocr(identifier, filepath):
    """Download DJVU OCR to filepath. Returns True if successful."""
    url = IA_DOWNLOAD.format(identifier)
    try:
        r = requests.get(url, timeout=120)
        if r.status_code == 200 and '<html' not in r.text[:200].lower():
            filepath.write_text(r.text, encoding='utf-8')
            size_mb = len(r.text) / (1024 * 1024)
            return True, size_mb
    except requests.Timeout:
        pass
    except Exception as e:
        pass
    return False, 0


def main(dry_run=False):
    manifest_path = DATA_DIR / 'manifest.json'
    existing = {}
    if manifest_path.exists():
        existing = {d['identifier'] for d in json.loads(manifest_path.read_text())}
    
    manifest = list(json.loads(manifest_path.read_text())) if manifest_path.exists() else []
    total_downloaded = 0
    
    for region, query in REGIONS.items():
        print(f'\n{"="*60}')
        print(f'REGION: {region}')
        print(f'{"="*60}')
        
        docs = search_ia(query)
        print(f'  Found {len(docs)} results')
        
        for doc in docs:
            ident = doc.get('identifier', '')
            title = doc.get('title', 'N/A')
            year = doc.get('year', '?')
            
            if ident in existing:
                continue
            
            filepath = DATA_DIR / f'{ident}.txt'
            
            if dry_run:
                print(f'  [DRY-RUN] {title[:90]} ({year})')
                continue
            
            print(f'  📥 {title[:80]} ({year})...', end=' ', flush=True)
            ok, size = download_ocr(ident, filepath)
            
            if ok:
                print(f'{size:.1f}MB ✅')
                manifest.append({
                    'identifier': ident,
                    'title': title,
                    'year': year,
                    'region': region,
                    'file': str(filepath.name),
                    'size_mb': round(size, 2),
                    'downloaded': datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
                })
                total_downloaded += 1
            else:
                print('no OCR ❌')
            
            time.sleep(DELAY)
    
    # Save manifest
    if not dry_run:
        manifest_path.write_text(json.dumps(manifest, indent=2))
    
    print(f'\n{"="*60}')
    print(f'DONE: {total_downloaded} downloaded, {len(manifest)} total in manifest')
    print(f'Files in: {DATA_DIR}')
    print(f'{"="*60}')


if __name__ == '__main__':
    dry = '--dry-run' in sys.argv or '--dry' in sys.argv
    main(dry_run=dry)
