#!/usr/bin/env python3
"""
Import Jordan mosque data from opendata.gov.jo

Source: Ministry of Awqaf Islamic Affairs and Holy Places
License: Jordanian Open Government Data License (commercial use allowed)

Usage: python scripts/enrichment/_import_jordan_mosques.py
"""
import sqlite3
import json
import urllib.request
from datetime import datetime

DB = r'E:\grid\churches.db'

# Known mosque dataset IDs from opendata.gov.jo
# Pattern: MIGRATED-{id}-2023, governorate-by-governorate
DATASET_IDS = [
    "MIGRATED-2482-2023",  # Ma'an
    "MIGRATED-2483-2023",  # Ajloun (maybe)
    "MIGRATED-2484-2023",
    "MIGRATED-2485-2023",
    "MIGRATED-2486-2023",
    "MIGRATED-2487-2023",
    "MIGRATED-2488-2023",
    "MIGRATED-2489-2023",
    "MIGRATED-2490-2023",
    "MIGRATED-2491-2023",
    "MIGRATED-2492-2023",
    "MIGRATED-2493-2023",
]

def fetch_dataset(dataset_id):
    """Fetch dataset metadata and download URL from Jordan open data API."""
    url = f"https://opendata.gov.jo/api/3/action/package_show?id={dataset_id}"
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'GRID/1.0'})
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode())
        result = data.get('result', {})
        if not result:
            return None
        
        resources = result.get('resources', [])
        if resources:
            download_url = resources[0].get('url', '')
            name = result.get('title_ar', result.get('title', dataset_id))
            return {'name': name, 'url': download_url, 'id': dataset_id}
    except Exception as e:
        print(f'  {dataset_id}: {e}')
    return None


def main():
    print('Fetching Jordan mosque datasets from opendata.gov.jo...')
    
    datasets = []
    for did in DATASET_IDS:
        ds = fetch_dataset(did)
        if ds and ds['url']:
            datasets.append(ds)
            print(f'  ✅ {ds["name"]} — {ds["url"][:80]}')
        else:
            print(f'  ⏭  {did} — not found or empty')
    
    print(f'\nFound {len(datasets)} mosque datasets')
    
    if not datasets:
        print('Try searching: https://opendata.gov.jo/en/search?q=mosques')
        return
    
    # Download each XLS file and parse
    import pandas as pd
    
    all_rows = []
    for ds in datasets:
        try:
            req = urllib.request.Request(ds['url'], headers={'User-Agent': 'GRID/1.0'})
            with urllib.request.urlopen(req, timeout=60) as resp:
                content = resp.read()
            
            # Try reading as Excel
            import io
            df = pd.read_excel(io.BytesIO(content))
            print(f'\n{ds["name"]}: {len(df)} rows, columns: {list(df.columns[:8])}')
            print(f'  Sample: {df.head(2).to_string()}')
            
            # Add source info
            df['source_dataset'] = ds['name']
            df['source_url'] = ds['url']
            all_rows.append(df)
        except Exception as e:
            print(f'  ❌ {ds["name"]}: {e}')
    
    if not all_rows:
        print('\nNo data loaded.')
        return
    
    merged = pd.concat(all_rows, ignore_index=True)
    print(f'\nTotal raw records: {len(merged)}')
    
    # Store in DB
    db = sqlite3.connect(DB, timeout=60)
    
    db.executescript('''
        CREATE TABLE IF NOT EXISTS raw_jordan_mosques (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            raw_data TEXT,               -- Full row as JSON
            mosque_name_ar TEXT,         -- Arabic name
            mosque_name_en TEXT,         -- English name if available
            governorate TEXT,            -- Province
            city TEXT,                   -- City/village
            mosque_type TEXT,            -- Friday mosque, neighborhood, etc.
            source TEXT DEFAULT 'opendata.gov.jo',
            imported_at TEXT DEFAULT (date('now'))
        );
    ''')
    
    # Store all data as JSON blobs for now (we'll parse columns later)
    db.execute('DELETE FROM raw_jordan_mosques')
    for _, row in merged.iterrows():
        row_dict = row.to_dict()
        row_json = json.dumps(row_dict, ensure_ascii=False, default=str)
        db.execute(
            'INSERT INTO raw_jordan_mosques (raw_data, source) VALUES (?, ?)',
            (row_json, 'opendata.gov.jo')
        )
    
    db.commit()
    total = db.execute("SELECT COUNT(*) FROM raw_jordan_mosques").fetchone()[0]
    
    # Provenance
    now = datetime.now().isoformat()
    db.execute('''
        INSERT INTO provenance_log
            (source, script_name, started_at, completed_at,
             churches_inserted, fields_populated, status, notes)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    ''', (
        'opendata_gov_jo',
        '_import_jordan_mosques.py',
        now, now, total,
        'mosque_name_ar,governorate,mosque_type',
        'completed',
        f'{total} Jordan mosques imported from Ministry of Awqaf'
    ))
    db.commit()
    db.close()
    
    print(f'\n{"="*60}')
    print(f'Imported {total} Jordan mosques → raw_jordan_mosques')
    print(f'Next: match to churches table by name/geo, enrich contacts')
    print(f'{"="*60}')

if __name__ == '__main__':
    main()
