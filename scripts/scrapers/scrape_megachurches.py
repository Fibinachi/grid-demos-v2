"""
Scrape top 10 US megachurches for campus locations.
Strategy: sitemap-first -> locations page fallback -> Census batch geocode.
Online campuses -> org_type='online_campus' with website as stream URL.
"""
import re, sqlite3, os, json, time, urllib.request, urllib.parse, csv, io, xml.etree.ElementTree as ET
from datetime import datetime
from playwright.sync_api import sync_playwright

PROJECT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DB = os.path.join(PROJECT, 'churches.db')

CHURCHES = [
    ('LifeChurch', 'https://www.life.church', 'OK', '/locations'),
    ('Highlands', 'https://www.churchofthehighlands.com', 'AL', '/locations'),
    ('CCV', 'https://www.ccv.church', 'AZ', '/locations'),
    ('Lakewood', 'https://www.lakewoodchurch.com', 'TX', '/visit'),
    ('NorthPoint', 'https://northpoint.org', 'GA', '/locations'),
    ('Crossroads', 'https://www.crossroads.net', 'OH', '/locations'),
    ('ChristFellowship', 'https://www.christfellowship.church', 'FL', '/locations'),
    ('Saddleback', 'https://saddleback.com', 'CA', '/visit/locations'),
    ('SoutheastChristian', 'https://www.southeastchristian.org', 'KY', '/locations'),
    ('EagleBrook', 'https://www.eaglebrookchurch.com', 'MN', '/locations'),
]

STATE_MAP = {
    'Alabama':'AL','Arizona':'AZ','California':'CA','Florida':'FL','Georgia':'GA',
    'Kentucky':'KY','Minnesota':'MN','Ohio':'OH','Oklahoma':'OK','Texas':'TX',
}

def log(msg): print(f"  {msg}", flush=True)

def fetch_sitemap(domain):
    """Check sitemap for location/campus URLs. Returns list or None."""
    patterns = [
        f'{domain}/sitemap.xml',
        f'{domain}/sitemap_index.xml',
        f'{domain}/wp-sitemap.xml',
    ]
    for sm_url in patterns:
        try:
            req = urllib.request.Request(sm_url, headers={'User-Agent': 'GW/1.0'})
            with urllib.request.urlopen(req, timeout=10) as resp:
                raw = resp.read().decode('utf-8', errors='replace')
            urls = []
            root = ET.fromstring(raw)
            ns = '{http://www.sitemaps.org/schemas/sitemap/0.9}'
            for el in root.iter(f'{ns}url'):
                loc = el.find(f'{ns}loc')
                if loc is not None and loc.text:
                    u = loc.text.strip()
                    if any(kw in u.lower() for kw in ['location', 'campus']):
                        urls.append(u)
            if urls:
                log(f"sitemap {sm_url}: {len(urls)} location URLs")
                return urls
        except Exception:
            continue
    return None

def parse_locations_text(text, church_name, state_abbr, website):
    """Parse campus entries from page text. Returns list of dicts."""
    campuses = []
    lines = [l.strip() for l in text.split('\n') if l.strip()]
    for i, line in enumerate(lines):
        # Online campus?
        if re.search(r'\bOnline\s*(?:Campus|Experience|Service|Church|Only)\b', line, re.I):
            name = line.strip()
            if len(name) > 45:
                name = f"{church_name} Online"
            campuses.append({'name': name, 'address': '', 'city': '', 'state': '',
                           'online': True, 'website': website})
            log(f"    [online] {name}")
            continue

        # Physical: look for street addresses
        m = re.search(r'(\d+\s+[\w\s]+(?:Rd|Road|St|Street|Dr|Drive|Ave|Avenue|Blvd|Ln|Hwy|Pkwy|Way|Ct|Cir|Trail|Loop))', line)
        if not m:
            continue

        addr = m.group(1).strip()
        if re.match(r'\d{3}[\s-]\d{4}', addr):
            continue

        # Name from preceding lines
        cand_name = ''
        for j in range(i-1, max(i-5, 0), -1):
            candidate = lines[j].strip()
            if candidate and 3 < len(candidate) < 60:
                if not re.search(r'\d{5}|Service|Watch|Give|More|Visit|Plan|Menu|Contact|Follow', candidate):
                    cand_name = candidate
                    break
        if not cand_name:
            cand_name = f"{church_name} Campus"

        # City,State
        city = ''
        line_state = state_abbr
        for j in [i, i+1, i+2]:
            if j < len(lines):
                m2 = re.search(r'([A-Z][a-z]+(?:\s[A-Z][a-z]+)?),\s*([A-Z]{2})', lines[j])
                if m2:
                    city = m2.group(1)
                    line_state = STATE_MAP.get(m2.group(2), m2.group(2))
                    break

        campuses.append({
            'name': cand_name, 'address': addr, 'city': city,
            'state': line_state, 'online': False, 'website': website
        })
        log(f"    {cand_name} | {addr} | {city or '?'}, {line_state}")

    # Fallback: city-only patterns
    if not campuses:
        for line in lines:
            for match in re.finditer(r'([A-Z][a-z]+)\s*(?:Campus|Location)\b', line):
                city = match.group(1)
                if city not in [c['city'] for c in campuses]:
                    campuses.append({
                        'name': f"{church_name} - {city}",
                        'address': '', 'city': city, 'state': state_abbr,
                        'online': False, 'website': website
                    })
                    log(f"    city-only: {city}")

    return campuses

