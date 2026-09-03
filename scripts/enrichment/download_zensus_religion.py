"""Download Zensus 2022 religion data at Gemeinde level via Genesis REST API."""
import urllib.request
import urllib.parse
import os
import json
import sqlite3
from pathlib import Path
from datetime import datetime

GENESIS_USER = os.environ.get('GENESIS_USER', 'RE014789')
GENESIS_PASS = os.environ.get('GENESIS_PASS', '')
DB = Path(r'E:\grid\churches.db')

def genesis_post(endpoint, params):
    """POST to Genesis API with username/password as headers."""
    url = f'https://www.regionalstatistik.de/genesisws/rest/2020/{endpoint}'
    data = '&'.join(f'{k}={v}' for k, v in params.items()).encode()
    req = urllib.request.Request(url, data=data, method='POST')
    req.add_header('Content-Type', 'application/x-www-form-urlencoded')
    req.add_header('username', GENESIS_USER)
    req.add_header('password', GENESIS_PASS)
    with urllib.request.urlopen(req, timeout=60) as resp:
        return json.loads(resp.read())

def genesis_get(endpoint, params=None):
    """GET from Genesis API."""
    url = f'https://www.regionalstatistik.de/genesisws/rest/2020/{endpoint}?username={GENESIS_USER}&password={GENESIS_PASS}'
    if params:
        url += '&' + '&'.join(f'{k}={v}' for k, v in params.items())
    req = urllib.request.Request(url, method='GET')
    with urllib.request.urlopen(req, timeout=60) as resp:
        return json.loads(resp.read())

# Step 1: Find the Zensus 2022 statistics
print("=== Finding Zensus 2022 statistics ===")
result = genesis_post('catalogue/statistics', {
    'name': 'zensus',
    'area': 'all',
    'pagelength': '50',
    'language': 'de'
})
stats = result.get('List', [])
print(f"Found {len(stats)} Zensus statistics")
for s in stats:
    print(f"  {s.get('Code','')}: {s.get('Content','')[:100]}")

# Step 2: Get tables for the population compact statistic 
# Try finding the right code
print("\n=== Finding 1000A tables ===")
result = genesis_post('catalogue/tables2statistic', {
    'name': '1000A',
    'area': 'all',
    'pagelength': '50',
    'language': 'de'
})
tables = result.get('List', [])
print(f"Found {len(tables)} tables")
for t in tables:
    code = t.get('Code', '')
    name = t.get('Content', '')[:100]
    print(f"  {code}: {name}")

# Step 3: Download the religion table (1000A-1018) with Gemeinde-level data
print("\n=== Downloading 1000A-1018 (Religion) ===")
try:
    # Use tablefile endpoint for CSV download
    result = genesis_post('data/tablefile', {
        'name': '1000A-1018',
        'area': 'all',
        'compress': 'false',
        'format': 'csv',
        'language': 'de',
        'regionalmerkmal': 'GEM',  # Gemeinde level
        'regionaldepth': 'all',
    })
    print(f"Keys: {list(result.keys())}")
    if 'Content' in result:
        content = result['Content']
        print(f"Content length: {len(content)}")
        # Save to file
        with open('e:/grid/data/zensus_de_religion_gemeinde.csv', 'w', encoding='utf-8') as f:
            f.write(content)
        lines = content.split('\n')
        print(f"Lines: {len(lines)}")
        for l in lines[:20]:
            print(l[:200])
    else:
        print(json.dumps(result, indent=2)[:2000])
except Exception as e:
    print(f"Error with tablefile: {e}")
    
    # Try alternative: data/table with CSV
    print("\n=== Trying data/table endpoint ===")
    try:
        result = genesis_post('data/table', {
            'name': '1000A-1018',
            'area': 'all',
            'compress': 'false',
            'format': 'csv',
            'language': 'de',
            'regionalmerkmal': 'GEM',
        })
        print(f"Keys: {list(result.keys())}")
        print(json.dumps(result, indent=2)[:2000])
    except Exception as e2:
        print(f"Error with data/table: {e2}")
        
        # Try without regionalmerkmal
        print("\n=== Trying basic table download ===")
        try:
            result = genesis_post('data/tablefile', {
                'name': '1000A-1018',
                'area': 'all',
                'compress': 'false',
                'format': 'csv',
                'language': 'de',
            })
            print(f"Success! Keys: {list(result.keys())}")
            if 'Content' in result:
                with open('e:/grid/data/zensus_de_religion_gemeinde.csv', 'w', encoding='utf-8') as f:
                    f.write(result['Content'])
                print(f"Saved {len(result['Content'])} chars")
        except Exception as e3:
            print(f"All approaches failed: {e3}")
