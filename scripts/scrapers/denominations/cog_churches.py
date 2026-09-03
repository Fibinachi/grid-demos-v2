#!/usr/bin/env python3
"""
Church of God (Cleveland, TN) Church Directory Scraper
=======================================================
Scrapes churchofgod.org/church_locator/churches.php for all US churches.
Data: Name, Address, Pastor, Phone, Website, Email
~4,358 expected records across all states.

Usage:
    python scripts/scrapers/scrape_cog.py --dry-run
    python scripts/scrapers/scrape_cog.py --states SC,GA,NC
    python scripts/scrapers/scrape_cog.py --all
    python scripts/scrapers/scrape_cog.py --all --import
"""
import argparse, csv, os, re, sqlite3, time, urllib.request
from datetime import datetime

PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DB_PATH = os.path.join(PROJECT_DIR, 'churches.db')
OUTPUT = os.path.join(PROJECT_DIR, 'data', 'cog_churches.csv')
UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
BASE = 'https://churchofgod.org/church_locator/churches.php'

# All US states + DC
STATES = ['AL','AK','AZ','AR','CA','CO','CT','DE','DC','FL','GA','HI','ID','IL',
          'IN','IA','KS','KY','LA','ME','MD','MA','MI','MN','MS','MO','MT','NE',
          'NV','NH','NJ','NM','NY','NC','ND','OH','OK','OR','PA','RI','SC','SD',
          'TN','TX','UT','VT','VA','WA','WV','WI','WY']


def scrape_state(state, limit=0):
    """Scrape all churches in a state. Returns list of dicts."""
    churches = []
    position = 0
    per_page = 10
    max_retries = 3
    
    while True:
        url = f'{BASE}?int_cur_position={position}&mode=citystate_search&searchtext=&state={state}'
        
        html = None
        for attempt in range(max_retries):
            try:
                req = urllib.request.Request(url, headers={'User-Agent': UA})
                with urllib.request.urlopen(req, timeout=20) as resp:
                    html = resp.read().decode('iso-8859-1', 'replace')
                break
            except Exception as e:
                if attempt < max_retries - 1:
                    time.sleep(2)
                else:
                    print(f'    Request failed at pos {position}: {e}')
                    # Return what we have so far
                    return churches
        
        if html is None:
            return churches
        
        # Parse churches from this page
        blocks = html.split('<TD><p><B>')[1:]
        
        if not blocks:
            # No more churches found
            break
        
        for block in blocks:
            church = {'state': state}
            
            name_end = block.find('</B>')
            name_raw = block[:name_end].strip()
            
            if ',' in name_raw:
                parts = name_raw.split(',', 1)
                church['city'] = parts[0].strip()
                church['name'] = parts[1].strip()
            else:
                church['name'] = name_raw
                church['city'] = ''
            
            pastor_match = re.search(r'Pastor:\s*(.*?)(?:</p></TD>|</TD>)', block)
            church['pastor'] = pastor_match.group(1).strip() if pastor_match else ''
            
            addr_rows = re.findall(r'<TD><p>((?!Phone:|Pastor:|Church Web Site:|Church Email:)[^<]+)</p></TD>', block)
            address_parts = []
            for a in addr_rows:
                a = a.strip()
                if a and not a.startswith('Phone') and not a.startswith('<BR>Pastor'):
                    address_parts.append(a)
            church['address'] = '; '.join(address_parts)
            
            phone_match = re.search(r'Phone:\s*\(?([\d\s\-)]+)\)?', block)
            phone = phone_match.group(1).strip() if phone_match else ''
            phone = phone.strip(')').strip()
            church['phone'] = phone
            
            web_match = re.search(r'Church Web Site:\s*(?:None|<A href="([^"]*)")', block)
            church['website'] = web_match.group(1).strip() if web_match and web_match.group(1) else ''
            
            email_match = re.search(r'Mailto:([^"]+)', block)
            church['email'] = email_match.group(1).strip() if email_match else ''
            
            churches.append(church)
        
        # Check for "Results X to Y of Z" to determine if done
        results_match = re.search(r'Results\s+(\d+)\s+to\s+(\d+)\s+of\s+(\d+)', html)
        if results_match:
            shown_to = int(results_match.group(2))
            total = int(results_match.group(3))
            if shown_to >= total:
                break
        else:
            # No results line means no more pages or no data
            break
        
        position += per_page
        if limit and len(churches) >= limit:
            break
        
        time.sleep(0.3)  # Be polite
    
    return churches


