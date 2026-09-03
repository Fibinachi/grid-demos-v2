"""Scrape mosque lists from Wikipedia country pages.
Master index: https://en.wikipedia.org/wiki/Lists_of_mosques
Creates source_wikipedia_mosques table, links to churches.
Resume-safe: tracks scraped URLs in scrape_log.
"""
import sqlite3, requests, re, sys, os, time, json
from datetime import datetime, timezone
from urllib.parse import urljoin
from bs4 import BeautifulSoup

DB = r"E:\grid\churches.db"
HEADERS = {"User-Agent": "GRID/1.0 (https://github.com/american-rel-infra; research project)"}
BASE = "https://en.wikipedia.org"
MASTER = f"{BASE}/wiki/Lists_of_mosques"
BATCH_SIZE = 50
SCRIPT = "wikipedia_mosques"

def log(msg):
    print(f"[{datetime.now(timezone.utc).strftime('%H:%M:%S')}] {msg}", flush=True)

conn = sqlite3.connect(DB, timeout=120)
conn.execute("PRAGMA busy_timeout = 120000")
c = conn.cursor()

# ── Resume support ──
c.execute("CREATE TABLE IF NOT EXISTS scrape_log (url TEXT PRIMARY KEY, scraped_at TEXT, status TEXT)")
scraped_urls = {r[0] for r in c.execute("SELECT url FROM scrape_log WHERE status='done'").fetchall()}
log(f"Already scraped: {len(scraped_urls)} pages")

# ── Source table ──
c.execute("""
    CREATE TABLE IF NOT EXISTS source_wikipedia_mosques (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        name_arabic TEXT,
        location TEXT,
        city TEXT,
        country TEXT,
        year_built INTEGER,
        capacity INTEGER,
        denomination TEXT,
        coordinates TEXT,
        lat REAL,
        lon REAL,
        image_url TEXT,
        wiki_url TEXT UNIQUE,
        list_country TEXT,
        notes TEXT,
        scraped_at TEXT DEFAULT (datetime('now'))
    )
""")
c.execute("CREATE INDEX IF NOT EXISTS idx_wp_mosques_country ON source_wikipedia_mosques(country)")
c.execute("CREATE INDEX IF NOT EXISTS idx_wp_mosques_name ON source_wikipedia_mosques(name)")

# ── Parse coordinates from DMS or decimal ──
def parse_coords(text):
    if not text:
        return None, None
    # Decimal: 24.4675°N 39.6114°E
    m = re.search(r'([\d.]+)°?\s*([NS])\s*,?\s*([\d.]+)°?\s*([EW])', text)
    if m:
        lat = float(m.group(1)) * (-1 if m.group(2) == 'S' else 1)
        lon = float(m.group(3)) * (-1 if m.group(4) == 'W' else 1)
        return lat, lon
    # DMS: 24°28′03″N 39°36′41″E
    m = re.search(r"(\d+)°(\d+)′(\d+)″([NS]).*?(\d+)°(\d+)′(\d+)″([EW])", text)
    if m:
        lat = int(m.group(1)) + int(m.group(2))/60 + int(m.group(3))/3600
        lon = int(m.group(5)) + int(m.group(6))/60 + int(m.group(7))/3600
        lat *= -1 if m.group(4) == 'S' else 1
        lon *= -1 if m.group(8) == 'W' else 1
        return lat, lon
    return None, None

