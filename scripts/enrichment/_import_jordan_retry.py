#!/usr/bin/env python3
"""Retry the 2 failed Jordan governorates with xlrd engine for old .xls files."""
import sqlite3, json, urllib.request, io
import pandas as pd
from datetime import datetime

DB = r'E:\grid\churches.db'

# The 2 failed governorates
RETRY_IDS = [
    "MIGRATED-2485-2023",  # البادية الشمالية
    "MIGRATED-2489-2023",  # الكورة
]

def fetch_dataset(dataset_id):
    url = f"https://opendata.gov.jo/api/3/action/package_show?id={dataset_id}"
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'GRID/1.0'})
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode())
        result = data.get('result', {})
        if result and result.get('resources'):
            return {
                'name': result.get('title_ar', result.get('title', dataset_id)),
                'url': result['resources'][0].get('url', '')
            }
    except Exception as e:
        print(f'  {dataset_id}: {e}')
    return None

db = sqlite3.connect(DB, timeout=60)
total = 0

for did in RETRY_IDS:
    ds = fetch_dataset(did)
    if not ds or not ds['url']:
        print(f'  ⏭ {did} — not found')
        continue
    
    print(f'  Downloading {ds["name"]}...')
    try:
        req = urllib.request.Request(ds['url'], headers={'User-Agent': 'GRID/1.0'})
        with urllib.request.urlopen(req, timeout=60) as resp:
            content = resp.read()
        
        # Try calamine engine (built into pandas 3.x, handles .xls natively)
        try:
            df = pd.read_excel(io.BytesIO(content), engine='calamine')
        except:
            try:
                df = pd.read_excel(io.BytesIO(content), engine='openpyxl')
            except Exception as e2:
                print(f'    ❌ All engines failed: {e2}')
                continue
        
        print(f'  {ds["name"]}: {len(df)} rows, cols: {list(df.columns[:6])}')
        
        for _, row in df.iterrows():
            row_dict = row.to_dict()
            row_json = json.dumps(row_dict, ensure_ascii=False, default=str)
            db.execute(
                'INSERT INTO raw_jordan_mosques (raw_data, source) VALUES (?, ?)',
                (row_json, 'opendata.gov.jo')
            )
            total += 1
        db.commit()
        print(f'    ✅ Imported {len(df)} rows')
    except Exception as e:
        print(f'    ❌ {e}')

db.close()
print(f'\nAdded {total} rows. Now re-run _match_jordan_mosques.py')
