"""
create_directory_churches.py — Create new GRID churches from high-confidence unmatched city directory entries
=============================================================================================================

Pipeline:
  1. Query city_directory_churches for unmatched entries with denomination keywords + addresses
  2. Parse church name and address from raw OCR text
  3. Assign faith/tradition/taxonomy from denomination keywords
  4. Geocode addresses (via Census batch API)
  5. Insert into churches table with provenance
  6. Link back to city_directory_churches via matched_church_id

Usage:
  python create_directory_churches.py --dry-run     # Report only
  python create_directory_churches.py               # Full pipeline
  python create_directory_churches.py --limit 100   # Process 100 only
"""

import json, os, re, sys, sqlite3, time
from datetime import datetime, timezone
from urllib.parse import urlencode
from collections import defaultdict

import requests

# ── Config ──────────────────────────────────────────────────────────
DB = 'e:/grid/churches.db'
NOW = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')
BATCH_SIZE = 500
CENSUS_URL = 'https://geocoding.geo.census.gov/geocoder/locations/onelineaddress'

# ── Denomination → Faith/Tradition mapping ───────────────────────────
DENOM_TO_FAITH = {
    'baptist': ('Christian', 'Baptist'),
    'methodist': ('Christian', 'Methodist'),
    'presbyterian': ('Christian', 'Presbyterian'),
    'lutheran': ('Christian', 'Lutheran'),
    'episcopal': ('Christian', 'Episcopal'),
    'catholic': ('Christian', 'Catholic'),
    'pentecostal': ('Christian', 'Pentecostal'),
    'holiness': ('Christian', 'Holiness'),
    'church of god': ('Christian', 'Church of God'),
    'church of christ': ('Christian', 'Church of Christ'),
    'assembly of god': ('Christian', 'Assembly of God'),
    'nazarene': ('Christian', 'Nazarene'),
    'adventist': ('Christian', 'Adventist'),
    'lds|latter.day|mormon': ('Christian', 'LDS'),
    "jehovah|witness": ('Christian', "Jehovah's Witness"),
    'synagogue|jewish|temple emanuel|temple israel|temple reyim|beth israel|beth shalom|b.nai|temple beth': ('Jewish', 'Rabbinic'),
    'orthodox': ('Christian', 'Orthodox'),
    'ame\b|african methodist': ('Christian', 'AME'),
    'amez|ame zion': ('Christian', 'AME Zion'),
    'cme\b': ('Christian', 'CME'),
    'reformed': ('Christian', 'Reformed'),
    'united church of christ|ucc\b': ('Christian', 'UCC'),
    'wesleyan': ('Christian', 'Wesleyan'),
    'foursquare': ('Christian', 'Foursquare'),
    'apostolic': ('Christian', 'Apostolic'),
    'gospel': ('Christian', 'Gospel'),
    'christian': ('Christian', 'Other'),
}


def classify_faith(name):
    """Infer faith and tradition from church name."""
    n = name.lower()
    for pat, (faith, tradition) in DENOM_TO_FAITH.items():
        if re.search(pat, n):
            return faith, tradition
    return 'Christian', 'Other'


