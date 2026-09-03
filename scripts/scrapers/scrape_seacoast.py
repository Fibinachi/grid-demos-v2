
"""Scrape Seacoast Church (seacoast.org) campuses and import as church records."""
import re, sqlite3, os, sys
from datetime import datetime

try:
    from playwright.sync_api import sync_playwright
    HAS_PW = True
except ImportError:
    HAS_PW = False

PROJECT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DB_PATH = os.path.join(PROJECT, 'churches.db')

def log(msg): print(f"  {msg}", flush=True)

def scrape_seacoast():
    if not HAS_PW:
        log("Playwright not installed")
        return

    log("=== Seacoast Church Campus Scraper ===")

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        page = browser.new_page()

        # Try known Seacoast locations URLs
        urls = [
            'https://www.seacoast.org/locations',
            'https://www.seacoast.org/campuses',
            'https://www.seacoast.org/visit',
        ]

        all_text = ''
        for url in urls:
            try:
                log(f"Trying {url}...")
                page.goto(url, wait_until='domcontentloaded', timeout=15000)
                page.wait_for_timeout(2000)
                text = page.inner_text('body')
                log(f"  Got {len(text):,} chars")
                all_text = text
                break
            except Exception as e:
                log(f"  Failed: {type(e).__name__}")

        if not all_text:
            log("Could not load any Seacoast locations page")
            browser.close()
            return

        # Extract campus info from text patterns
        # Typical format: "Campus Name | Address | Service Times"
        campuses = []

        # Pattern: "Campus Name" followed by address
        campus_blocks = re.split(r'\n(?=[A-Z][\w\s]+Campus|\d+\s+[A-Z])', all_text)
        for block in campus_blocks:
            if len(block) < 20:
                continue

            # Extract name
            name = ''
            m = re.search(r'^([A-Z][\w\s\'-]+(?:Campus|Church|Chapel))', block)
            if m:
                name = m.group(1).strip()
            else:
                m = re.search(r'^([A-Z][\w\s\'-]{5,40})', block)
                if m: name = m.group(1).strip()

            if not name or 'Seacoast' not in name:
                # Also try: lines that look like campus entries (short title lines)
                lines = block.strip().split('\n')
                for line in lines[:3]:
                    line = line.strip()
                    if 5 < len(line) < 80 and not line.startswith(('http', 'www', '202', 'Servic')):
                        name = line
                        break

            # Skip non-campus content
            if name:
                name_clean = name.split('|')[0].split(' - ')[0].strip()
                if any(kw in name_clean.lower() for kw in ['privacy', 'about', 'contact', 'give', 'watch']):
                    continue

            # Extract address and city/state
            addr, city, state = '', '', ''
            m = re.search(r'(\d+\s+[\w\s]+(?:Rd|Road|St|Street|Dr|Drive|Ave|Avenue|Hwy|Blvd))', block)
            if m:
                addr = m.group(1).strip()

            m = re.search(r'([A-Z][a-z]+(?:\s[A-Z][a-z]+)?),\s*(SC|NC|GA|FL)', block)
            if m:
                city = m.group(1).strip()
                state = m.group(2).strip()

            # Extract website link
            links = page.query_selector_all('a')
            campus_url = ''
            for link in links:
                href = link.get_attribute('href') or ''
                txt = (link.inner_text() or '').strip()
                if name_clean.lower() in txt.lower() and 'seacoast.org' in href:
                    campus_url = href
                    break

            if name_clean and len(name_clean) > 3:
                campuses.append({
                    'name': name_clean,
                    'address': addr,
                    'city': city,
                    'state': state,
                    'website': campus_url,
                    'full_text': block[:1000],
                })
                log(f"  Found: {name_clean} | {addr} | {city}, {state}")

        browser.close()

        if not campuses:
            log("No campuses found in page text. Manual inspection needed.")
            # Save raw text for debugging
            with open('data/seacoast_raw.txt', 'w', encoding='utf-8') as f:
                f.write(all_text[:10000])
            log(f"Saved raw text to data/seacoast_raw.txt")
            return

        # Save to DB
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        now = datetime.utcnow().isoformat()
        main_id = None
        new_count = 0

        for camp in campuses:
            # Check if already exists
            c.execute("SELECT id FROM churches WHERE name LIKE ? AND city=? AND state=?",
                      (f"%{camp['name']}%", camp['city'], camp['state']))
            existing = c.fetchone()

            if existing:
                c.execute("""UPDATE churches SET address=?, website=?, last_updated=?
                    WHERE id=?""", (camp['address'], camp['website'], now, existing[0]))
                log(f"  Updated: {camp['name']}")
            else:
                c.execute("""INSERT INTO churches (name, city, state, address, website,
                    denomination, family, faith_tradition, org_type, source, website_source, last_updated)
                    VALUES (?,?,?,?,?,'Non-Denominational / Independent','Evangelical','Christian',
                    'church','seacoast_scraper','seacoast_org',?)""",
                    (camp['name'], camp['city'], camp['state'], camp['address'],
                     camp['website'], now))
                new_count += 1
                log(f"  NEW: {camp['name']} ({camp['city']}, {camp['state']})")

            # Track main campus
            if 'mount pleasant' in camp['name'].lower() or 'main' in camp['name'].lower():
                main_id = c.lastrowid or (existing[0] if existing else c.lastrowid)

        # Link campuses to main
        if main_id and len(campuses) > 1:
            c.execute("UPDATE churches SET campus_count=? WHERE id=?", (len(campuses), main_id))
            log(f"\n  Main campus #{main_id}: campus_count = {len(campuses)}")

            for camp in campuses:
                c.execute("SELECT id FROM churches WHERE name LIKE ? AND city=? AND state=?",
                          (f"%{camp['name']}%", camp['city'], camp['state']))
                existing = c.fetchone()
                if existing and existing[0] != main_id:
                    c.execute("UPDATE churches SET parent_church_id=?, campus_name=?, campus_type=? WHERE id=?",
                              (main_id, camp['name'], 'campus', existing[0]))

            # Also link by name pattern
            c.execute("""UPDATE churches SET parent_church_id=?, campus_type='campus'
                WHERE (name LIKE '%Seacoast%' AND city IN ('Mt Pleasant','Mount Pleasant','Charleston'))
                AND id != ? AND parent_church_id IS NULL""", (main_id, main_id))

        conn.commit()
        log(f"\nTotal: {len(campuses)} campuses ({new_count} new, {len(campuses)-new_count} updated)")
        c.execute("SELECT COUNT(1) FROM churches WHERE source='seacoast_scraper'")
        log(f"Seacoast churches in DB: {c.fetchone()[0]}")
        conn.close()

if __name__ == '__main__':
    scrape_seacoast()
