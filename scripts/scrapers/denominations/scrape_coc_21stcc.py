"""
Scrape Churches of Christ from 21stcc.com database.
Each worker gets its OWN browser (thread-safe).
IDs 2-12475 are valid (~12,474 churches).
"""
import json, os, time
from playwright.sync_api import sync_playwright
import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT = os.path.join(SCRIPT_DIR, '..', '..', 'data', 'coc_churches.jsonl')

STATE_MAP = {
    'ALABAMA': 'AL', 'ALASKA': 'AK', 'ARIZONA': 'AZ', 'ARKANSAS': 'AR',
    'CALIFORNIA': 'CA', 'COLORADO': 'CO', 'CONNECTICUT': 'CT', 'DELAWARE': 'DE',
    'FLORIDA': 'FL', 'GEORGIA': 'GA', 'HAWAII': 'HI', 'IDAHO': 'ID',
    'ILLINOIS': 'IL', 'INDIANA': 'IN', 'IOWA': 'IA', 'KANSAS': 'KS',
    'KENTUCKY': 'KY', 'LOUISIANA': 'LA', 'MAINE': 'ME', 'MARYLAND': 'MD',
    'MASSACHUSETTS': 'MA', 'MICHIGAN': 'MI', 'MINNESOTA': 'MN', 'MISSISSIPPI': 'MS',
    'MISSOURI': 'MO', 'MONTANA': 'MT', 'NEBRASKA': 'NE', 'NEVADA': 'NV',
    'NEW HAMPSHIRE': 'NH', 'NEW JERSEY': 'NJ', 'NEW MEXICO': 'NM', 'NEW YORK': 'NY',
    'NORTH CAROLINA': 'NC', 'NORTH DAKOTA': 'ND', 'OHIO': 'OH', 'OKLAHOMA': 'OK',
    'OREGON': 'OR', 'PENNSYLVANIA': 'PA', 'PUERTO RICO': 'PR', 'RHODE ISLAND': 'RI',
    'SOUTH CAROLINA': 'SC', 'SOUTH DAKOTA': 'SD', 'TENNESSEE': 'TN', 'TEXAS': 'TX',
    'UTAH': 'UT', 'VERMONT': 'VT', 'VIRGIN ISLANDS': 'VI', 'VIRGINIA': 'VA',
    'WASHINGTON': 'WA', 'WEST VIRGINIA': 'WV', 'WISCONSIN': 'WI', 'WYOMING': 'WY',
    'AMERICAN SAMOA': 'AS', 'GUAM': 'GU', 'NORTHERN MARIANAS': 'MP',
    'DISTRICT OF COLUMBIA': 'DC',
}


def scrape_worker(id_list):
    """Scrape a list of IDs using its own Playwright browser."""
    results = []
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        page = browser.new_page()
        for cid in id_list:
            try:
                url = 'https://www.21stcc.com/dbinterface/dbinterface/public/search/details/{}'.format(cid)
                page.goto(url, wait_until='domcontentloaded', timeout=15000)
                page.wait_for_timeout(500)
                data = page.evaluate("""() => {
                    const r = {};
                    document.querySelectorAll('input').forEach(inp => {
                        const n = inp.name;
                        if (n && n !== '_token' && n !== 'churchesId' && n !== 'saveChanges' && inp.value) r[n] = inp.value;
                    });
                    document.querySelectorAll('select').forEach(sel => {
                        const n = sel.name || sel.id;
                        if (!n) return;
                        const opt = sel.options[sel.selectedIndex];
                        if (opt && opt.text && opt.text !== 'Select a state...' && opt.text !== n) r[n] = opt.text;
                    });
                    return r;
                }""")
                name = data.get('printName', '')
                if name and 'error' not in page.title().lower():
                    sf = (data.get('state', '') or '').strip().upper()
                    results.append({
                        'source_id': cid, 'name': name,
                        'address': data.get('locationAddress', ''),
                        'city': data.get('city', ''),
                        'state': STATE_MAP.get(sf, sf[:2]),
                        'zip': data.get('zip', ''),
                        'phone': data.get('telephone', ''),
                        'email': data.get('email', ''),
                        'website': data.get('website', ''),
                        'attendance': int(data.get('attedance', 0) or 0),
                        'members': int(data.get('members', 0) or 0),
                        'established_year': int(data.get('EstablishedYear', 0) or 0),
                    })
            except:
                pass
        browser.close()
    return results


def import_to_db(jsonl_path, db_path='churches.db'):
    import sqlite3
    db = sqlite3.connect(db_path)
    cur = db.cursor()
    cur.execute("SELECT name, city, state FROM churches WHERE LOWER(denomination) LIKE '%church of christ%' OR LOWER(family) LIKE '%church of christ%'")
    existing = set()
    for r in cur.fetchall():
        existing.add(((r[0] or '').strip().upper(), (r[1] or '').strip().upper(), (r[2] or '').strip().upper()))
    imported = 0
    matched = 0
    with open(jsonl_path) as f:
        for line in f:
            r = json.loads(line)
            key = (r['name'].upper(), r['city'].upper(), r['state'].upper())
            if key in existing:
                matched += 1
                continue
            cur.execute("""
                INSERT INTO churches (name, denomination, family, address, city, state, zip,
                    phone, email, website, attendance_arda, members_arda,
                    source, org_type, faith_tradition, classification_source, denom_subgroup)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (r['name'], 'Churches of Christ', 'Churches of Christ',
                  r['address'], r['city'], r['state'], r['zip'],
                  r['phone'], r['email'], r['website'],
                  r['attendance'], r['members'],
                  'coc_21stcc', 'church', 'christian', 'denomination_scrape', '21stcc_database'))
            imported += 1
    db.commit()
    print('Import: {} new, {} matched'.format(imported, matched))
    db.close()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--start', type=int, default=2)
    parser.add_argument('--end', type=int, default=12475)
    parser.add_argument('--workers', type=int, default=4, help='Browser instances')
    parser.add_argument('--import', dest='do_import', action='store_true')
    args = parser.parse_args()

    os.makedirs(os.path.dirname(OUTPUT), exist_ok=True)
    ids = list(range(args.start, args.end + 1))
    bs = (len(ids) + args.workers - 1) // args.workers
    batches = [ids[i:i+bs] for i in range(0, len(ids), bs)]
    print('CoC Scraper: {} IDs, {} workers'.format(len(ids), args.workers))
    t0 = time.time()

    all_results = []
    with ThreadPoolExecutor(max_workers=args.workers) as executor:
        futures = {executor.submit(scrape_worker, b): b for b in batches}
        done = 0
        for f in as_completed(futures):
            try:
                all_results.extend(f.result())
            except:
                pass
            done += 1
            print('  Worker {}/{} done ({} records, {:.0f}s)'.format(done, len(batches), len(all_results), time.time()-t0))

    all_results.sort(key=lambda r: r['source_id'])
    with open(OUTPUT, 'w', encoding='utf-8') as f:
        for r in all_results:
            f.write(json.dumps(r) + '\n')

    elapsed = time.time() - t0
    print('\nDone in {:.0f}s: {} records'.format(elapsed, len(all_results)))
    sc = {}
    for r in all_results:
        sc[r['state']] = sc.get(r['state'], 0) + 1
    print('Top states:')
    for st, cnt in sorted(sc.items(), key=lambda x: -x[1])[:10]:
        print('  {}: {}'.format(st, cnt))

    if args.do_import:
        print('Importing...')
        import_to_db(OUTPUT)

if __name__ == '__main__':
    main()