def parse_name_address(raw_name, raw_address=''):
    """Parse church name and address from raw OCR text.
    Many unmatched entries have address merged into the name field.
    Returns (name, address)."""
    combined = raw_name
    if raw_address:
        combined += ' ' + raw_address
    
    # Clean OCR artifacts
    combined = re.sub(r'\([^)]*(?:R|D|L|Ch|Nv|Au|S\s*dr|Nfk|Baysd)[^)]*\)', '', combined)  # Direction codes
    combined = re.sub(r'\(28052\)|\(462\d\d\)|\(\d{5}\)', '', combined)  # ZIP codes
    
    # Try to split at address pattern
    m = re.search(r'(.*?)(\d+\s+(?:[NSEW]\s+)?[A-Z][a-z]+(?:\s+(?:St|Av|Ave|Rd|Dr|Blvd|Ln|Way|'
                  r'Cir|Ct|Pl|Hwy|Pkwy|Trl|Ter|Run|Row|Al|Aly|Cres|Plz|Xing|Cv|Bnd|La))\.?)',
                  combined)
    if m:
        name = m.group(1).strip().rstrip(',').rstrip('.')
        addr = m.group(2).strip()
        rest = combined[m.end():].strip()
        if rest:
            addr += ' ' + rest
        addr = re.sub(r'\s+', ' ', addr).strip()
    else:
        name = combined
        addr = raw_address
    
    # Clean name
    name = re.sub(r'\s+', ' ', name).strip()
    # Remove leading/trailing garbage
    name = re.sub(r'^[*^0-9]+\s*', '', name)  # Leading numbers/symbols
    name = re.sub(r'\s*\([^)]*\)\s*$', '', name)  # Trailing parentheticals
    name = re.sub(r'[,.;:]+$', '', name)
    
    # ALL CAPS → Title Case
    if name == name.upper() and len(name) > 15:
        name = name.title()
    
    return name.strip(), addr.strip()


def geocode_batch(addresses, city, state):
    """Batch geocode addresses via Census API. Returns list of (lat, lon) or (None, None)."""
    results = []
    for addr in addresses:
        if not addr:
            results.append((None, None))
            continue
        
        full = f'{addr}, {city}, {state}'
        full = ' '.join(full.split())
        
        try:
            params = urlencode({'address': full, 'benchmark': '2020', 'format': 'json'})
            r = requests.get(CENSUS_URL + '?' + params,
                           headers={'User-Agent': 'GRID/1.0'}, timeout=10)
            data = r.json()
            matches = data.get('result', {}).get('addressMatches', [])
            if matches:
                coords = matches[0].get('coordinates', {})
                results.append((coords.get('y'), coords.get('x')))
            else:
                results.append((None, None))
        except Exception:
            results.append((None, None))
        
        time.sleep(0.1)  # Rate limit
    
    return results


