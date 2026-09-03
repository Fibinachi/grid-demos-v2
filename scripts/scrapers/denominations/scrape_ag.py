#!/usr/bin/env python3
"""
Assemblies of God Church Directory Scraper
===========================================
Scrapes all AG churches from ag.org directory.
URL: https://ag.org/Resources/Directories/Church-Directory?D={n}&page={p}

Usage:
    python scripts/scrapers/denominations/scrape_ag.py
    python scripts/scrapers/denominations/scrape_ag.py --limit=5
    python scripts/scrapers/denominations/scrape_ag.py --resume
"""

import csv, json, re, sys, time
from pathlib import Path

PROJECT_DIR = Path(r"E:\grid")
DATA_DIR = PROJECT_DIR / "data"
OUTPUT_CSV = DATA_DIR / "ag_churches.csv"
STATE_FILE = DATA_DIR / "ag_scraper_state.json"


def extract_churches(text):
    """Parse church entries from page text."""
    churches = []
    blocks = re.split(r'\n{2,}', text)

    for block in blocks:
        lines = [l.strip() for l in block.split('\n') if l.strip()]
        if not lines:
            continue

        name = lines[0]
        if len(name) < 5 or any(s in name for s in [
            'AG NEWS', 'EVENTS', 'STORE', 'ESPA' + chr(209) + 'OL',
            'CHURCH DIRECTORY', 'Search', 'District', 'City', 'State',
            'SEARCH', 'Privacy Policy', 'AGREE', 'REVIEW', 'Home',
            'About Us', 'Give', 'Prayer', 'Resources', 'COPYRIGHT',
            'PRESS', 'HELP', 'Terms of Use', 'All Rights Reserved',
            'Employment', 'Select District', 'Select State',
        ]):
            continue

        keywords = ['Church', 'Temple', 'Chapel', 'Assembly', 'Ministries',
                    'Fellowship', 'Cathedral', 'Gospel', 'Tabernacle',
                    'Worship', 'Christian', 'Outreach', 'Center',
                    'Community', 'Family', 'Mission', 'Faith',
                    'Hope', 'Grace', 'New Life', 'Living Water',
                    'Calvary', 'Victory', 'Abundant', 'Harvest',
                    'Light', 'Love', 'Word', 'River', 'Rock',
                    'Cross', 'Trinity', 'Redeemer', 'King']
        if not any(k.lower() in name.lower() for k in keywords):
            continue

        addr = ''
        phone = ''
        pastor = ''
        street = ''
        city = ''
        state_code = ''

        for line in lines[1:]:
            if re.match(r'^[\d\s\-\(\)\.]+$', line) and len(line) > 7:
                phone = line
            elif re.search(r'\d{5}', line) and re.search(r'[A-Z]{2}', line):
                addr = line
            elif line.startswith('Reverend') or line.startswith('Pastor') or line.startswith('Rev.'):
                pastor = line
            elif line.startswith('Hervenly') or line.startswith('Minister'):
                pastor = line

        if addr:
            m = re.search(r'([A-Za-z\s.]+?),\s*([A-Z]{2})(?:\s|$)', addr)
            if m:
                city = m.group(1).strip()
                state_code = m.group(2)
            else:
                m = re.search(r'\s+([A-Za-z\s.]+?)\s+([A-Z]{2})\s+\d{5}', addr)
                if m:
                    city = m.group(1).strip()
                    state_code = m.group(2)

            addr_clean = re.sub(r',\s*[A-Za-z\s.]+,\s*[A-Z]{2}\s+\d{5}(?:-\d{4})?', '', addr)
            if addr_clean != addr:
                street = addr_clean.strip()

        churches.append({
            'name': name[:200],
            'address': street[:200],
            'city': city[:100],
            'state': state_code[:10],
            'phone': phone[:50],
            'pastor': pastor[:200],
        })

    return churches


def main():
    import argparse
    from playwright.sync_api import sync_playwright

    parser = argparse.ArgumentParser()
    parser.add_argument('--limit', type=int)
    parser.add_argument('--resume', action='store_true')
    parser.add_argument('--headless', action='store_true', default=True)
    args = parser.parse_args()

    all_churches = []
    done = set()

    if args.resume and STATE_FILE.exists():
        with open(STATE_FILE) as f:
            saved = json.load(f)
            all_churches = saved.get('churches', [])
            done = set(tuple(p) for p in saved.get('done', []))
        print(f"Resumed: {len(all_churches)} churches, {len(done)} pages done")

    if OUTPUT_CSV.exists():
        with open(OUTPUT_CSV, encoding='utf-8') as f:
            existing = list(csv.DictReader(f))
            if len(existing) > len(all_churches):
                all_churches = existing

    districts = list(range(1, 90))
    if args.limit:
        districts = districts[:args.limit]

    print(f"Districts: {len(districts)}")

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=args.headless)
        ctx = browser.new_context(
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/148.0.0.0 Safari/537.36',
            viewport={'width': 1920, 'height': 1080},
        )
        page = ctx.new_page()
        page.add_init_script('Object.defineProperty(navigator,"webdriver",{get:()=>undefined})')

        for d in districts:
            page_num = 1
            district_churches = 0

            while True:
                key = (d, page_num)
                if key in done:
                    page_num += 1
                    continue

                url = f'https://ag.org/Resources/Directories/Church-Directory?D={d}&page={page_num}'
                print(f"\n[D{d:02d} p{page_num}] ", end='', flush=True)

                try:
                    page.goto(url, wait_until='commit', timeout=20000)
                    page.wait_for_timeout(3000)
                    text = page.evaluate('() => document.body.innerText')

                    if 'No results' in text:
                        done.add(key)
                        if page_num == 1:
                            print('empty')
                        else:
                            print('done')
                        break

                    churches = extract_churches(text)
                    existing_names = {c['name'].lower().rstrip('.') for c in all_churches}
                    new = [c for c in churches if c['name'].lower().rstrip('.') not in existing_names]

                    if new:
                        all_churches.extend(new)
                        district_churches += len(new)
                        print(f'+{len(new)}', end='')
                    else:
                        print('.', end='')

                    done.add(key)
                    page_num += 1
                    if page_num > 100:
                        break

                except Exception as e:
                    print(f'ERR:{str(e)[:40]}')
                    done.add(key)
                    page_num += 1
                    continue

                time.sleep(1)

            if district_churches:
                print(f' [{district_churches}]')

            save_results(all_churches)
            with open(STATE_FILE, 'w') as f:
                json.dump({'churches': all_churches, 'done': list(done)}, f)

        browser.close()

    print(f"\nDone! {len(all_churches)} churches")
    save_results(all_churches)


def save_results(churches):
    if not churches:
        return
    fields = ['name', 'address', 'city', 'state', 'phone', 'pastor']
    with open(OUTPUT_CSV, 'w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for ch in churches:
            w.writerow({k: ch.get(k, '') for k in fields})


if __name__ == '__main__':
    main()
