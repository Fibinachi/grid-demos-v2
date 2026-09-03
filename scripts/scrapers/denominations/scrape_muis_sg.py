"""Scrape Singapore MUIS mosque directory."""
import requests, re, sqlite3, time
from bs4 import BeautifulSoup
from datetime import datetime, timezone

NOW = datetime.now(timezone.utc).isoformat()
SOURCE = "muis_sg"
DB = "E:/grid/churches.db"
URL = "https://www.muis.gov.sg/community/mosque/mosque-directory/"

def geocode_sg(address):
    """Geocode Singapore address using Nominatim. Very approximate."""
    # Singapore is small — most mosques cluster near city center
    # We'll use a rough approximation or skip
    return None, None

print(f"Fetching {URL}...")
headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
resp = requests.get(URL, headers=headers, timeout=30)
soup = BeautifulSoup(resp.text, 'html.parser')

# Find the table
table = soup.find('table')
if not table:
    print("No table found!")
    exit()

mosques = []
for row in table.find_all('tr')[1:]:  # skip header
    cells = row.find_all('td')
    if len(cells) < 3:
        continue
    
    name_cell = cells[0]
    addr_cell = cells[1]
    contact_cell = cells[2]
    
    name = name_cell.get_text(strip=True)
    link = name_cell.find('a')
    detail_url = link['href'] if link else ''
    if detail_url and not detail_url.startswith('http'):
        detail_url = 'https://www.muis.gov.sg' + detail_url
    
    address = addr_cell.get_text(' ', strip=True)
    
    contact_text = contact_cell.get_text(' ', strip=True)
    phone = ''
    email = ''
    phone_match = re.search(r'[\d]{4,}[\d\s-]*', contact_text)
    if phone_match:
        phone = phone_match.group(0).strip()
    email_match = re.search(r'[\w.-]+@[\w.-]+\.\w+', contact_text)
    if email_match:
        email = email_match.group(0)
    
    mosques.append({
        'name': name,
        'address': address,
        'phone': phone,
        'email': email,
        'url': detail_url,
    })

print(f"Found {len(mosques)} mosques")

# Show sample
for m in mosques[:5]:
    print(f"  {m['name'][:40]:40s} | {m['phone']:15s} | {m['email'][:30]}")

# ── Insert into DB ──
conn = sqlite3.connect(DB)
conn.execute("PRAGMA journal_mode=WAL")
conn.execute("PRAGMA busy_timeout=60000")
c = conn.cursor()

# Build coordinate grid
c.execute("SELECT ROUND(lat,4), ROUND(lon,4) FROM holy_sites WHERE lat IS NOT NULL")
grid = set(c.fetchall())

ch_inserted = 0
hs_inserted = 0
contact_inserted = 0

for m in mosques:
    # Geocode — we'll try a simple approach
    # For now, insert without coordinates (will need geocoding later)
    lat, lon = None, None
    
    # Insert holy_site
    if lat is not None:
        gl, gn = round(lat, 4), round(lon, 4)
        if (gl, gn) not in grid:
            c.execute("""
                INSERT INTO holy_sites 
                (name, faith, tradition, country, lat, lon, source_primary, is_landmark, landmark_type, confidence_score)
                VALUES (?,?,?,?,?,?,?,?,?,?)
            """, (m['name'][:500], 'Islam', 'Sunni', 'SG', lat, lon, SOURCE, 0, 'mosque', 0.9))
            hs_inserted += 1
            grid.add((gl, gn))
        hs_site_id = c.lastrowid
    else:
        c.execute("""
            INSERT INTO holy_sites 
            (name, faith, tradition, country, source_primary, is_landmark, landmark_type, confidence_score)
            VALUES (?,?,?,?,?,?,?,?)
        """, (m['name'][:500], 'Islam', 'Sunni', 'SG', SOURCE, 0, 'mosque', 0.9))
        hs_inserted += 1
        hs_site_id = c.lastrowid
    
    # Insert church
    c.execute("""
        INSERT INTO churches 
        (name, faith, denomination, address, country, source, holy_site_id, landmark_type)
        VALUES (?,?,?,?,?,?,?,?)
    """, (m['name'][:500], 'Islam', 'Sunni', m['address'][:500], 'SG', SOURCE, hs_site_id, 'mosque'))
    church_id = c.lastrowid
    ch_inserted += 1
    
    # Insert contacts
    if m['phone'] or m['email']:
        c.execute("""
            INSERT INTO church_contacts 
            (church_id, phone, email, phone_source, email_source, website, website_source)
            VALUES (?,?,?,?,?,?,?)
        """, (church_id, m['phone'], m['email'], SOURCE, SOURCE, m['url'], SOURCE))
        contact_inserted += 1

conn.commit()

# ── Verify ──
c.execute("SELECT COUNT(*) FROM churches WHERE source=?", (SOURCE,))
print(f"\n=== Results ===")
print(f"  Mosques scraped: {len(mosques)}")
print(f"  holy_sites inserted: {hs_inserted}")
print(f"  churches inserted: {ch_inserted}")
print(f"  with contacts: {contact_inserted}")

c.execute("SELECT COUNT(*) FROM churches WHERE country='SG'")
print(f"  SG total now: {c.fetchone()[0]:,}")

# Provenance
c.execute("""
    INSERT INTO provenance_log 
    (source, script_name, started_at, completed_at, churches_inserted,
     fields_populated, records_attempted, records_matched, status, notes)
    VALUES(?,?,?,?,?,?,?,?,'completed',?)
""", (SOURCE, "scrape_muis_sg.py", NOW, datetime.now(timezone.utc).isoformat(),
     ch_inserted, "name,address,phone,email,website,denomination",
     len(mosques), ch_inserted,
     f"MUIS Singapore: {len(mosques)} mosques scraped"))

conn.commit()
conn.close()
print("\nDone.")