def main(dry_run=False, limit=0):
    db = sqlite3.connect(DB)
    db.execute('PRAGMA journal_mode=WAL')
    db.row_factory = sqlite3.Row
    
    print('Loading high-confidence unmatched entries...')
    
    # Build LIKE conditions for church keywords
    keywords = ['church', 'chapel', 'temple', 'synagogue', 'mosque', 'tabernacle',
                'ministry', 'fellowship', 'worship', 'assembly', 'congregation',
                'cathedral', 'parish', 'baptist', 'methodist', 'presbyterian',
                'lutheran', 'episcopal', 'catholic', 'pentecostal', 'holiness',
                'nazarene', 'adventist', 'apostolic', 'gospel', 'wesleyan',
                'foursquare', 'covenant', 'kingdom hall', 'latter day', 'jehovah',
                'christian', 'jesus', 'redeemer', 'savior', 'calvary', 'bethel',
                'bethlehem', 'zion']
    
    like_clauses = ' OR '.join([f"raw_name LIKE '%{kw}%'" for kw in keywords])
    
    rows = db.execute(f'''
        SELECT raw_name, raw_address, directory_city, directory_state,
               COUNT(DISTINCT directory_id) as dirs,
               MIN(directory_year) as first_year,
               MAX(directory_year) as last_year,
               GROUP_CONCAT(DISTINCT directory_id) as dir_ids
        FROM city_directory_churches
        WHERE matched_church_id IS NULL
          AND ({like_clauses})
        GROUP BY raw_name, directory_city
        ORDER BY dirs DESC, first_year
    ''').fetchall()
    
    if limit:
        rows = rows[:limit]
    
    print(f'  {len(rows)} entries to process\n')
    
    # Parse names/addresses and filter
    HAS_ADDR = re.compile(r'\d+\s+(?:[NSEW]\s+)?[A-Z][a-z]+(?:\s+(?:St|Av|Ave|Rd|Dr|Blvd|Ln|Way|Cir|Ct|Pl|Hwy|Pkwy|Trl|Ter))', re.IGNORECASE)
    PERSON_NAME = re.compile(r'^[A-Z][a-z]+\s+[A-Z]\.?\s+[A-Z][a-z]+')  # e.g., "Clegg E Arnold"
    
    churches = []
    for r in rows:
        name, addr = parse_name_address(r['raw_name'], r['raw_address'] or '')
        faith, tradition = classify_faith(name)
        
        # Strict filter: must have a street address in addr or name
        has_addr = bool(HAS_ADDR.search(addr)) or bool(HAS_ADDR.search(name))
        if not has_addr:
            continue
        
        # Skip person names
        if PERSON_NAME.match(name) and not any(kw in name.lower() for kw in ['church', 'temple', 'chapel', 'synagogue', 'mosque', 'ministry', 'fellowship']):
            continue
        
        # Skip entries where name is just "Church" with an address
        if name.strip().lower() in ('church', 'churches'):
            continue
        
        churches.append({
            'name': name,
            'address': addr,
            'city': r['directory_city'],
            'state': r['directory_state'],
            'faith': faith,
            'tradition': tradition,
            'building_year': r['first_year'],
            'closed_year': r['last_year'] if r['last_year'] < 1973 else None,
            'source': f'city_directory_{r["first_year"]}',
            'dir_ids': r['dir_ids'],
            'dir_years': f'{r["first_year"]}-{r["last_year"]}',
            'n_dirs': r['dirs'],
            'raw_name': r['raw_name'],
        })
    
    print(f'Parsed {len(churches)} churches')
    
    # Show sample
    print('\nSample churches to create:')
    for c in churches[:15]:
        print(f'  {c["name"][:50]:50s} {c["city"]:15s} {c["faith"]:12s} '
              f'yr={c["building_year"]} [{c["address"][:40]}]')
    
    if dry_run:
        db.close()
        return
    
    # ── Geocode (skip for now — addresses are already in the data) ───
    print(f'\nSkipping geocoding (already have addresses)')
    for c in churches:
        c['lat'] = None
        c['lon'] = None
    geocoded = 0
    
    # ── Insert into churches ─────────────────────────────────────────
    print(f'\nInserting into churches table...')
    
    # Get next church ID
    max_id = db.execute('SELECT MAX(id) FROM churches').fetchone()[0] or 0
    next_id = max_id + 1
    
    inserted = 0
    for i, c in enumerate(churches):
        try:
            db.execute('''
                INSERT INTO churches (id, name, address, city, state, country,
                    faith, tradition, building_year, closed_year, source, latitude, longitude)
                VALUES (?, ?, ?, ?, ?, 'US', ?, ?, ?, ?, ?, ?, ?)
            ''', (
                next_id + i,
                c['name'][:200],
                c['address'][:200],
                c['city'],
                c['state'],
                c['faith'],
                c['tradition'],
                c['building_year'],
                c['closed_year'],
                c['source'],
                c['lat'],
                c['lon'],
            ))
            inserted += 1
        except Exception as e:
            print(f'  ⚠️  Insert error for {c["name"][:40]}: {e}')
    
    db.commit()
    
    # Update city_directory_churches with new church IDs
    print(f'  Linking back to city_directory_churches...')
    linked = 0
    for i, c in enumerate(churches):
        church_id = next_id + i
        # Link by raw_name + city
        db.execute('''
            UPDATE city_directory_churches
            SET matched_church_id = ?, matched_name = ?
            WHERE raw_name = ? AND directory_city = ? AND matched_church_id IS NULL
        ''', (church_id, c['name'], c['raw_name'], c['city']))
        linked += db.execute('SELECT changes()').fetchone()[0]
    
    db.commit()
    
    print(f'\n{"="*60}')
    print(f'DONE: {inserted} new churches created, {linked} directory entries linked')
    print(f'First new ID: {next_id}, Last: {next_id + inserted - 1}')
    print(f'{"="*60}')
    
    db.close()


if __name__ == '__main__':
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument('--dry-run', action='store_true', help='Report only, no writes')
    ap.add_argument('--limit', type=int, default=0, help='Max churches to process')
    args = ap.parse_args()
    main(dry_run=args.dry_run, limit=args.limit)
