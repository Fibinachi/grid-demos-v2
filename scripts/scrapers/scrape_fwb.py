"""
Scrape Free Will Baptist Church directory - NAFWB.
Source: https://directory.nafwb.org/
Uses HTML scraping with concurrent workers for speed.
Supports --import for direct DB ingestion.
"""
import urllib.request, re, time, os, csv
from concurrent.futures import ThreadPoolExecutor, as_completed
import sqlite3
import argparse

UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'

def fetch(url, retries=2):
    for i in range(retries):
        try:
            req = urllib.request.Request(url, headers={'User-Agent': UA})
            return urllib.request.urlopen(req, timeout=15).read().decode('utf-8', 'replace')
        except Exception:
            if i < retries - 1:
                time.sleep(1)
            else:
                return None

def find_listing_urls_fast():
    """Binary search for last page, then collect all listing URLs concurrently."""
    def check_page(p):
        url = 'https://directory.nafwb.org/' if p == 1 else 'https://directory.nafwb.org/page/{}/'.format(p)
        html = fetch(url)
        if html:
            links = re.findall(r'href="(https://directory\.nafwb\.org/\d+/[^"]+)"', html)
            return (p, links) if links else (p, [])
        return (p, [])

    # Binary search for last page
    low, high = 1, 300
    while low < high:
        mid = (low + high + 1) // 2
        _, links = check_page(mid)
        if links:
            low = mid
        else:
            high = mid - 1
    last_page = low
    print('Pages: 1..{}'.format(last_page))

    # Collect all URLs concurrently
    all_urls = []
    seen = set()
    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = {executor.submit(check_page, p): p for p in range(1, last_page + 1)}
        for f in as_completed(futures):
            try:
                _, links = f.result()
                for link in links:
                    clean = link.split('#')[0]
                    if clean not in seen:
                        seen.add(clean)
                        all_urls.append(clean)
            except:
                pass
    print('Total listing URLs: {}'.format(len(all_urls)))
    return all_urls


def scrape_detail(url):
    """Scrape a single church listing page."""
    html = fetch(url)
    if not html:
        return None
    data = {'url': url}
    # Name from schema.org itemprop or title
    m = re.search(r'itemprop="name"[^>]*>([^<]+)<', html)
    if m:
        data['name'] = m.group(1).strip()
    if 'name' not in data:
        m = re.search(r'<title>([^<]+)</title>', html)
        if m and 'not found' not in m.group(1).lower():
            title = m.group(1)
            # Remove trailing site name
            title = re.sub(r'\s*[-–|]\s*NAFWB.*$', '', title).strip()
            data['name'] = title
    # Address
    m = re.search(r'<address[^>]*>([^<]+)</address>', html)
    if m:
        data['address'] = m.group(1).strip()
    # w2dc fields: street, city, state, phone, pastor
    fields = re.findall(r'<span[^>]*class="[^"]*w2dc-field-content[^"]*"[^>]*>([\s\S]*?)</span>', html)
    field_texts = [re.sub(r'<[^>]+>', '', f).strip() for f in fields if re.sub(r'<[^>]+>', '', f).strip()]
    if len(field_texts) >= 1:
        data['street'] = field_texts[0]
    if len(field_texts) >= 2:
        data['city'] = field_texts[1]
    if len(field_texts) >= 3:
        data['state_full'] = field_texts[2]
    if len(field_texts) >= 4:
        phone_raw = field_texts[3]
        # Decode HTML entities like &#49; -> 1
        phone_raw = re.sub(r'&#(\d+);', lambda m: chr(int(m.group(1))), phone_raw)
        digits = re.sub(r'[^\d]', '', phone_raw)
        if len(digits) >= 7:
            data['phone'] = digits
    if len(field_texts) >= 5:
        data['pastor'] = field_texts[4]
    # Phone from tel: links
    if 'phone' not in data:
        tel_links = re.findall(r'tel:([^\'"<]+)', html)
        if tel_links:
            data['phone'] = tel_links[0].strip()
    # Association
    m = re.search(r'Association:</span>[\s\S]*?<span[^>]*>([^<]+)</span>', html)
    if m:
        data['association'] = m.group(1).strip()
    # Website
    site_links = re.findall(r'<a[^>]*href="(https?://[^"]+)"[^>]*>View Our Site', html)
    if site_links:
        data['website'] = site_links[0]
    if 'website' not in data:
        ext_links = re.findall(r'<a[^>]*href="(https?://[^"]+)"[^>]*target="_blank"', html)
        for ln in ext_links:
            if 'directory.nafwb.org' not in ln and 'facebook.com' not in ln.lower():
                data['website'] = ln
                break
    # Coordinates from JS
    coord_m = re.findall(r'new w2dc_map_markers_attrs\([^,]+,\s*eval\(\[\["(\d+)","([\d\.\-]+)","([\d\.\-]+)"', html)
    if coord_m:
        data['latitude'] = coord_m[0][1]
        data['longitude'] = coord_m[0][2]
    return data if data.get('name') else None


