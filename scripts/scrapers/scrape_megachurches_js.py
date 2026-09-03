"""
Scrape the 5 JS-rendered megachurch sites that the generic scraper couldn't parse.
Uses wait_for_selector + longer timeouts + multiple extraction strategies.
"""
import re, sqlite3, os, json, time, urllib.request, urllib.parse, csv, io
from datetime import datetime
from playwright.sync_api import sync_playwright

PROJECT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DB = os.path.join(PROJECT, 'churches.db')

# (name, url, state, total_attendance, expected_campuses)
CHURCHES = [
    ('Life.Church', 'https://life.church/locations/', 'OK', 85000, 40),
    ('Lakewood Church', 'https://lakewoodchurch.com/visit', 'TX', 45000, 1),
    ('North Point Ministries', 'https://northpoint.org/locations/', 'GA', 37000, 8),
    ('Christ Fellowship', 'https://www.christfellowship.church/locations', 'FL', 29500, 17),
    ('Southeast Christian Church', 'https://www.southeastchristian.org/locations', 'KY', 28000, 5),
]

STATE_MAP = {'Alabama':'AL','Arizona':'AZ','California':'CA','Florida':'FL','Georgia':'GA',
    'Kentucky':'KY','Minnesota':'MN','Ohio':'OH','Oklahoma':'OK','Texas':'TX'}

def log(msg): print(f"  {msg}", flush=True)

def parse_text(text, church_name, state):
    """Extract campus entries from page text."""
    campuses = []
    lines = [l.strip() for l in text.split('\n') if l.strip()]
    for i, line in enumerate(lines):
        # Online campus?
        if re.search(r'\bOnline\s*(?:Campus|Experience|Service|Church|Only)\b', line, re.I):
            name = line.strip()
            if len(name) > 45: name = f"{church_name} Online"
            campuses.append({'name': name, 'address': '', 'city': '', 'state': '',
                           'online': True})
            log(f"    [online] {name}")
            continue

        # Street address pattern
        m = re.search(r'(\d+\s+[\w\s]+(?:Rd|Road|St|Street|Dr|Drive|Ave|Avenue|Blvd|Ln|Hwy|Pkwy|Way|Ct|Cir|Trail|Loop))', line)
        if not m: continue
        addr = m.group(1).strip()
        if re.match(r'\d{3}[\s-]\d{4}', addr): continue  # phone number

        # Name from preceding lines
        cand_name = ''
        for j in range(i-1, max(i-5, 0), -1):
            candidate = lines[j].strip()
            if candidate and 3 < len(candidate) < 60:
                if not re.search(r'\d{5}|Service|Watch|Give|More|Visit|Plan|Menu|Contact|Follow', candidate):
                    cand_name = candidate; break
        if not cand_name: cand_name = f"{church_name} Campus"

        # City,State
        city = ''; line_state = state
        for j in [i, i+1, i+2]:
            if j < len(lines):
                m2 = re.search(r'([A-Z][a-z]+(?:\s[A-Z][a-z]+)?),\s*([A-Z]{2})', lines[j])
                if m2:
                    city = m2.group(1)
                    line_state = STATE_MAP.get(m2.group(2), m2.group(2))
                    break

        campuses.append({'name': cand_name, 'address': addr, 'city': city,
                        'state': line_state, 'online': False})
        log(f"    {cand_name} | {addr} | {city or '?'}, {line_state}")

    # Fallback: city-only matches
    if not campuses:
        for line in lines:
            for match in re.finditer(r'([A-Z][a-z]+)\s*(?:Campus|Location)\b', line):
                city = match.group(1)
                if city not in [c['city'] for c in campuses]:
                    campuses.append({'name': f"{church_name} - {city}",
                        'address': '', 'city': city, 'state': state, 'online': False})
                    log(f"    city-only: {city}")

    return campuses

