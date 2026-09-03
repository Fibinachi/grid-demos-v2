#!/usr/bin/env python3
"""
Global GCatholic Special Churches Scraper
=========================================
Scrapes cathedrals, basilicas, shrines, and World Heritage churches
from all 254 countries on gcatholic.org.

Data captured per church:
  - name, alternate_name, gcatholic_id
  - address, city, region, country, country_code
  - latitude, longitude (extracted from map link)
  - diocese, archdiocese, province (Catholic hierarchy)
  - church_type (Cathedral, Basilica, Shrine, World Heritage Site)
  - rite (Roman Latin, Eastern, etc.)
  - patron_saint, dedication
  - website
  - last_updated (from GCatholic)

Output: data/gcatholic_global.csv
Checkpoint: data/gcatholic_global_checkpoint.json (resume-safe)

Usage:
    .venv\Scripts\python.exe scripts/scrapers/denominations/catholic_gcatholic_global.py
    .venv\Scripts\python.exe scripts/scrapers/denominations/catholic_gcatholic_global.py --country FR,IT,DE  # specific countries
    .venv\Scripts\python.exe scripts/scrapers/denominations/catholic_gcatholic_global.py --phase churches  # skip country list refresh
"""

import csv, json, os, re, sys, time, urllib.request
from datetime import datetime, timezone
from pathlib import Path

# ── Config ──
PROJECT_ROOT = Path(__file__).resolve().parents[3]
DATA_DIR = PROJECT_ROOT / 'data'
OUT_CSV = DATA_DIR / 'gcatholic_global.csv'
CHECKPOINT = DATA_DIR / 'gcatholic_global_checkpoint.json'
COUNTRIES_JSON = DATA_DIR / 'gcatholic_countries.json'

UA = 'GrantWizard/2.0 (academic research; contact@example.com)'
DELAY = 1.0  # seconds between requests (be polite)
TIMEOUT = 10  # seconds for church lists; details can take longer

# ── Utilities ──
def log(msg):
    print(f'[{datetime.now().strftime("%H:%M:%S")}] {msg}', flush=True)

def fetch(url, retries=2):
    for attempt in range(retries + 1):
        try:
            req = urllib.request.Request(url, headers={'User-Agent': UA})
            with urllib.request.urlopen(req, timeout=TIMEOUT) as f:
                return f.read().decode('utf-8', 'replace')
        except Exception as e:
            if attempt < retries:
                time.sleep(2)
                continue
            return None

def save_checkpoint(data):
    # Convert sets to lists for JSON
    save_data = dict(data)
    save_data['done_churches'] = list(data.get('done_churches', []))
    with open(CHECKPOINT, 'w') as f:
        json.dump(save_data, f, indent=2)

def load_checkpoint():
    if CHECKPOINT.exists():
        with open(CHECKPOINT) as f:
            data = json.load(f)
            data['done_churches'] = set(data.get('done_churches', []))
            return data
    return {'done_countries': [], 'done_churches': set(), 'total_churches': 0}

def extract_gps(html):
    """Extract GPS coordinates from GCatholic map init data.
    Pattern: gc.init2([['...','...','/churches/france/1865','... 44.2065, 0.6188']])"""
    # Look for coordinates in the gc.init2 array
    m = re.search(r"gc\.init2\(\[\['[^']+','[^']+','[^']+','[^']*?([-\d.]+),\s*([-\d.]+)", html)
    if m:
        return float(m.group(1)), float(m.group(2))
    # Alternative: data-coords attribute
    m = re.search(r'data-coords="([-\d.]+),\s*([-\d.]+)"', html)
    if m:
        return float(m.group(1)), float(m.group(2))
    # Third pattern: coordinates in page text like "44.2065, 0.6188" near location info
    m = re.search(r'Location:.*?([-\d.]+),\s*([-\d.]+)', html, re.DOTALL)
    if m:
        return float(m.group(1)), float(m.group(2))
    return None, None

def extract_field(html, label):
    """Extract a labeled field from GCatholic page text."""
    # Pattern: "Label: Value"
    m = re.search(rf'{re.escape(label)}:\s*([^<\n]+)', html)
    if m:
        return m.group(1).strip()
    return None

