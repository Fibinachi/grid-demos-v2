#!/usr/bin/env python3
"""Download Episcopal Church Annual volumes from IA."""
import json, time, requests
from pathlib import Path
from datetime import datetime, timezone

DATA_DIR = Path('e:/grid/data/episcopal_annual')
DATA_DIR.mkdir(parents=True, exist_ok=True)
IA_DOWNLOAD = 'https://archive.org/download/{0}/{0}_djvu.txt'

# Known Episcopal yearbook identifiers
KNOWN_IDENTS = [
    (1871, 'protestantepisc06unkngoog'),
    (1908, 'protestantepisco00unse_0'),
]

def main():
    manifest_path = DATA_DIR / 'manifest.json'
    existing = set()
    if manifest_path.exists():
        existing = {d['identifier'] for d in json.loads(manifest_path.read_text())}
    
    manifest = list(json.loads(manifest_path.read_text())) if manifest_path.exists() else []
    
    for year, ident in KNOWN_IDENTS:
        if ident in existing:
            continue
            
        print(f"  {year}: {ident}...", end=' ', flush=True)
        
        url = IA_DOWNLOAD.format(ident)
        try:
            r = requests.get(url, timeout=120)
            if r.status_code == 200 and '<html' not in r.text[:200].lower():
                filepath = DATA_DIR / f'{year}_episcopal_almanac.txt'
                filepath.write_text(r.text, encoding='utf-8')
                size_mb = len(r.text) / (1024 * 1024)
                print(f"{size_mb:.1f}MB downloaded")
                manifest.append({
                    'identifier': ident,
                    'year': year,
                    'file': str(filepath.name),
                    'size_mb': round(size_mb, 2),
                    'downloaded': datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
                })
            else:
                print('no OCR')
        except Exception as e:
            print(f'error: {e}')
        time.sleep(1.0)
    
    manifest_path.write_text(json.dumps(manifest, indent=2))
    print("\nDone")

if __name__ == "__main__":
    main()