"""Scrape Life.Church campuses — single site, known selector."""
import re, sqlite3, time
from datetime import datetime
from playwright.sync_api import sync_playwright

conn = sqlite3.connect('churches.db')
c = conn.cursor()
now = datetime.utcnow().isoformat()
seen = set()
total = 0

STATE_MAP = {'Colorado':'CO','Florida':'FL','Iowa':'IA','Kansas':'KS',
    'Nebraska':'NE','New Mexico':'NM','New York':'NY','Tennessee':'TN',
    'Texas':'TX','Oklahoma':'OK'}

with sync_playwright() as pw:
    browser = pw.chromium.launch(headless=True)
    page = browser.new_page()
    page.goto('https://life.church/locations/', wait_until='load', timeout=25000)
    page.wait_for_timeout(4000)
    els = page.query_selector_all('[class*="location"]')
    print(f'Found {len(els)} location elements')

    text = '\n'.join([e.inner_text() for e in els])
    lines = [l.strip() for l in text.split('\n') if l.strip()]

    for i, line in enumerate(lines):
        m = re.search(r'(\d+\s+[\w\s]+(?:Rd|Road|St|Street|Dr|Drive|Ave|Avenue|Blvd|Ln|Hwy|Pkwy|Way|Ct|Cir|Trail|Loop))', line)
        if not m: continue
        addr = m.group(1).strip()
        if re.match(r'\d{3}[\s-]\d{4}', addr): continue
        if addr in seen: continue
        seen.add(addr)

        city = ''; st = 'OK'
        for j in [i, i+1]:
            if j < len(lines):
                m2 = re.search(r'([A-Z][a-z]+(?:\s[A-Z][a-z]+)?),\s*([A-Z]{2})', lines[j])
                if m2:
                    city = m2.group(1)
                    st = STATE_MAP.get(m2.group(2), m2.group(2))
                    break

        c.execute("""INSERT INTO churches (name,city,state,address,website,
            denomination,family,faith_tradition,org_type,source,last_updated)
            VALUES (?,?,?,?,?,'Non-Denom','Evangelical','Christian',
            'church','megachurch_scraper',?)""",
            (f'Life.Church - {city}', city, st, addr,
             'https://life.church/locations/', now))
        c.execute("UPDATE churches SET id=rowid WHERE id IS NULL AND source='megachurch_scraper'")
        total += 1
        print(f'  {city}, {st}: {addr}')

    conn.commit()
    page.close()
    browser.close()

# Distribute attendance: 85,000
if total > 0:
    main_att = round(85000 * 0.20)
    other_att = round((85000 * 0.80) / (total - 1)) if total > 1 else 85000
    c.execute("""UPDATE churches SET attendance_est=?,
        attendance_source='megachurch_scraper', attendance_confidence=0.9,
        last_updated=? WHERE source='megachurch_scraper'
        AND website LIKE '%life.church%'
        AND id = (SELECT MIN(id) FROM churches WHERE source='megachurch_scraper'
        AND website LIKE '%life.church%')""", (main_att, now))
    c.execute("""UPDATE churches SET attendance_est=?,
        attendance_source='megachurch_scraper', attendance_confidence=0.7,
        last_updated=? WHERE source='megachurch_scraper'
        AND website LIKE '%life.church%' AND attendance_est IS NULL""",
        (other_att, now))
    conn.commit()
    print(f'\n{total} campuses: main={main_att:,}, others={other_att:,}')

c.execute("""SELECT COUNT(*), SUM(attendance_est) FROM churches
    WHERE source='megachurch_scraper' AND org_type='church'""")
n, s = c.fetchone()
print(f'Grand total: {n} physical, {s:,} weekly')
conn.close()
