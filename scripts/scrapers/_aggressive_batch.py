"""
AGGRESSIVE BATCH SCRAPER — tries all finders, multiple strategies each.
Doesn't stop until every scraper is attempted. Retries failures.
"""
import requests, re, json, sqlite3, time, csv
from bs4 import BeautifulSoup
from concurrent.futures import ThreadPoolExecutor, as_completed

DB = r'E:\grid\churches.db'

# ALL finders from backlog — domain, finder URL, denomination name
FINDERS = [
    # Already had success or partial success
    ("rca_wpsl", "RCA", "www.rca.org", "/wp-json/wp/v2/wpsl_stores", "Reformed Church in America", "Reformed"),
    # WordPress sites
    ("cme_wp", "CME", "thecmechurch.org", "/wp-json/wp/v2/types", "Christian Methodist Episcopal", "Methodist"),
    ("upci_wp", "UPCI", "upci.org", "/wp-json/wp/v2/types", "United Pentecostal Church International", "Pentecostal"),
    ("icoc_wp", "ICOC", "disciplestoday.org", "/wp-json/wp/v2/types", "International Churches of Christ", "Churches of Christ"),
    ("foursquare_wp", "Foursquare", "www.foursquare.org", "/wp-json/wp/v2/types", "Foursquare Church", "Pentecostal"),
    ("ucc_wp", "UCC", "www.ucc.org", "/wp-json/wp/v2/types", "United Church of Christ", "Congregational"),
    ("cma_wp", "C&MA", "cmalliance.org", "/wp-json/wp/v2/types", "Christian and Missionary Alliance", "Evangelical"),
    ("aflc_wp", "AFLC", "www.aflc.org", "/wp-json/wp/v2/types", "Association of Free Lutheran Congregations", "Lutheran"),
    ("nafwb_wp", "NAFWB", "directory.nafwb.org", "/wp-json/wp/v2/types", "National Association of Free Will Baptists", "Baptist"),
    ("apostolic_wp", "Apostolic Lutheran", "www.apostoliclutheran.org", "/wp-json/wp/v2/types", "Apostolic Lutheran Church", "Lutheran"),
    # Non-WP with known structures
    ("crcna_drupal", "CRCNA", "www.crcna.org", "/churches?format=json", "Christian Reformed Church", "Reformed"),
    ("wels_yearbook", "WELS Yearbook", "yearbook.wels.net", "/unitsearch", "Wisconsin Evangelical Lutheran Synod", "Lutheran"),
    ("cov_church", "Covenant", "covchurch.org", "/find-a-church/", "Evangelical Covenant Church", "Evangelical"),
    ("calvary_chapel", "Calvary Chapel", "calvarycca.org", "/churches/", "Calvary Chapel", "Evangelical"),
    ("converge", "Converge", "converge.org", "/who-we-are/churches/", "Converge", "Baptist"),
    ("arp_church", "ARP", "arpchurch.org", "/worship-with-us/", "Associate Reformed Presbyterian", "Presbyterian"),
    ("gmc_church", "GMC", "globalmethodist.org", "/find-a-church-2/", "Global Methodist Church", "Methodist"),
    ("ccc_union", "CCCU", "www.cccuhq.org", "/churches", "Churches of Christ in Christian Union", "Churches of Christ"),
    ("church_of_christ", "Church of Christ Dir", "www.church-of-christ.org", "/directories/churches.html", "Churches of Christ", "Churches of Christ"),
    ("vineyard", "Vineyard", "vineyardusa.org", "/find/", "Vineyard USA", "Evangelical"),
    ("tgc_churches", "TGC", "www.thegospelcoalition.org", "/churches/", "The Gospel Coalition", "Evangelical"),
    ("acts29", "Acts29", "www.acts29.com", "/find-a-church/", "Acts 29 Network", "Evangelical"),
    ("arc_church", "ARC", "www.arcchurches.com", "/find-a-church/", "ARC Churches", "Evangelical"),
    ("primitivemethodist", "Primitive Methodist", "www.primitivemethodistchurch.org", "/churches", "Primitive Methodist Church", "Methodist"),
    ("cooljc", "COOLJC", "www.cooljc.org", "/locate-church/", "Church of Our Lord Jesus Christ", "Pentecostal"),
    ("pcg_church", "PCG", "www.pcg.org", "/about/findchurch", "Philadelphia Church of God", "Other"),
    ("taalc", "TAALC", "www.taalc.org", "/church-finder", "The American Association of Lutheran Churches", "Lutheran"),
    ("clba_church", "CLBA", "clba.org", "/locations", "Church of the Lutheran Brethren", "Lutheran"),
    ("els_church", "ELS", "els.org", "/locations/", "Evangelical Lutheran Synod", "Lutheran"),
]

