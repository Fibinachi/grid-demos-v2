#!/usr/bin/env python3
"""
Christian Science Directory Scraper (Playwright)
=================================================
Scrapes directory.christianscience.com for all US branch churches,
societies, and groups. Data is JS-rendered so we use Playwright.

Strategy: Search by each US state with 500mi radius.
Extracts: name, address, phone, email, org type.

Usage:
    python scripts/scrapers/scrape_cs_directory.py --dry-run --limit 3
    python scripts/scrapers/scrape_cs_directory.py --import
"""
import argparse
import re
import sqlite3
import os
import time

PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DB_PATH = os.path.join(PROJECT_DIR, 'churches.db')

US_STATES = [
    "Alabama", "Alaska", "Arizona", "Arkansas", "California",
    "Colorado", "Connecticut", "Delaware", "Florida", "Georgia",
    "Hawaii", "Idaho", "Illinois", "Indiana", "Iowa",
    "Kansas", "Kentucky", "Louisiana", "Maine", "Maryland",
    "Massachusetts", "Michigan", "Minnesota", "Mississippi", "Missouri",
    "Montana", "Nebraska", "Nevada", "New Hampshire", "New Jersey",
    "New Mexico", "New York", "North Carolina", "North Dakota", "Ohio",
    "Oklahoma", "Oregon", "Pennsylvania", "Rhode Island", "South Carolina",
    "South Dakota", "Tennessee", "Texas", "Utah", "Vermont",
    "Virginia", "Washington", "West Virginia", "Wisconsin", "Wyoming",
]

SEARCH_URL = "https://directory.christianscience.com/search_results"


def parse_results(text):
    """Parse search results text into structured records."""
    records = []
    
    # Split by distance markers
    blocks = re.split(r'\d+\.?\d*\s*mi\.\s*\(\d+\.?\d*\s*km\.\)', text)
    
    for block in blocks:
        block = block.strip()
        if not block:
            continue
        
        lines = [l.strip() for l in block.split('\n') if l.strip()]
        if len(lines) < 2:
            continue
        
        org_type = lines[0]
        name = lines[1] if len(lines) > 1 else ''
        
        # Must be a church/society/group
        if 'Churches' not in org_type and 'Society' not in org_type:
            continue
        if not name:
            continue
        
        phone = ''
        email = ''
        city, state = '', ''
        
        for l in lines:
            ph = re.match(r'(\d{3}[-.]?\d{3}[-.]?\d{4})', l)
            if ph:
                phone = ph.group(1)
            em = re.match(r'([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})', l)
            if em:
                email = em.group(1)
            addr_match = re.match(r'^([A-Za-z\s.,\-]+),\s*([A-Z]{2})(?:,\s*United\s*States)?$', l)
            if addr_match:
                city = addr_match.group(1).strip()
                state = addr_match.group(2).strip()
        
        records.append({
            'name': name, 'city': city, 'state': state,
            'phone': phone, 'email': email, 'type': org_type,
        })
    
    return records


def scrape():
    """Main scrape loop using Playwright."""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("Need Playwright. Run: pip install playwright && playwright install chromium")
        return []
    
    all_records = []
    seen_keys = set()
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        
        for i, state in enumerate(US_STATES):
            page = browser.new_page()
            url = f"{SEARCH_URL}?keyword=&location={state.replace(' ', '+')}&rt-csg=1&sort=distance&dr=500"
            
            print(f"  [{i+1:2d}/{len(US_STATES)}] {state:20s}...", end=' ', flush=True)
            
            try:
                page.goto(url, wait_until='domcontentloaded', timeout=20000)
                page.wait_for_timeout(8000)
                
                body = page.evaluate("() => document.body.innerText")
                count_m = re.search(r'of\s+([0-9,]+)\s+results', body)
                total = count_m.group(1) if count_m else '?'
                
                records = parse_results(body)
                new_recs = []
                for r in records:
                    key = (r['name'], r['city'], r['state'])
                    if key not in seen_keys and key[0]:
                        seen_keys.add(key)
                        new_recs.append(r)
                
                all_records.extend(new_recs)
                print(f"{total} results, {len(new_recs)} new")
                
            except Exception as e:
                print(f"ERROR: {e}")
            
            page.close()
            time.sleep(1.5)
        
        browser.close()
    
    return all_records


