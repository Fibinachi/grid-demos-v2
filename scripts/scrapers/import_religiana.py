"""
import_religiana.py — Import Religiana European religious heritage buildings.

Source: https://religiana.com (15,155 pins extracted from map)
Strategy: Batch concurrent HTTP fetch → sequential DB insert.
Phase 1: Fetch N pages in parallel threads (HTTP only, no DB).
Phase 2: Insert results serially into churches.db.
Repeat for each batch.

Usage:
    python scripts/scrapers/import_religiana.py            # full import
    python scripts/scrapers/import_religiana.py --limit 10 # test batch
"""
import json, os, re, time, sys, argparse, sqlite3
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone

import requests
from bs4 import BeautifulSoup

PROJECT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, PROJECT)

from gw_db import connect, Provenance

# ── paths ──
PINS_FILE = os.path.join(PROJECT, 'data', 'religiana_pins.json')
DB_PATH = os.path.join(PROJECT, 'churches.db')
CK_FILE = os.path.join(PROJECT, 'data', 'religiana_checkpoint.json')

UA = 'GRID/1.0 (Religiana importer)'

BATCH_FETCH = 500

COUNTRY_MAP = {
    'FR': 'France', 'GB': 'United Kingdom', 'IT': 'Italy', 'ES': 'Spain',
    'DE': 'Germany', 'PT': 'Portugal', 'NL': 'Netherlands', 'BE': 'Belgium',
    'CH': 'Switzerland', 'AT': 'Austria', 'IE': 'Ireland', 'DK': 'Denmark',
    'SE': 'Sweden', 'NO': 'Norway', 'FI': 'Finland', 'PL': 'Poland',
    'CZ': 'Czech Republic', 'SK': 'Slovakia', 'HU': 'Hungary', 'RO': 'Romania',
    'BG': 'Bulgaria', 'GR': 'Greece', 'HR': 'Croatia', 'SI': 'Slovenia',
    'LT': 'Lithuania', 'LV': 'Latvia', 'EE': 'Estonia', 'LU': 'Luxembourg',
    'MT': 'Malta', 'CY': 'Cyprus', 'IS': 'Iceland', 'LI': 'Liechtenstein',
    'MC': 'Monaco', 'SM': 'San Marino', 'VA': 'Vatican City', 'AD': 'Andorra',
    'AL': 'Albania', 'BA': 'Bosnia and Herzegovina', 'ME': 'Montenegro',
    'MK': 'North Macedonia', 'RS': 'Serbia', 'TR': 'Turkey', 'UA': 'Ukraine',
    'BY': 'Belarus', 'MD': 'Moldova', 'GE': 'Georgia', 'AM': 'Armenia',
    'AZ': 'Azerbaijan', 'RU': 'Russia', 'XK': 'Kosovo',
    'US': 'United States', 'CA': 'Canada', 'AU': 'Australia', 'NZ': 'New Zealand',
    'JP': 'Japan', 'KR': 'South Korea', 'IN': 'India', 'CN': 'China',
}


def parse_location(loc_text):
    """Parse 'City, CC' or 'City, Country' into city, country, country_code."""
    loc_text = (loc_text or '').strip()
    city, country, country_code = None, None, None

    # Pattern: "Some City, CC" where CC is 2-letter code
    m = re.match(r'^(.+?),\s*([A-Z]{2})$', loc_text)
    if m:
        city = m.group(1).strip()
        country_code = m.group(2).strip()
        country = COUNTRY_MAP.get(country_code, country_code)
        return city, country, country_code

    # Pattern: "Some City, Country Name"
    m = re.match(r'^(.+?),\s*(.+)$', loc_text)
    if m:
        city = m.group(1).strip()
        country_name = m.group(2).strip()
        # Try to reverse-map
        for cc, cn in COUNTRY_MAP.items():
            if cn.lower() == country_name.lower():
                country = cn
                country_code = cc
                break
        if not country:
            country = country_name
        return city, country, country_code

    if loc_text:
        city = loc_text

    return city, country, country_code


def extract_address(soup):
    """Extract address from sidebar. The Address h3 is followed by text."""
    for h3 in soup.find_all(['h3', 'h4']):
        if h3.get_text(strip=True).lower() == 'address':
            parent = h3.find_parent(['div', 'section', 'aside'])
            if parent:
                parts = []
                for sibling in h3.find_next_siblings():
                    if sibling.name in ['h3', 'h4']:
                        break
                    txt = sibling.get_text(' ', strip=True)
                    if txt and len(txt) > 3:
                        parts.append(txt)
                if parts:
                    return ' '.join(parts)
    return None


