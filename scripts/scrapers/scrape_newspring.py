"""Scrape NewSpring Church campuses with detail-page clicks."""
import re, sqlite3, os
from datetime import datetime
from playwright.sync_api import sync_playwright

PROJECT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DB_PATH = os.path.join(PROJECT, 'churches.db')
def log(msg): print(f"  {msg}", flush=True)

log("=== NewSpring Church Scraper ===")
with sync_playwright() as pw:
    browser = pw.chromium.launch(headless=True)
    page = browser.new_page()
    page.goto('https://newspring.cc/locations', wait_until='networkidle', timeout=20000)
    page.wait_for_timeout(3000)
    
    # Click "Get Directions" on each to reveal address
    for link in page.query_selector_all('a:has-text("Get Directions")'):
        try: link.click(); page.wait_for_timeout(300)
        except: pass
    
    text = page.inner_text('body')
    campuses = []
    for block in text.split('Location\n')[1:]:
        lines = [l.strip() for l in block.split('\n') if l.strip()]
        if len(lines) < 2: continue
        name = lines[0]
        addr = ''
        for i, line in enumerate(lines):
            if 'Get Directions' in line and i+1 < len(lines):
                addr = lines[i+1]; break
        if name and name not in ('NEWSPRING CHURCH','PO Box','Built on'):
            campuses.append({'name': f"NewSpring Church - {name}", 'address': addr,
                'city': name, 'state': 'SC', 'website': f"https://newspring.cc/locations"})
            log(f"  {name} | {addr}")
    browser.close()

    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    now = datetime.utcnow().isoformat()
    main_id = None; new_count = 0
    for camp in campuses:
        c.execute("SELECT id FROM churches WHERE name LIKE ? AND city=? AND state=?", (f"%{camp['name']}%", camp['city'], camp['state']))
        ex = c.fetchone()
        if ex:
            c.execute("UPDATE churches SET address=?, website=?, denomination=?, family=?, last_updated=? WHERE id=?", (camp['address'], camp['website'], 'Non-Denominational / Independent', 'Evangelical', now, ex[0]))
        else:
            c.execute("INSERT INTO churches (name,city,state,address,website,denomination,family,faith_tradition,org_type,source,website_source,last_updated) VALUES (?,?,?,?,?,'Non-Denominational / Independent','Evangelical','Christian','church','newspring_scraper','newspring_cc',?)", (camp['name'], camp['city'], camp['state'], camp['address'], camp['website'], now))
            new_count += 1
        if 'anderson' in camp['name'].lower(): main_id = c.lastrowid or (ex[0] if ex else c.lastrowid)
    if main_id and len(campuses) > 1:
        c.execute("UPDATE churches SET campus_count=? WHERE id=?", (len(campuses), main_id))
        for camp in campuses:
            c.execute("SELECT id FROM churches WHERE name LIKE ? AND city=? AND state=?", (f"%{camp['name']}%", camp['city'], camp['state']))
            ex = c.fetchone()
            if ex and ex[0] != main_id: c.execute("UPDATE churches SET parent_church_id=?,campus_name=?,campus_type=? WHERE id=?", (main_id, camp['name'], 'campus', ex[0]))
    conn.commit()
    log(f"\n{len(campuses)} campuses ({new_count} new, {len(campuses)-new_count} updated)")
    conn.close()