def census_geocode_batch(addresses):
    """Batch geocode via Census API."""
    if not addresses: return {}
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(['Unique ID', 'Street address', 'City', 'State', 'ZIP'])
    for i, a in enumerate(addresses):
        writer.writerow([str(i), a.get('address',''), a.get('city',''), a.get('state',''), ''])

    url = 'https://geocoding.geo.census.gov/geocoder/locations/addressbatch'
    boundary = '----FormBoundaryGW'
    body = (
        f'--{boundary}\r\n'
        f'Content-Disposition: form-data; name="benchmark"\r\n\r\nPublic_AR_Current\r\n'
        f'--{boundary}\r\n'
        f'Content-Disposition: form-data; name="addressFile"; filename="addrs.csv"\r\n'
        f'Content-Type: text/csv\r\n\r\n{buf.getvalue()}\r\n'
        f'--{boundary}--\r\n'
    ).encode('utf-8')

    req = urllib.request.Request(url, data=body,
        headers={'Content-Type': f'multipart/form-data; boundary={boundary}'})
    results = {}
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            raw = resp.read().decode('utf-8', errors='replace')
        for line in raw.strip().split('\n'):
            parts = line.split(',')
            if len(parts) >= 6 and parts[5].strip() == 'Match':
                idx = parts[0].strip()
                try:
                    lat, lon = float(parts[3].strip()), float(parts[4].strip())
                    results[idx] = (lat, lon)
                except: pass
        log(f"  Census: {len(results)}/{len(addresses)} matched")
    except Exception as e:
        log(f"  Census FAIL: {e}")
    return results