def census_geocode_batch(addresses):
    """Batch geocode via Census API. Returns dict of idx->(lat,lon)."""
    if not addresses:
        return {}

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
                    lat = float(parts[3].strip())
                    lon = float(parts[4].strip())
                    results[idx] = (lat, lon)
                except:
                    pass
        log(f"  Census: {len(results)}/{len(addresses)} matched")
    except Exception as e:
        log(f"  Census FAIL: {e}")
    return results

def run():
    log("=== Megachurch Campus Scraper (Sitemap + Census) ===")
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    now = datetime.utcnow().isoformat()
    total_new, total_online, total_geo = 0, 0, 0

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)

        for name, domain, state_abbr, loc_path in CHURCHES:
            log(f"\n{name}: {domain}")

            campus_urls = fetch_sitemap(domain)
            all_campuses = []

            if campus_urls:
                for cu in campus_urls[:60]:
                    page = browser.new_page()
                    try:
                        page.goto(cu, wait_until='domcontentloaded', timeout=12000)
                        text = page.inner_text('body')
                        camps = parse_locations_text(text, name, state_abbr, cu)
                        for camp in camps:
                            camp['page_url'] = cu
                        all_campuses.extend(camps)
                    except Exception as e:
                        log(f"  FAIL {cu}: {e}")
                    finally:
                        page.close()

            if not all_campuses:
                loc_url = f'{domain}{loc_path}'
                page = browser.new_page()
                try:
                    log(f"  trying {loc_url}")
                    page.goto(loc_url, wait_until='domcontentloaded', timeout=15000)
                    page.wait_for_timeout(2000)
                    text = page.inner_text('body')
                    log(f"  {len(text)} chars")
                    all_campuses = parse_locations_text(text, name, state_abbr, loc_url)
                    for camp in all_campuses:
                        camp['page_url'] = loc_url
                except Exception as e:
                    log(f"  FAIL {loc_url}: {e}")
                finally:
                    page.close()

            for camp in all_campuses:
                if camp.get('online'):
                    process_online(c, name, camp, now)
                    total_online += 1
                else:
                    process_physical(c, name, camp, now)
                    total_new += 1

            conn.commit()

        browser.close()

    # Batch geocode all new physical campuses via Census
    log("\n=== Census Batch Geocoding ===")
    c.execute("""SELECT id, name, address, city, state FROM churches
        WHERE source='megachurch_scraper' AND org_type='church' AND latitude IS NULL""")
    to_geo = c.fetchall()
    if to_geo:
        log(f"{len(to_geo)} to geocode")
        batch_size = 50
        for batch_start in range(0, len(to_geo), batch_size):
            batch_addrs = [{'address': r[2], 'city': r[3], 'state': r[4]} for r in to_geo[batch_start:batch_start+batch_size]]

            results = census_geocode_batch(batch_addrs)

            for i, row in enumerate(to_geo[batch_start:batch_start+batch_size]):
                church_id = row[0]
                if str(i) in results:
                    lat, lon = results[str(i)]
                    c.execute("""UPDATE churches SET latitude=?,longitude=?,
                        geocode_source='census',geocode_confidence=0.8,
                        geocode_last_verified=? WHERE id=?""",
                        (lat, lon, now, church_id))
                    total_geo += 1

            conn.commit()
            log(f"  batch {batch_start//batch_size + 1}: saved")
            if batch_start + batch_size < len(to_geo):
                time.sleep(1.5)

    log(f"\n=== Done: {total_new} physical, {total_online} online, {total_geo} geocoded ===")
    c.execute("""SELECT org_type, COUNT(1) FROM churches
        WHERE source='megachurch_scraper' GROUP BY org_type""")
    for row in c.fetchall():
        log(f"  {row[0]}: {row[1]}")
    conn.close()

def process_physical(c, church_name, camp, now):
    c.execute("""SELECT id FROM churches
        WHERE name=? AND city=? AND org_type='church'""",
        (camp['name'], camp['city']))
    ex = c.fetchone()
    if ex:
        c.execute("""UPDATE churches SET address=?, website=?, last_updated=?
            WHERE id=?""", (camp['address'], camp['website'], now, ex[0]))
        log(f"    [update] {camp['name']}")
    else:
        c.execute("""INSERT INTO churches (name,city,state,address,website,
            denomination,family,faith_tradition,org_type,source,last_updated)
            VALUES (?,?,?,?,?,'Non-Denom','Evangelical','Christian',
            'church','megachurch_scraper',?)""",
            (camp['name'], camp['city'], camp['state'],
             camp['address'], camp['website'], now))
        log(f"    [new] {camp['name']} | {camp['city']}")

def process_online(c, church_name, camp, now):
    c.execute("""SELECT id FROM churches
        WHERE name=? AND org_type='online_campus'""",
        (camp['name'],))
    ex = c.fetchone()
    if ex:
        c.execute("""UPDATE churches SET website=?, last_updated=?
            WHERE id=?""", (camp['website'], now, ex[0]))
        log(f"    [update-online] {camp['name']}")
    else:
        c.execute("""INSERT INTO churches (name,website,
            denomination,family,faith_tradition,org_type,source,last_updated)
            VALUES (?,?,'Non-Denom','Evangelical','Christian',
            'online_campus','megachurch_scraper',?)""",
            (camp['name'], camp['website'], now))
        log(f"    [new-online] {camp['name']} -> {camp['website']}")

if __name__ == '__main__':
    run()