STATE_MAP = {
    'alabama': 'AL', 'alaska': 'AK', 'arizona': 'AZ', 'arkansas': 'AR',
    'california': 'CA', 'colorado': 'CO', 'connecticut': 'CT', 'delaware': 'DE',
    'florida': 'FL', 'georgia': 'GA', 'hawaii': 'HI', 'idaho': 'ID',
    'illinois': 'IL', 'indiana': 'IN', 'iowa': 'IA', 'kansas': 'KS',
    'kentucky': 'KY', 'louisiana': 'LA', 'maine': 'ME', 'maryland': 'MD',
    'massachusetts': 'MA', 'michigan': 'MI', 'minnesota': 'MN', 'mississippi': 'MS',
    'missouri': 'MO', 'montana': 'MT', 'nebraska': 'NE', 'nevada': 'NV',
    'new hampshire': 'NH', 'new jersey': 'NJ', 'new mexico': 'NM', 'new york': 'NY',
    'north carolina': 'NC', 'north dakota': 'ND', 'ohio': 'OH', 'oklahoma': 'OK',
    'oregon': 'OR', 'pennsylvania': 'PA', 'rhode island': 'RI', 'south carolina': 'SC',
    'south dakota': 'SD', 'tennessee': 'TN', 'texas': 'TX', 'utah': 'UT',
    'vermont': 'VT', 'virginia': 'VA', 'washington': 'WA', 'west virginia': 'WV',
    'wisconsin': 'WI', 'wyoming': 'WY', 'district of columbia': 'DC',
}

def parse_state(state_full):
    if not state_full:
        return ''
    s = state_full.strip().lower()
    if len(s) == 2:
        return s.upper()
    return STATE_MAP.get(s, s.upper()[:2])

def parse_zip(address):
    m = re.search(r'(\d{5})(?:[-\s](\d{4}))?', address or '')
    return (m.group(1) + ('-' + m.group(2) if m.group(2) else '')) if m else ''