def extract_address_v2(soup):
    """Alternative: find Address in sidebar_key/value pairs."""
    # Look for label/value pairs in sidebar
    sidebar = soup.find('div', class_=lambda c: c and 'sidebar' in str(c).lower())
    if not sidebar:
        return None

    for field in sidebar.find_all(['div', 'span', 'p']):
        text = field.get_text(' ', strip=True)
        if text.lower().startswith('address'):
            # Could be "Address: Le bourg 23200, Saint-Avit-de-Tardes France"
            after = text[len('Address'):].lstrip(':').strip()
            if after:
                return after
    return None


def extract_page_data(node_id):
    """Fetch and parse a single Religiana building page."""
    url = f'https://religiana.com/node/{node_id}'
    sess = requests.Session()
    sess.headers.update({'User-Agent': UA})
    try:
        r = sess.get(url, allow_redirects=True, timeout=20)
        if r.status_code != 200:
            return {'religiana_id': node_id, 'error': f'HTTP {r.status_code}'}

        soup = BeautifulSoup(r.text, 'html.parser')
        data = {
            'religiana_id': node_id,
            'religiana_url': r.url,
            'error': None,
        }

        # Name
        h1 = soup.find('h1', class_='article-header-title')
        data['name'] = h1.get_text(strip=True) if h1 else None

        # Building type from body class
        body = soup.find('body')
        btype = None
        if body:
            for cls in body.get('class', []):
                if cls.startswith('page-node-type-'):
                    btype = cls.replace('page-node-type-', '')
        data['building_type'] = btype

        # Location text (first <p> with coordinates-like content)
        data['location_text'] = None
        for p in soup.find_all('p'):
            imgs = p.find_all('img')
            txt = p.get_text(strip=True)
            if imgs and txt and len(txt) < 80:
                data['location_text'] = txt
                break

        # Fallback: any short p near the top that looks like "City, CC"
        if not data['location_text']:
            for p in soup.find_all('p'):
                txt = p.get_text(strip=True)
                if re.match(r'^[A-Za-z].+,\s*[A-Z]{2}$', txt):
                    data['location_text'] = txt
                    break

        # Address from sidebar
        data['address'] = extract_address(soup) or extract_address_v2(soup)

        # Meta description
        meta = soup.find('meta', attrs={'name': 'description'})
        data['description'] = meta.get('content', '').strip() if meta else None

        # First paragraph from article for description fallback
        article = soup.find('article')
        if article:
            first_para = article.find('p')
            if first_para:
                txt = first_para.get_text(strip=True)
                if txt and len(txt) > 20 and not data.get('description'):
                    data['description'] = txt[:500]
                elif txt and len(txt) > 20:
                    data['article_first_para'] = txt[:300]

        return data

    except requests.exceptions.Timeout:
        return {'religiana_id': node_id, 'error': 'timeout'}
    except requests.exceptions.ConnectionError as e:
        return {'religiana_id': node_id, 'error': f'conn_err: {e}'}
    except Exception as e:
        return {'religiana_id': node_id, 'error': str(e)}
    finally:
        sess.close()


def load_checkpoint():
    if os.path.exists(CK_FILE):
        ck = json.load(open(CK_FILE))
        # ensure required keys
        ck.setdefault('processed', 0)
        ck.setdefault('inserted', 0)
        ck.setdefault('errors', 0)
        ck.setdefault('total', 0)
        return ck
    return {'processed': 0, 'inserted': 0, 'errors': 0, 'total': 0}


def save_checkpoint(ck):
    json.dump(ck, open(CK_FILE, 'w'))