# ── Phase 1: Country List ──
def scrape_countries():
    """Get all 254 country codes and names from the main dioceses page.
    Uses the pre-extracted list if available (avoids JS-rendering issues)."""
    if COUNTRIES_JSON.exists():
        with open(COUNTRIES_JSON) as f:
            countries = json.load(f)
        log(f'Loaded {len(countries)} countries from {COUNTRIES_JSON}')
        return countries

    log('Phase 1: Scraping country list...')
    html = fetch('https://www.gcatholic.org/dioceses/')
    if not html:
        log('ERROR: Could not fetch dioceses page')
        return []

    # Extract country links: /dioceses/country/XX
    # The page has <a href="/dioceses/country/FR">France</a>
    countries = []
    for m in re.finditer(
        r'<a\s+href="(/dioceses/country/([A-Z]{2,3}))"[^>]*>([^<]+)</a>',
        html, re.I
    ):
        code = m.group(2)
        name = m.group(3).strip()
        if len(code) >= 2 and len(name) > 1 and not name.startswith('<'):
            countries.append({
                'code': code,
                'name': name,
                'url': 'https://www.gcatholic.org' + m.group(1),
            })

    # Also try country links with different URL pattern
    if not countries:
        for m in re.finditer(
            r'<a\s+href="[^"]*?country[/-]([A-Z]{2,3})[^"]*"[^>]*>([^<]+)</a>',
            html, re.I
        ):
            code = m.group(1)
            name = m.group(2).strip()
            if len(code) >= 2 and len(name) > 1:
                countries.append({
                    'code': code,
                    'name': name,
                    'url': f'https://www.gcatholic.org/dioceses/country/{code}',
                })

    # Deduplicate by code
    seen = set()
    unique = []
    for c in countries:
        if c['code'] not in seen:
            seen.add(c['code'])
            unique.append(c)

    log(f'Found {len(unique)} countries')
    if unique:
        with open(COUNTRIES_JSON, 'w') as f:
            json.dump(unique, f, indent=2)
    return unique


# ── Phase 2: Church List per Country ──
def scrape_country_churches(country_code, country_name):
    """Get all special church links for a country."""
    url = f'https://gcatholic.org/churches/data/all-{country_code}'
    # Short timeout for church list pages (they're small)
    html = fetch(url, retries=0)  # no retries on church list
    if not html:
        log(f'  No church data page for {country_name} ({country_code})')
        return []

    churches = []
    # Pattern: <a href="../france/1865">Cathédrale Saint-Caprais</a>
    # The base is gcatholic.org/churches/data/all-XX, so ../ goes to churches/
    for m in re.finditer(
        r'<a\s+href="\.\./([a-z]+)/(\d+)"[^>]*>\s*([^<]+?)\s*</a>',
        html, re.I
    ):
        country_dir = m.group(1)  # e.g. "france"
        church_id = m.group(2)    # e.g. "1865"
        name = m.group(3).strip()
        name = re.sub(r'\s+', ' ', name)
        if name and len(name) > 3 and not name.startswith('<') and not re.match(r'^[\s\d]+$', name):
            churches.append({
                'gcatholic_id': church_id,
                'name': name,
                'url': f'https://www.gcatholic.org/churches/{country_dir}/{church_id}',
                'country_code': country_code,
                'country': country_name,
            })

    return churches


# ── Phase 3: Individual Church Details ──
def scrape_church_detail(church):
    """Scrape structured details from an individual church page."""
    html = fetch(church['url'])
    if not html:
        return church

    # GCatholic uses <span class="label">Field: </span>Value patterns
    # Extract known fields
    fields = {
        'Jurisdiction': 'diocese',
        'Type': 'church_type',
        'Rite': 'rite',
        'Patron': 'patron_saint',
        'Address': 'address_raw',
        'History': 'history_note',
    }

    for label, key in fields.items():
        # Pattern: <span class="label">Type: </span><img...><a...>Cathedral</a></p>
        m = re.search(
            rf'<span\s+class="label">\s*{re.escape(label)}:\s*</span>(.*?)</p>',
            html, re.I | re.DOTALL
        )
        if m:
            # Strip all HTML tags, just get the text
            val = re.sub(r'<[^>]+>', ' ', m.group(1))
            val = re.sub(r'\s+', ' ', val).strip()
            if val and val != '&nbsp;':
                church[key] = val

    # Extract diocese specifically
    if not church.get('diocese'):
        m = re.search(r'Diocese of\s+<span[^>]*>([^<]+)</span>', html, re.I)
        if m:
            church['diocese'] = m.group(1).strip()

    # Parse church_type into boolean flags
    if church.get('church_type'):
        ct = church['church_type']
        church['is_cathedral'] = 'Cathedral' in ct
        church['is_basilica'] = 'Basilica' in ct
        church['is_shrine'] = 'Shrine' in ct
        church['is_world_heritage'] = 'World Heritage' in ct
        church['is_co_cathedral'] = 'Co-Cathedral' in ct
        church['is_pro_cathedral'] = 'Pro-Cathedral' in ct

    # Extract Plus Code (Google Maps location)
    m = re.search(r'query=([A-Z0-9+%]+)', html)
    if m:
        church['plus_code'] = m.group(1).replace('%2B', '+')

    # Extract GCatholic Church ID (confirm)
    m = re.search(r'GCatholic Church ID:\s*(\d+)', html)
    if m:
        church['gcatholic_id'] = m.group(1)

    # Extract website
    m = re.search(r'Websites?:?\s*</span>\s*<a\s+href="([^"]+)"', html, re.I)
    if m:
        church['website'] = m.group(1)

    # Extract "Last updated" date
    m = re.search(r'Last updated on (\d{4}\.\d{2}\.\d{2})', html)
    if m:
        church['gcatholic_updated'] = m.group(1)

    # Extract alternate name from title: <h1>Name<br>AlternateName</h1>
    m = re.search(r'<h1>[^<]+<br>([^<]+)</h1>', html)
    if m:
        church['alternate_name'] = m.group(1).strip()

    return church