successes = []
failures = []

def try_strategy(name, domain, url, movement, tradition, strategy):
    """Try one extraction strategy. Returns list of church dicts or None."""
    try:
        if strategy == "wp_wpsl":
            # WP Store Locator plugin
            r = requests.get(f"https://{domain}/wp-json/wp/v2/wpsl_stores?per_page=1", timeout=8)
            if r.status_code == 200:
                total = int(r.headers.get('X-WP-Total', 0))
                if total > 50:
                    return fetch_wpsl(domain, total)
        elif strategy == "wp_types":
            # Check custom post types for church data
            r = requests.get(f"https://{domain}/wp-json/wp/v2/types", timeout=8)
            if r.status_code == 200:
                types = r.json()
                for type_name in types:
                    if any(kw in type_name.lower() for kw in ['church', 'location', 'store', 'congregation', 'parish']):
                        base = types[type_name].get('rest_base', type_name)
                        r2 = requests.get(f"https://{domain}/wp-json/wp/v2/{base}?per_page=1", timeout=8)
                        if r2.status_code == 200:
                            total = int(r2.headers.get('X-WP-Total', 0))
                            if total > 20:
                                return fetch_wp_type(domain, base, total)
        elif strategy == "html_table":
            r = requests.get(url if 'http' in url else f"https://{domain}{url}", timeout=10,
                           headers={'User-Agent': 'Mozilla/5.0'})
            if r.status_code == 200:
                soup = BeautifulSoup(r.text, 'html.parser')
                tables = soup.find_all('table')
                for t in tables:
                    rows = t.find_all('tr')
                    churches = []
                    for row in rows[1:]:
                        cells = row.find_all(['td', 'th'])
                        if len(cells) >= 3:
                            name = cells[0].get_text(strip=True)
                            if len(name) > 5 and len(name) < 100:
                                churches.append({
                                    'name': name,
                                    'address': cells[1].get_text(strip=True) if len(cells) > 1 else '',
                                    'city': cells[2].get_text(strip=True) if len(cells) > 2 else '',
                                    'state': cells[3].get_text(strip=True) if len(cells) > 3 else '',
                                })
                    if len(churches) > 10:
                        return churches
        elif strategy == "json_ld":
            r = requests.get(url if 'http' in url else f"https://{domain}{url}", timeout=10,
                           headers={'User-Agent': 'Mozilla/5.0'})
            if r.status_code == 200:
                matches = re.findall(r'application/ld\+json[^>]*>({.+?})</script', r.text, re.DOTALL)
                churches = []
                for m in matches:
                    try:
                        ld = json.loads(m)
                        items = ld.get('@graph', [ld]) if isinstance(ld, dict) else []
                        for item in items:
                            if isinstance(item, dict):
                                addr = item.get('address', {})
                                name = item.get('name', '')
                                if name and addr and addr.get('addressLocality'):
                                    churches.append({
                                        'name': name,
                                        'address': addr.get('streetAddress', ''),
                                        'city': addr.get('addressLocality', ''),
                                        'state': addr.get('addressRegion', ''),
                                    })
                    except: pass
                if len(churches) > 10:
                    return churches
    except Exception as e:
        pass
    return None