def run():
    log("=== JS-Aware Megachurch Scraper ===\n")
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    now = datetime.utcnow().isoformat()
    all_inserts = []

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)

        for name, url, state, total_att, expected in CHURCHES:
            log(f"{name}: {url}")
            page = browser.new_page()
            campuses = []

            try:
                # Strategy: wait longer, try networkidle first then fall back
                page.goto(url, wait_until='load', timeout=25000)
                # Give JS time to render
                page.wait_for_timeout(4000)

                # Try to find location containers
                selectors = [
                    '.location', '.locations__item', '.campus', '.campuses__item',
                    'article', '[class*="location"]', '[class*="campus"]',
                    'li:has(address)', 'div:has(address)',
                ]
                found_selector = None
                for sel in selectors:
                    try:
                        page.wait_for_selector(sel, timeout=2000)
                        found_selector = sel
                        break
                    except: pass

                if found_selector:
                    # Extract from structured elements
                    elements = page.query_selector_all(found_selector)
                    log(f"  Found {len(elements)} elements via '{found_selector}'")
                    for el in elements:
                        txt = el.inner_text()
                        camps = parse_text(txt, name, state)
                        for camp in camps:
                            camp['page_url'] = url
                        campuses.extend(camps)
                else:
                    # Fallback: grab all visible text
                    text = page.inner_text('body')
                    log(f"  No selector match, {len(text)} chars raw text")
                    campuses = parse_text(text, name, state)
                    for camp in campuses:
                        camp['page_url'] = url

            except Exception as e:
                log(f"  ERROR: {e}")
                # Last resort: try with longer timeout
                try:
                    page.goto(url, wait_until='load', timeout=40000)
                    page.wait_for_timeout(8000)
                    text = page.inner_text('body')
                    log(f"  Retry: {len(text)} chars")
                    campuses = parse_text(text, name, state)
                except Exception as e2:
                    log(f"  FATAL: {e2}")
            finally:
                page.close()

            # Save to DB
            for camp in campuses:
                if camp.get('online'):
                    c.execute("""INSERT INTO churches (name,website,
                        denomination,family,faith_tradition,org_type,source,last_updated)
                        VALUES (?,?,'Non-Denom','Evangelical','Christian',
                        'online_campus','megachurch_scraper',?)""",
                        (camp['name'], url, now))
                    c.execute("UPDATE churches SET id=rowid WHERE id IS NULL AND source='megachurch_scraper'")
                    log(f"    [online] {camp['name']}")
                else:
                    c.execute("""INSERT INTO churches (name,city,state,address,website,
                        denomination,family,faith_tradition,org_type,source,last_updated)
                        VALUES (?,?,?,?,?,'Non-Denom','Evangelical','Christian',
                        'church','megachurch_scraper',?)""",
                        (camp['name'], camp['city'] or '', camp['state'],
                         camp['address'], url, now))
                    c.execute("UPDATE churches SET id=rowid WHERE id IS NULL AND source='megachurch_scraper'")
                    all_inserts.append(camp)
                    log(f"    [new] {camp['name']} | {camp['city'] or '?'}")

            conn.commit()

        browser.close()

    # Batch geocode via Census
    if all_inserts:
        log(f"\n=== Census Batch Geocoding: {len(all_inserts)} addresses ===")
        c.execute("""SELECT id, name, address, city, state FROM churches
            WHERE source='megachurch_scraper' AND org_type='church' AND latitude IS NULL""")
        to_geo = c.fetchall()
        if to_geo:
            batch_size = 50
            total_geo = 0
            for bs in range(0, len(to_geo), batch_size):
                batch = [{'address': r[2], 'city': r[3], 'state': r[4]} for r in to_geo[bs:bs+batch_size]]
                results = census_geocode_batch(batch)
                for i, row in enumerate(to_geo[bs:bs+batch_size]):
                    if str(i) in results:
                        lat, lon = results[str(i)]
                        c.execute("""UPDATE churches SET latitude=?,longitude=?,
                            geocode_source='census',geocode_confidence=0.8,
                            geocode_last_verified=? WHERE id=?""",
                            (lat, lon, now, row[0]))
                        total_geo += 1
                conn.commit()
                log(f"  batch {bs//batch_size+1}: {len(results)} geocoded")
                if bs + batch_size < len(to_geo): time.sleep(1.5)
            log(f"  Total geocoded: {total_geo}")

    # Distribute attendance (80/20 split)
    log("\n=== Attendance Distribution ===")
    for name, url, state, total_att, expected in CHURCHES:
        c.execute("""SELECT COUNT(*) FROM churches 
            WHERE source='megachurch_scraper' AND org_type='church' 
            AND website=?""", (url,))
        total = c.fetchone()[0]
        if total == 0: continue

        if total == 1:
            c.execute("""UPDATE churches SET attendance_est=?,
                attendance_source='megachurch_scraper', attendance_confidence=0.9,
                last_updated=? WHERE source='megachurch_scraper' 
                AND org_type='church' AND website=?""",
                (total_att, now, url))
            log(f"  {name}: 1 -> {total_att:,}")
        else:
            main_att = round(total_att * 0.20)
            other_att = round((total_att * 0.80) / (total - 1))
            # Main = first campus
            c.execute("""UPDATE churches SET attendance_est=?,
                attendance_source='megachurch_scraper', attendance_confidence=0.9,
                last_updated=? WHERE source='megachurch_scraper' 
                AND org_type='church' AND website=? AND id = (
                    SELECT MIN(id) FROM churches WHERE source='megachurch_scraper' 
                    AND org_type='church' AND website=?)""",
                (main_att, now, url, url))
            c.execute("""UPDATE churches SET attendance_est=?,
                attendance_source='megachurch_scraper', attendance_confidence=0.7,
                last_updated=? WHERE source='megachurch_scraper' 
                AND org_type='church' AND website=? AND attendance_est IS NULL""",
                (other_att, now, url))
            log(f"  {name}: {total} camps, main={main_att:,}, others={other_att:,}")

    conn.commit()

    # Summary
    c.execute("""SELECT website, COUNT(*), MAX(attendance_est) FROM churches 
        WHERE source='megachurch_scraper' AND org_type='church'
        GROUP BY website ORDER BY MAX(attendance_est) DESC""")
    for r in c.fetchall():
        log(f"  {r[0][:50]:50s} {r[1]:3d} camps  ~{r[2]:,}")

    c.execute("SELECT COUNT(*), SUM(attendance_est) FROM churches WHERE source='megachurch_scraper' AND org_type='church'")
    n, s = c.fetchone()
    log(f"\nTotal: {n} physical campuses, {s:,} weekly attendance")
    conn.close()

if __name__ == '__main__':
    run()