# ── Main ──
def main():
    target_countries = None
    if '--country' in sys.argv:
        idx = sys.argv.index('--country')
        target_countries = set(sys.argv[idx + 1].upper().split(','))

    log('=== GCatholic Global Special Churches Scraper ===')

    # Load checkpoint
    ck = load_checkpoint()
    log(f'Checkpoint: {len(ck["done_countries"])} countries done, '
        f'{len(ck["done_churches"])} churches scraped')

    # Phase 1: Country list
    countries = scrape_countries()
    if target_countries:
        countries = [c for c in countries if c['code'] in target_countries]
        log(f'Filtered to {len(countries)} target countries: {target_countries}')

    # Phase 2: Collect all church links, save checkpoint per country
    all_churches = []
    fieldnames = [
        'gcatholic_id', 'name', 'alternate_name', 'church_type',
        'is_cathedral', 'is_basilica', 'is_shrine', 'is_world_heritage',
        'is_co_cathedral', 'is_pro_cathedral',
        'diocese', 'rite', 'patron_saint',
        'address_raw', 'plus_code',
        'country', 'country_code', 'latitude', 'longitude',
        'website', 'url', 'history_note',
        'gcatholic_updated', 'source',
    ]

    # Load existing CSV if resuming
    existing_by_id = {}
    if OUT_CSV.exists():
        with open(OUT_CSV, encoding='utf-8') as f:
            for row in csv.DictReader(f):
                existing_by_id[row['gcatholic_id']] = row
        log(f'Loaded {len(existing_by_id)} existing churches from CSV')

    # Sync checkpoint done_churches with CSV (CSV is ground truth)
    for gid in existing_by_id:
        ck['done_churches'].add(gid)
    save_checkpoint(ck)

    churches_to_scrape = []

    # If all countries done, skip Phase 2 but still need to rebuild pending list
    # Re-fetch church lists for countries that have unscraped churches
    if len(ck['done_countries']) >= len(countries):
        log('All countries catalogued. Rebuilding pending list from unscraped churches...')
        # Re-scan countries for churches not yet in CSV
        for country in countries:
            try:
                country_churches = scrape_country_churches(country['code'], country['name'])
                for ch in country_churches:
                    if ch['gcatholic_id'] not in existing_by_id and ch['gcatholic_id'] not in ck['done_churches']:
                        churches_to_scrape.append(ch)
            except Exception:
                pass
            time.sleep(0.3)  # faster since we're not saving checkpoint per country

    # Original Phase 2 loop for countries not yet catalogued
    for i, country in enumerate(countries):
        if country['code'] in ck['done_countries']:
            continue

        try:
            log(f'\n[{i+1}/{len(countries)}] {country["name"]} ({country["code"]})')
            country_churches = scrape_country_churches(country['code'], country['name'])
            log(f'  Found {len(country_churches)} special churches')

            new_count = 0
            for ch in country_churches:
                if ch['gcatholic_id'] not in existing_by_id and ch['gcatholic_id'] not in ck['done_churches']:
                    churches_to_scrape.append(ch)
                    new_count += 1

            if new_count > 0:
                log(f'  {new_count} new churches to scrape')

        except Exception as e:
            log(f'  ERROR: {e}')

        # Mark country done regardless (skip failing ones)
        ck['done_countries'].append(country['code'])
        save_checkpoint(ck)
        time.sleep(DELAY)

        time.sleep(DELAY)

    log(f'\n=== Phase 3: Scraping {len(churches_to_scrape)} church details ===')

    # Load existing churches
    all_churches = list(existing_by_id.values())

    for i, ch in enumerate(churches_to_scrape):
        if i > 0 and i % 50 == 0:
            log(f'  Progress: {i}/{len(churches_to_scrape)} ({i/len(churches_to_scrape)*100:.0f}%)')
            # Save intermediate
            ck['done_churches'].update(c['gcatholic_id'] for c in churches_to_scrape[:i])
            ck['total_churches'] = len(all_churches) + i
            save_checkpoint(ck)
            # Write CSV
            _write_csv(OUT_CSV, fieldnames, all_churches + churches_to_scrape[:i])

        ch = scrape_church_detail(ch)
        ch['source'] = 'gcatholic_global'
        all_churches.append(ch)
        ck['done_churches'].add(ch['gcatholic_id'])

        if i > 0 and i % 5 == 0:
            time.sleep(DELAY)  # Rate limiting
        else:
            time.sleep(0.5)

    # Mark countries as done
    for country in countries:
        ck['done_countries'].append(country['code'])
    ck['total_churches'] = len(all_churches)
    save_checkpoint(ck)

    # Final write
    _write_csv(OUT_CSV, fieldnames, all_churches)
    log(f'\nDone! {len(all_churches)} churches -> {OUT_CSV}')


def _write_csv(path, fieldnames, churches):
    """Write churches to CSV, keeping existing rows."""
    with open(path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction='ignore')
        writer.writeheader()
        for ch in churches:
            writer.writerow(ch)


if __name__ == '__main__':
    main()