def main():
    parser = argparse.ArgumentParser(description='COG Church Scraper')
    parser.add_argument('--dry-run', action='store_true')
    parser.add_argument('--all', action='store_true')
    parser.add_argument('--states', help='Comma-separated state codes')
    parser.add_argument('--limit', type=int, default=0, help='Per state limit')
    parser.add_argument('--import', dest='do_import', action='store_true')
    args = parser.parse_args()
    
    if args.states:
        state_list = [s.strip().upper() for s in args.states.split(',')]
    elif args.all:
        state_list = STATES
    else:
        state_list = STATES[:3]  # Default: first 3 states
    
    print(f'Scraping {len(state_list)} states for COG churches...')
    
    all_churches = []
    for state in state_list:
        print(f'  {state}...', end=' ', flush=True)
        try:
            churches = scrape_state(state, args.limit)
            print(f'{len(churches):,} churches')
            all_churches.extend(churches)
            # Incremental save
            os.makedirs(os.path.dirname(OUTPUT), exist_ok=True)
            with open(OUTPUT, 'w', newline='', encoding='utf-8') as f:
                w = csv.DictWriter(f, fieldnames=['name','address','city','state','pastor','phone','website','email'])
                w.writeheader()
                w.writerows(all_churches)
        except Exception as e:
            print(f'ERROR: {e}')
    
    print(f'\nTotal churches scraped: {len(all_churches):,}')
    
    if args.dry_run:
        for c in all_churches[:10]:
            print(f'  {c["name"][:40]:40s} | {c["city"]:18s} {c["state"]:3s} | {c["pastor"][:20]:20s} | {c["phone"]:15s}')
        print(f'  ... {len(all_churches) - 10} more')
        return
    
    # Save CSV
    os.makedirs(os.path.dirname(OUTPUT), exist_ok=True)
    with open(OUTPUT, 'w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=['name','address','city','state','pastor','phone','website','email'])
        w.writeheader()
        w.writerows(all_churches)
    print(f'Saved to {OUTPUT}')
    
    # Import to DB
    if args.do_import:
        db = sqlite3.connect(DB_PATH, timeout=60)
        matched, inserted = 0, 0
        for c in all_churches:
            existing = db.execute("""
                SELECT id FROM churches
                WHERE LOWER(name) = LOWER(?) AND LOWER(city) = LOWER(?) AND state = ?
                LIMIT 1
            """, (c['name'], c['city'], c['state'])).fetchone()
            
            if existing:
                db.execute("""UPDATE churches SET
                    denomination = COALESCE(NULLIF(denomination,''), 'Church of God (Cleveland, TN)'),
                    family = COALESCE(NULLIF(family,''), 'Church of God (Cleveland, TN)'),
                    website = CASE WHEN website = '' OR website IS NULL THEN ? ELSE website END,
                    phone = CASE WHEN phone = '' OR phone IS NULL THEN ? ELSE phone END,
                    last_updated = datetime('now')
                    WHERE id = ?""", (c.get('website',''), c.get('phone',''), existing[0]))
                matched += 1
            else:
                db.execute("""INSERT INTO churches
                    (name, address, city, state, faith_tradition, family, denomination,
                     pastor_name, phone, website, source, last_updated)
                    VALUES (?,?,?,?,'christian','Church of God (Cleveland, TN)','Church of God (Cleveland, TN)',
                            ?,?,?,'cog_scraper',datetime('now'))""",
                    (c['name'], c['address'], c['city'], c['state'],
                     c.get('pastor',''), c.get('phone',''), c.get('website','')))
                inserted += 1
        
        db.commit()
        print(f'Import: {matched} matched, {inserted} new records')
        db.close()


if __name__ == '__main__':
    main()
