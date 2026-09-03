"""Scrape visitamosque.us — Ahmadiyya Muslim Community USA mosques."""
import requests, re, sqlite3, time
from bs4 import BeautifulSoup
from datetime import datetime, timezone

NOW = datetime.now(timezone.utc).isoformat()
SOURCE = "visitamosque_us"
DB = "E:/grid/churches.db"
BASE = "https://visitamosque.us"

HEADERS = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}

def scrape_state_page(state_slug):
    """Scrape a state listing page to get individual mosque URLs."""
    url = f"{BASE}/mosque-item/{state_slug}/"
    try:
        r = requests.get(url, headers=HEADERS, timeout=15)
        soup = BeautifulSoup(r.text, 'html.parser')
        mosque_links = []
        for link in soup.find_all('a', href=True):
            href = link['href']
            if '/mosque-item/' in href and href.count('/') >= 3 and href != f"/mosque-item/{state_slug}/":
                if not href.startswith('http'):
                    href = BASE + href
                mosque_links.append(href)
        return list(set(mosque_links))
    except Exception as e:
        print(f"  ERROR {state_slug}: {e}")
        return []

def scrape_mosque_page(url):
    """Scrape individual mosque detail page."""
    try:
        r = requests.get(url, headers=HEADERS, timeout=15)
        soup = BeautifulSoup(r.text, 'html.parser')
        
        name = ''
        h1 = soup.find('h1') or soup.find('h2')
        if h1:
            name = h1.get_text(strip=True)
        
        # Look for address, phone, etc. in text
        text = soup.get_text(' ', strip=True)
        
        # Try to find address pattern
        address = ''
        addr_patterns = [
            r'(\d+\s+[A-Za-z\s]+(?:Street|St|Avenue|Ave|Road|Rd|Drive|Dr|Lane|Ln|Way|Blvd|Boulevard|Court|Ct)[^,]*,?\s*[A-Za-z\s]+,?\s*[A-Z]{2}\s*\d{5})',
            r'(\d+\s+[A-Za-z\s]+,?\s*[A-Za-z\s]+,?\s*[A-Z]{2}\s*\d{5})',
        ]
        for pat in addr_patterns:
            m = re.search(pat, text)
            if m:
                address = m.group(1)
                break
        
        # Phone
        phone = ''
        phone_m = re.search(r'[\d]{3}[-.\s]?[\d]{3}[-.\s]?[\d]{4}', text)
        if phone_m:
            phone = phone_m.group(0)
        
        # Email
        email = ''
        email_m = re.search(r'[\w.-]+@[\w.-]+\.\w+', text)
        if email_m:
            email = email_m.group(0)
        
        return {
            'name': name,
            'address': address,
            'phone': phone,
            'email': email,
            'url': url,
        }
    except Exception as e:
        print(f"  ERROR {url}: {e}")
        return None

# ── Get all state pages ──
print("Step 1: Finding state pages...")
r = requests.get(BASE, headers=HEADERS, timeout=15)
soup = BeautifulSoup(r.text, 'html.parser')
state_links = []
for link in soup.find_all('a', href=True):
    href = link['href']
    if '/mosque-item/' in href and href.count('/') <= 3:
        state_links.append(href)

# Extract unique state slugs
state_slugs = set()
for link in state_links:
    parts = link.strip('/').split('/')
    if len(parts) >= 2:
        state_slugs.add(parts[-1])

print(f"  Found {len(state_slugs)} state pages")

# ── Get all mosque URLs ──
all_mosque_urls = set()
for slug in sorted(state_slugs):
    urls = scrape_state_page(slug)
    all_mosque_urls.update(urls)
    print(f"  {slug}: {len(urls)} mosques")

print(f"\n  Total mosque URLs: {len(all_mosque_urls)}")

# ── Scrape individual mosques ──
print("\nStep 2: Scraping individual mosques...")
mosques = []
for i, url in enumerate(sorted(all_mosque_urls)):
    m = scrape_mosque_page(url)
    if m and m['name']:
        mosques.append(m)
    if (i+1) % 20 == 0:
        print(f"  {i+1}/{len(all_mosque_urls)}")
    time.sleep(1)

print(f"  Scraped {len(mosques)} mosques with names")

# Show sample
for m in mosques[:5]:
    print(f"  {m['name'][:40]:40s} | {m['phone']:15s} | {m['address'][:50]}")

# ── Insert into DB ──
print("\nStep 3: Inserting into DB...")
conn = sqlite3.connect(DB)
conn.execute("PRAGMA journal_mode=WAL")
conn.execute("PRAGMA busy_timeout=30000")
c = conn.cursor()

c.execute("SELECT ROUND(lat,4), ROUND(lon,4) FROM holy_sites WHERE lat IS NOT NULL")
grid = set(c.fetchall())

ch_inserted = 0
hs_inserted = 0
contact_inserted = 0

for m in mosques:
    # Holy site (no coords from scrape)
    c.execute("""
        INSERT INTO holy_sites 
        (name, faith, tradition, country, source_primary, is_landmark, landmark_type, confidence_score)
        VALUES (?,?,?,?,?,?,?,?)
    """, (m['name'][:500], 'Islam', 'Ahmadiyya', 'US', SOURCE, 0, 'mosque', 0.9))
    hs_site_id = c.lastrowid
    hs_inserted += 1
    
    # Church
    c.execute("""
        INSERT INTO churches 
        (name, faith, denomination, address, country, source, holy_site_id, landmark_type, mosque_type)
        VALUES (?,?,?,?,?,?,?,?,?)
    """, (m['name'][:500], 'Islam', 'Ahmadiyya', m['address'][:500], 'US', SOURCE, hs_site_id, 'mosque', 'ahmadiyya_mosque'))
    church_id = c.lastrowid
    ch_inserted += 1
    
    # Contacts
    if m['phone'] or m['email'] or m['url']:
        c.execute("""
            INSERT INTO church_contacts 
            (church_id, phone, email, website, phone_source, email_source, website_source, website_scrape_status)
            VALUES (?,?,?,?,?,?,?,?)
        """, (church_id, m['phone'], m['email'], m['url'], SOURCE, SOURCE, SOURCE, 'found'))
        contact_inserted += 1

conn.commit()

print(f"\n=== Results ===")
print(f"  Mosques scraped: {len(mosques)}")
print(f"  holy_sites: {hs_inserted}")
print(f"  churches: {ch_inserted}")
print(f"  with contacts: {contact_inserted}")

c.execute("SELECT COUNT(*) FROM churches WHERE source=?", (SOURCE,))
print(f"  DB total for source: {c.fetchone()[0]}")

c.execute("""
    INSERT INTO provenance_log 
    (source, script_name, started_at, completed_at, churches_inserted,
     fields_populated, records_attempted, records_matched, status, notes)
    VALUES(?,?,?,?,?,?,?,?,'completed',?)
""", (SOURCE, "scrape_visitamosque_us.py", NOW, datetime.now(timezone.utc).isoformat(),
     ch_inserted, "name,address,phone,email,website,denomination,mosque_type",
     len(mosques), ch_inserted,
     f"visitamosque.us: {len(mosques)} Ahmadiyya mosques scraped"))

conn.commit()
conn.close()
print("\nDone.")