# ── Parse a country's mosque list page ──
def scrape_country_page(url, country_name):
    if url in scraped_urls:
        return 0
    
    log(f"  Fetching: {url}")
    try:
        resp = requests.get(url, headers=HEADERS, timeout=30)
        resp.raise_for_status()
    except Exception as e:
        log(f"    Error: {e}")
        c.execute("INSERT OR REPLACE INTO scrape_log VALUES (?, ?, ?)",
                  (url, datetime.now(timezone.utc).isoformat(), f"error: {e}"))
        conn.commit()
        return 0
    
    soup = BeautifulSoup(resp.text, 'html.parser')
    tables = soup.find_all('table', class_='wikitable')
    if not tables:
        log(f"    No wikitable found")
        c.execute("INSERT OR REPLACE INTO scrape_log VALUES (?, ?, ?)",
                  (url, datetime.now(timezone.utc).isoformat(), "done:0"))
        conn.commit()
        return 0
    
    inserted = 0
    for table in tables:
        rows = table.find_all('tr')[1:]  # skip header
        for row in rows:
            cells = row.find_all(['th', 'td'])
            if len(cells) < 2:
                continue
            
            # Try to extract data from cells
            name = None
            location = None
            year_built = None
            capacity = None
            image_url = None
            wiki_link = None
            
            # First cell is usually the name or image+name
            first_cell = cells[0]
            # Find wiki link
            link = first_cell.find('a', href=re.compile(r'^/wiki/'))
            if link and '/wiki/File:' not in link.get('href', ''):
                name = link.get_text(strip=True)
                wiki_link = urljoin(BASE, link['href'])
            else:
                name = first_cell.get_text(strip=True)
            
            # Find image
            img = first_cell.find('img')
            if img:
                src = img.get('src', '')
                if src.startswith('//'):
                    src = 'https:' + src
                image_url = src
            
            # Parse remaining cells
            for i, cell in enumerate(cells[1:], 1):
                text = cell.get_text(strip=True)
                
                # Location
                if any(w in text.lower() for w in ['street', 'district', 'city', 'province', 'region', 'town']) \
                   and not location:
                    location = text
                elif re.match(r'^\d{4}$', text):
                    year_built = int(text)
                elif re.match(r'^[\d,]+$', text) and not capacity:
                    capacity = int(text.replace(',', ''))
                elif not location and len(text) < 100:
                    location = text
            
            if name:
                lat, lon = None, None
                # Try to find coordinates in the row
                coord_span = row.find('span', class_='geo')
                if coord_span:
                    lat, lon = parse_coords(coord_span.get_text(strip=True))
                
                c.execute("""
                    INSERT OR IGNORE INTO source_wikipedia_mosques
                    (name, location, country, year_built, capacity, image_url, wiki_url, list_country, lat, lon)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (name[:500], location[:500] if location else None, country_name,
                      year_built, capacity, image_url, wiki_link, country_name, lat, lon))
                if c.rowcount > 0:
                    inserted += 1
    
    c.execute("INSERT OR REPLACE INTO scrape_log VALUES (?, ?, ?)",
              (url, datetime.now(timezone.utc).isoformat(), f"done:{inserted}"))
    conn.commit()
    return inserted

# ── Step 1: Fetch master index ──
log("=== Fetching master index ===")
resp = requests.get(MASTER, headers=HEADERS, timeout=15)
resp.raise_for_status()
soup = BeautifulSoup(resp.text, 'html.parser')

# Collect all country links from the page
country_links = []
seen = set()
for link in soup.find_all('a', href=re.compile(r'^/wiki/List_of_mosques_in_')):
    href = link['href']
    if href in seen:
        continue
    seen.add(href)
    url = urljoin(BASE, href)
    # Extract country from URL: List_of_mosques_in_France → France
    country = href.replace('/wiki/List_of_mosques_in_', '').replace('_', ' ')
    country_links.append((url, country))

log(f"Found {len(country_links)} country pages")

# ── Step 2: Scrape each country ──
total = 0
for i, (url, country) in enumerate(country_links):
    log(f"\n[{i+1}/{len(country_links)}] {country}")
    n = scrape_country_page(url, country)
    total += n
    if n > 0:
        log(f"  → {n} new mosques")
    
    if (i + 1) % 10 == 0:
        log(f"  === Progress: {i+1}/{len(country_links)} countries, {total} mosques ===")
    
    time.sleep(0.5)  # rate limit

# ── Step 3: Summary ──
log(f"\n{'='*60}")
log(f"Scrape complete")
log(f"  Countries: {len(country_links)}")
log(f"  New mosques: {total}")
total_all = c.execute("SELECT COUNT(*) FROM source_wikipedia_mosques").fetchone()[0]
log(f"  Total in table: {total_all}")

# ── Step 4: Match with existing churches ──
log(f"\n=== Matching with existing churches ===")
mosques = c.execute("SELECT id, name, lat, lon, country, wiki_url FROM source_wikipedia_mosques").fetchall()
matched = 0
for m in mosques:
    m_id, m_name, m_lat, m_lon, m_country, m_wiki = m
    
    # Try exact name match first
    church = c.execute(
        "SELECT id FROM churches WHERE name=? AND country=? AND faith='Islam'",
        (m_name, m_country)
    ).fetchone()
    
    if not church and m_lat and m_lon:
        # Try proximity match (within 0.01 degrees ~1km)
        church = c.execute(
            "SELECT id FROM churches WHERE ABS(latitude-?)<0.01 AND ABS(longitude-?)<0.01 AND country=?",
            (m_lat, m_lon, m_country)
        ).fetchone()
    
    if church:
        c.execute("INSERT OR IGNORE INTO church_external_ids (church_id, source, id_value) VALUES (?, 'wikipedia_mosques', ?)",
                  (church[0], m_wiki))
        matched += 1

log(f"  Matched: {matched} / {total_all}")

conn.close()
log("\nDone!")