def ensure_columns(db):
    existing = {r[1] for r in db.execute('PRAGMA table_info(churches)').fetchall()}
    for col, dtype in [
        ('cs_church_name', 'TEXT'),
        ('cs_has_email', 'INTEGER'),
        ('cs_has_phone', 'INTEGER'),
    ]:
        if col not in existing:
            db.execute(f'ALTER TABLE churches ADD COLUMN {col} {dtype}')


def main():
    parser = argparse.ArgumentParser(description='Christian Science Directory Scraper')
    parser.add_argument('--dry-run', action='store_true')
    parser.add_argument('--import', dest='do_import', action='store_true')
    parser.add_argument('--limit', type=int, default=0)
    args = parser.parse_args()
    
    print('=== Christian Science Directory Scraper ===')
    print()
    
    records = scrape()
    
    print(f'\nTotal unique records: {len(records):,}')
    print(f'  With email: {sum(1 for r in records if r["email"]):,}')
    print(f'  With phone: {sum(1 for r in records if r["phone"]):,}')
    
    state_counts = {}
    for r in records:
        s = r['state'] or '??'
        state_counts[s] = state_counts.get(s, 0) + 1
    print(f'\nTop states:')
    for s, c in sorted(state_counts.items(), key=lambda x: -x[1])[:10]:
        print(f'  {s:5s} {c:>5,}')
    
    print(f'\nFirst 10:')
    for r in records[:10]:
        parts = [r['name']]
        if r['city']: parts.append(r['city'])
        if r['state']: parts.append(r['state'])
        if r['phone']: parts.append(f"p:{r['phone']}")
        if r['email']: parts.append(f"e:{r['email']}")
        print(f'  {" | ".join(parts)}')
    
    if args.do_import:
        db = sqlite3.connect(DB_PATH, timeout=60)
        ensure_columns(db)
        matched, imported = 0, 0
        
        for r in records:
            ex = db.execute("SELECT id, email, phone FROM churches WHERE LOWER(name)=LOWER(?) AND LOWER(city)=LOWER(?) AND state=?", 
                          (r['name'], r['city'] or '', r['state'] or '')).fetchone()
            if ex:
                updates = []
                params = []
                if r['email'] and not ex[1]:
                    updates.append("email = ?")
                    params.append(r['email'])
                if r['phone'] and not ex[2]:
                    updates.append("phone = ?")
                    params.append(r['phone'])
                updates.append("cs_church_name = ?")
                params.append(r['name'])
                updates.append("cs_has_email = ?")
                params.append(1 if r['email'] else 0)
                updates.append("cs_has_phone = ?")
                params.append(1 if r['phone'] else 0)
                updates.append("last_updated = datetime('now')")
                params.append(ex[0])
                if updates:
                    db.execute(f"UPDATE churches SET {', '.join(updates)} WHERE id = ?", params)
                matched += 1
            else:
                db.execute("INSERT INTO churches (name,city,state,phone,email,faith_tradition,source,cs_church_name,cs_has_email,cs_has_phone,created_at,last_updated) VALUES (?,?,?,?,?,'other','cs_directory',?,?,?,datetime('now'),datetime('now'))",
                         (r['name'], r['city'], r['state'], r['phone'], r['email'], r['name'], 1 if r['email'] else 0, 1 if r['phone'] else 0))
                imported += 1
        
        db.commit()
        print(f'\nImported: {matched} matched, {imported} new = {matched+imported} total')
        db.close()
    
    print('\nDone!')


if __name__ == '__main__':
    main()