def main():
    parser = argparse.ArgumentParser(description='Import Religiana buildings')
    parser.add_argument('--limit', type=int, default=None,
                        help='Limit to N buildings (test mode)')
    parser.add_argument('--workers', type=int, default=20,
                        help='Concurrent HTTP workers')
    parser.add_argument('--restart', action='store_true',
                        help='Ignore checkpoint, start fresh')
    args = parser.parse_args()

    # Load pins
    pins = json.load(open(PINS_FILE))
    print(f'Religiana pins: {len(pins):,}', flush=True)

    if args.limit:
        pins = pins[:args.limit]
        print(f'  (limited to {args.limit})', flush=True)

    # Load or reset checkpoint
    ck = load_checkpoint() if not args.restart else {
        'processed': 0, 'inserted': 0, 'errors': 0, 'total': len(pins)
    }
    ck['total'] = len(pins)

    if ck['processed'] > 0:
        pins = pins[ck['processed']:]
        print(f'Resuming from pin #{ck["processed"]:,} ({len(pins):,} remaining)', flush=True)
        print(f'  Previous: {ck["inserted"]:,} ins, {ck["errors"]:,} err', flush=True)

    start_time = time.time()
    db_inserted = 0
    db_errors = 0
    batch_num = 0

    # Process in batches: fetch N pages in parallel, then insert sequentially
    while pins:
        batch = pins[:BATCH_FETCH]
        pins = pins[BATCH_FETCH:]
        batch_num += 1
        b_start = time.time()

        # Phase 1: Fetch pages in parallel (HTTP only, no DB)
        fetch_results = []
        with ThreadPoolExecutor(max_workers=args.workers) as executor:
            futures = {}
            for pin in batch:
                node_id = int(pin['church_id'])
                future = executor.submit(extract_page_data, node_id)
                futures[future] = pin

            for future in as_completed(futures):
                pin = futures[future]
                result = future.result()
                result['_pin'] = pin
                fetch_results.append(result)

        fetch_time = time.time() - b_start
        fetch_ok = sum(1 for r in fetch_results if not r.get('error'))
        fetch_err = sum(1 for r in fetch_results if r.get('error'))

        # Phase 2: Insert into DB (sequential, single connection)
        inserted_here = 0
        errors_here = 0

        # Open a fresh raw connection for each insert batch
        conn = sqlite3.connect(DB_PATH, timeout=60)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA busy_timeout=60000")
        conn.execute("PRAGMA synchronous=OFF")
        c = conn.cursor()

        # Ensure church_sources table
        c.execute("""
            CREATE TABLE IF NOT EXISTS church_sources (
                church_id INTEGER, source_name TEXT, source_url TEXT, notes TEXT,
                PRIMARY KEY (church_id, source_name)
            )
        """)

        # Find max existing ID
        max_id = c.execute("SELECT COALESCE(MAX(id), 800000) FROM churches").fetchone()[0]

        for i, result in enumerate(fetch_results):
            pin = result['_pin']
            ck['processed'] += 1

            if result.get('error'):
                errors_here += 1
                db_errors += 1
                ck['errors'] += 1
                continue

            city, country, country_code = parse_location(result.get('location_text'))

            max_id += 1
            try:
                c.execute("""
                    INSERT INTO churches
                        (id, name, address, city, country, latitude, longitude,
                         source, landmark_type)
                    VALUES (?, ?, ?, ?, ?, ?, ?, 'religiana', ?)
                """, (
                    max_id,
                    result.get('name'),
                    result.get('address'),
                    city,
                    country or country_code,
                    float(pin['lat']) if pin.get('lat') else None,
                    float(pin['lng']) if pin.get('lng') else None,
                    None,
                ))

                c.execute("""
                    INSERT OR IGNORE INTO church_sources
                        (church_id, source_name, source_url, notes)
                    VALUES (?, 'religiana', ?, ?)
                """, (max_id, result.get('religiana_url', ''),
                      f'Religiana building #{result["religiana_id"]}'))

                inserted_here += 1
                db_inserted += 1
                ck['inserted'] += 1

            except Exception as e:
                errors_here += 1
                db_errors += 1
                ck['errors'] += 1
                max_id -= 1
                if db_errors <= 5:
                    print(f'  DB err ID={result["religiana_id"]}: {e}', flush=True)

        conn.commit()
        conn.close()

        # Update checkpoint
        save_checkpoint(ck)

        elapsed = time.time() - start_time
        rate = ck['processed'] / elapsed if elapsed > 0 else 0
        pct = ck['processed'] / ck['total'] * 100
        fetch_rate = len(batch) / fetch_time if fetch_time > 0 else 0

        print(f'  Batch {batch_num}: {len(batch):,} fetched in {fetch_time:.0f}s ({fetch_rate:.0f}/s) '
              f'| +{inserted_here} ins, {errors_here} err '
              f'| Total: {ck["inserted"]:,}/{ck["processed"]:,} ({pct:.1f}%) @ {rate:.0f}/s',
              flush=True)

    # Done — log provenance
    conn = sqlite3.connect(DB_PATH, timeout=60)
    with Provenance(conn, 'import_religiana.py', source='religiana',
                    action='inserted',
                    fields='name,address,city,country,latitude,longitude,source'):
        pass  # Provenance logs on exit

    elapsed = time.time() - start_time
    print(f'\n=== Done ===', flush=True)
    print(f'  Processed: {ck["processed"]:,}', flush=True)
    print(f'  Inserted:  {ck["inserted"]:,}', flush=True)
    print(f'  Errors:    {ck["errors"]:,}', flush=True)
    print(f'  Time:      {elapsed:.0f}s ({ck["processed"]/elapsed:.0f}/s)', flush=True)


if __name__ == '__main__':
    main()