def fetch_wpsl(domain, total):
    """Fetch all wpsl_stores."""
    churches = []
    for page in range(1, (total // 100) + 2):
        r = requests.get(f"https://{domain}/wp-json/wp/v2/wpsl_stores", 
                        params={'per_page': 100, 'page': page, '_embed': True}, timeout=15)
        if r.status_code != 200: break
        for s in r.json():
            title = s['title']['rendered'].strip()
            # WPSL data is in ACF fields or content
            content = s.get('content', {}).get('rendered', '')
            m = re.search(r'([^,]+),\s*([A-Z]{2})\s+(\d{5})', content)
            if m:
                churches.append({
                    'name': title,
                    'city': m.group(1).strip(),
                    'state': m.group(2),
                    'address': '',
                })
        if len(r.json()) < 100: break
        time.sleep(0.2)
    return churches if churches else None

def fetch_wp_type(domain, base, total):
    """Fetch all items of a WP custom post type."""
    churches = []
    for page in range(1, min((total // 100) + 2, 30)):
        r = requests.get(f"https://{domain}/wp-json/wp/v2/{base}", 
                        params={'per_page': 100, 'page': page, '_embed': True}, timeout=15)
        if r.status_code != 200: break
        for item in r.json():
            title = item.get('title', {}).get('rendered', '') if isinstance(item.get('title'), dict) else ''
            content = item.get('content', {}).get('rendered', '') if isinstance(item.get('content'), dict) else ''
            text = f"{title} {content}"
            m = re.search(r'([^,]+),\s*([A-Z]{2})\s+(\d{5})', text)
            if m:
                churches.append({
                    'name': title.strip(),
                    'city': m.group(1).strip(),
                    'state': m.group(2),
                    'address': '',
                })
        if len(r.json()) < 100: break
        time.sleep(0.2)
    return churches if churches else None

def import_churches(churches, source, movement_name, tradition_name):
    """Import into DB."""
    if not churches: return 0, 0
    db = sqlite3.connect(DB)
    db.execute('PRAGMA busy_timeout=60000')
    c = db.cursor()
    
    mov = c.execute("SELECT id FROM movement WHERE name=?", (movement_name,)).fetchone()
    if mov: mov_id = mov[0]
    else:
        mid = c.execute("SELECT MAX(id) FROM movement").fetchone()[0] + 1
        trad = c.execute("SELECT id FROM tradition WHERE name=?", (tradition_name,)).fetchone()
        c.execute("INSERT INTO movement (id, name, tradition_id) VALUES (?,?,?)", 
                  (mid, movement_name, trad[0] if trad else None))
        db.commit(); mov_id = mid
    
    prot_id = c.execute("SELECT id FROM legacy WHERE name='Protestant'").fetchone()[0]
    trad = c.execute(f"SELECT id FROM tradition WHERE name='{tradition_name}'").fetchone()
    trad_id = trad[0] if trad else prot_id
    nid = c.execute('SELECT MAX(id) FROM churches').fetchone()[0] + 1
    imp = dup = 0
    
    for ch in churches:
        if not ch.get('state'): continue
        ex = c.execute("SELECT id FROM churches WHERE name=? AND city=? AND state=? AND faith='Christian'",
                       (ch['name'], ch.get('city',''), ch['state'])).fetchone()
        if ex:
            c.execute("UPDATE churches SET movement_id=?, tradition_id=?, legacy_id=? WHERE id=? AND movement_id IS NULL",
                      (mov_id, trad_id, prot_id, ex[0]))
            if c.rowcount > 0: dup += 1; continue
        c.execute("""INSERT INTO churches (id, name, city, state, country, address,
            faith, culture_id, legacy_id, tradition_id, movement_id, landmark_type, source)
            VALUES (?,?,?,?,'US',?,'Christian',555,?,?,?,'church',?)""",
            (nid, ch['name'], ch.get('city',''), ch['state'], ch.get('address',''), prot_id, trad_id, mov_id, source))
        nid += 1; imp += 1
    db.commit()
    db.close()
    return imp, dup

# ── MAIN ──
print("=== AGGRESSIVE BATCH SCRAPE ===\n")

for key, name, domain, path, movement, tradition in FINDERS:
    print(f"\n--- {name} ({key}) ---")
    
    strategies = ["wp_wpsl", "wp_types", "html_table", "json_ld"]
    found = False
    
    for strategy in strategies:
        url = f"https://{domain}{path}" if not path.startswith('http') else path
        result = try_strategy(key, domain, url, movement, tradition, strategy)
        if result and len(result) > 0:
            imp, dup = import_churches(result, key, movement, tradition)
            total = imp + dup
            print(f"  ✅ {strategy}: {len(result)} churches → {imp} new, {dup} updated")
            successes.append((name, len(result), imp))
            found = True
            break
        else:
            pass  # silently continue to next strategy
    
    if not found:
        print(f"  ❌ All strategies failed")
        failures.append(name)
    
    time.sleep(0.3)

print(f"\n{'='*60}")
print(f"SUCCESSES: {len(successes)}")
for name, count, imp in successes:
    print(f"  ✅ {name}: {count} churches ({imp} new)")
print(f"\nFAILURES: {len(failures)}")
for name in failures:
    print(f"  ❌ {name}")