def import_to_db(results, db_path='churches.db'):
    import time
    for attempt in range(5):
        try:
            db = sqlite3.connect(db_path, timeout=30)
            cur = db.cursor()
            break
        except Exception as e:
            if attempt < 4:
                time.sleep(3)
            else:
                print('ERROR: Could not connect to DB after 5 attempts:', e)
                return
    # Build set of existing FWB records
    cur.execute("SELECT name, city, state FROM churches WHERE LOWER(denomination) LIKE '%free will%' OR LOWER(family) LIKE '%free will%'")
    existing = set()
    for r in cur.fetchall():
        existing.add((r[0].strip().upper() if r[0] else '', (r[1] or '').strip().upper(), (r[2] or '').strip().upper()))
    imported = 0
    matched = 0
    for r in results:
        name = (r.get('name') or '').strip()
        city = (r.get('city') or '').strip()
        state = parse_state(r.get('state_full', ''))
        street = (r.get('street') or r.get('address') or '').strip()
        phone = r.get('phone', '')
        website = r.get('website', '')
        pastor = r.get('pastor', '')
        lat = r.get('latitude')
        lng = r.get('longitude')
        zip_code = parse_zip(r.get('address', ''))
        if not name:
            continue
        key = (name.upper(), city.upper(), state.upper())
        if key in existing:
            matched += 1
            continue
        cur.execute("""
            INSERT INTO churches (
                name, denomination, family, address, city, state, zip,
                phone, website, pastor_name, latitude, longitude,
                source, org_type, faith_tradition, classification_source,
                geocode_source, denom_subgroup
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            name, 'National Association of Free Will Baptists', 'Free Will Baptist',
            street, city, state, zip_code,
            phone, website, pastor, lat, lng,
            'fwb_scraper', 'church', 'christian', 'denomination_scrape',
            'directory_listing' if lat else None, 'nafwb'
        ))
        imported += 1
    db.commit()
    # Update existing contacts records
    cur.execute("""
        UPDATE churches SET denomination = 'National Association of Free Will Baptists',
                            family = 'Free Will Baptist'
        WHERE LOWER(denomination) LIKE '%free will%'
          AND (denomination IS NULL OR denomination = '' OR denomination = 'Free Will Baptist')
    """)
    db.commit()
    print('\nImport: {} new, {} matched existing, total results {}'.format(imported, matched, len(results)))
    print('Updated existing records: {}'.format(cur.rowcount))
    db.close()


def main():
    parser = argparse.ArgumentParser(description='Scrape NAFWB Free Will Baptist directory')
    parser.add_argument('--import', dest='do_import', action='store_true', help='Import into DB')
    parser.add_argument('--workers', type=int, default=10, help='Concurrent workers (default: 10)')
    parser.add_argument('--urls-only', action='store_true', help='Only discover URLs')
    args = parser.parse_args()

    print('='*60)
    print('Free Will Baptist Church Directory Scraper')
    print('Source: https://directory.nafwb.org/')
    print('='*60)

    print('\nStep 1: Discovering listing URLs...')
    urls = find_listing_urls_fast()
    if args.urls_only or not urls:
        return

    print('\nStep 2: Scraping details ({} workers)...'.format(args.workers))
    results = []
    done = 0
    with ThreadPoolExecutor(max_workers=args.workers) as executor:
        futures = {executor.submit(scrape_detail, url): url for url in urls}
        for f in as_completed(futures):
            done += 1
            try:
                data = f.result()
                if data:
                    results.append(data)
            except Exception:
                pass
            if done % 100 == 0 or done == len(urls):
                print('  {}/{} done, {} valid'.format(done, len(urls), len(results)))

    print('\nDone: {} valid results from {} URLs'.format(len(results), len(urls)))

    # State distribution
    state_counts = {}
    for r in results:
        st = parse_state(r.get('state_full', ''))
        state_counts[st] = state_counts.get(st, 0) + 1
    print('\n=== State Distribution (top 15) ===')
    for st, cnt in sorted(state_counts.items(), key=lambda x: -x[1])[:15]:
        print('  {}: {}'.format(st, cnt))
    print('  ({} total states)'.format(len(state_counts)))

    if args.do_import:
        print('\nStep 3: Importing to database...')
        import_to_db(results)
    else:
        print('\nUse --import to import into DB. Sample:')
        for r in results[:5]:
            print('  {} | {}, {} | {} | {}'.format(
                (r.get('name') or '')[:40], (r.get('city') or '')[:15],
                parse_state(r.get('state_full', '')),
                r.get('phone', '') or 'no phone',
                r.get('website', '')[:30] if r.get('website') else 'no site'
            ))


if __name__ == '__main__':
    main()
