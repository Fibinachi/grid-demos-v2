#!/usr/bin/env python3
"""
Scrape Wesleyan Church district directories and import into churches.db.

Districts with accessible directories:
  - Kansas District (kdwc.org) — Squarespace, ~28 churches
  - South Carolina District (scwesleyan.org) — Nucleus, ~46 churches  
  - South Coastal District (southcoastalwesleyan.com) — Weebly, ~20+ churches

Also: Classify existing Wesleyan contacts with their proper district based
on state geography.

Usage: python scripts/scrapers/denominations/scrape_wesleyan_districts.py [--dry-run]
"""
import urllib.request, re, ssl, sqlite3, sys, json, time
from datetime import datetime

DB = r'E:\grid\churches.db'
UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

DRY_RUN = '--dry-run' in sys.argv

# District definitions with state coverage for classification
DISTRICTS = {
    'Atlantic':           {'states': ['DE', 'MD', 'DC', 'VA'], 'url': 'https://www.atlanticdistrict.com'},
    'Central Canada':     {'states': ['ON', 'MB', 'SK'], 'url': 'http://www.ccdwesleyan.ca'},
    'Chesapeake':         {'states': ['MD', 'VA', 'DC'], 'url': 'http://www.chesapeakewesleyan.com'},
    'Crossroads':         {'states': ['IL', 'IN', 'KY', 'MI', 'OH'], 'url': 'https://www.wesleyan.org/crossroads'},
    'Florida':            {'states': ['FL'], 'url': 'https://www.floridawesleyan.com'},
    'Great Lakes':        {'states': ['MI', 'IN', 'OH'], 'url': 'https://theglr.org'},
    'Greater Ohio':       {'states': ['OH'], 'url': 'http://www.gowesleyan.org'},
    'Indiana South':      {'states': ['IN'], 'url': 'http://www.indianasouth.org'},
    'Kansas':             {'states': ['KS'], 'url': 'http://www.kdwc.org'},
    'Kentucky-Tennessee': {'states': ['KY', 'TN'], 'url': None},
    'Mountain Plains':    {'states': ['CO', 'WY', 'MT', 'ND', 'SD', 'NE'], 'url': 'https://www.mountainplainsdistrict.com'},
    'North Carolina East':{'states': ['NC'], 'url': 'http://www.ncewesleyan.com'},
    'North Carolina West':{'states': ['NC'], 'url': 'http://www.ncwestdistrict.org'},
    'Northeast':          {'states': ['CT', 'MA', 'ME', 'NH', 'NJ', 'NY', 'PA', 'RI', 'VT'], 'url': 'http://www.northeastdistrict.org'},
    'Northwest':          {'states': ['AK', 'ID', 'OR', 'WA'], 'url': 'http://www.northwestdistrict.org'},
    'Pacific Southwest':  {'states': ['AZ', 'CA', 'HI', 'NV', 'UT'], 'url': 'http://www.pswdistrict.com'},
    'Penn York':          {'states': ['PA', 'NY'], 'url': 'http://www.pennyorkdistrict.org'},
    'Shenandoah':         {'states': ['VA', 'WV', 'MD'], 'url': 'http://www.shenandoahdistrict.ws'},
    'South Carolina':     {'states': ['SC'], 'url': 'https://www.scwesleyan.org'},
    'South Coastal':      {'states': ['GA', 'SC'], 'url': 'https://www.southcoastalwesleyan.com'},
    'Tri-State':          {'states': ['OH', 'KY', 'WV', 'PA'], 'url': 'http://www.tsdwc.org'},
    'Western New York':   {'states': ['NY'], 'url': 'http://www.wnydistrict.com'},
}

conn = sqlite3.connect(DB)
c = conn.cursor()

def log(msg):
    print(f'  {msg}')

def upsert_church(name, city, state, address=None, phone=None, email=None, website=None,
                  district=None, denomination='Wesleyan Church', family='wesleyan',
                  source='wesleyan_district_scraper', pastor=None):
    """Insert or update a church record."""
    if not name or not state:
        return
    
    # Try to match by name + state
    c.execute("SELECT id FROM churches WHERE name = ? AND state = ?", (name, state))
    row = c.fetchone()
    
    if row:
        church_id = row[0]
        # Update fields if empty
        updates = []
        params = []
        for field, val in [('city', city), ('address', address), ('phone', phone),
                           ('email', email), ('website', website), ('district', district),
                           ('denomination', denomination), ('family', family),
                           ('source', source)]:
            if val:
                c.execute(f"SELECT {field} FROM churches WHERE id = ?", (church_id,))
                current = c.fetchone()[0]
                if not current or (isinstance(current, str) and current.strip() == ''):
                    updates.append(f"{field} = ?")
                    params.append(val)
        if updates:
            updates.append("last_updated = datetime('now')")
            params.append(church_id)
            if DRY_RUN:
                log(f'  [DRY] Would update ID={church_id}: {name} ({city}, {state})')
            else:
                c.execute(f"UPDATE churches SET {', '.join(updates)} WHERE id = ?", params)
        return church_id
    else:
        # Insert new
        if DRY_RUN:
            log(f'  [DRY] Would insert: {name} ({city}, {state})')
            return None
        cols = ['name', 'city', 'state', 'denomination', 'family', 'source', 'district']
        vals = [name, city, state, denomination, family, source, district]
        if address:
            cols.append('address'); vals.append(address)
        if phone:
            cols.append('phone'); vals.append(phone)
        if email:
            cols.append('email'); vals.append(email)
        if website:
            cols.append('website'); vals.append(website)
        
        c.execute(f"INSERT INTO churches ({', '.join(cols)}) VALUES ({', '.join(['?']*len(cols))})", vals)
        return c.lastrowid

def fetch(url, timeout=15):
    req = urllib.request.Request(url, headers={'User-Agent': UA})
    resp = urllib.request.urlopen(req, timeout=timeout, context=ctx)
    return resp.read().decode('utf-8', 'replace')

print('=' * 60)
print(f'WESLEYAN DISTRICT SCRAPER — {"DRY RUN" if DRY_RUN else "LIVE"}')
print(f'Started: {datetime.now().isoformat()}')
print('=' * 60)

# ── 1. Scrape Kansas District (Squarespace) ─────────────────────────────
print('\n--- 1. Kansas District (kdwc.org/churches) ---')
try:
    html = fetch('https://www.kdwc.org/churches')
    
    # Squarespace: churches in h2 tags, each followed by a <p> with details
    # <h2>Church Name</h2><p>Street<br>City, State Zip<br>Pastor's Name...<br>...</p>
    blocks = re.split(r'<h2\s[^>]*>', html)[1:]  # skip header
    kansas_churches = []
    
    for block in blocks:
        name_match = re.match(r'([^<]+)</h2>', block)
        if not name_match:
            continue
        name = name_match.group(1).strip()
        name = re.sub(r'&mdash;', '-', name).strip()
        name = re.sub(r'\s*--\s*', ' - ', name)
        
        # Get the paragraph content (between <p> and </p>)
        p_match = re.search(r'<p[^>]*>([\s\S]*?)</p>', block)
        p_content = p_match.group(1) if p_match else ''
        
        # Split by <br> to get lines
        lines = [l.strip() for l in re.split(r'<br\s*/?>', p_content) if l.strip()]
        
        street = ''
        city = ''
        state = 'KS'
        zip_code = ''
        pastor = ''
        phone = ''
        email = ''
        website = ''
        
        for line in lines:
            line_stripped = re.sub(r'<[^>]+>', '', line).strip()
            
            # Address line: "City, ST ZIP" or "Street" or "PO Box ..."
            if re.match(r'^\d+\s', line_stripped) or line_stripped.startswith('PO Box'):
                street = line_stripped
            elif re.match(r'^[A-Z][a-z]+[,\s]+[A-Z]{2}\s+\d', line_stripped):
                # "City, ST ZIP" - extract city
                city_match = re.match(r'^([^,]+),\s*([A-Z]{2})\s+(\d[\d-]*)', line_stripped)
                if city_match:
                    city = city_match.group(1).strip()
                    state = city_match.group(2)
                    zip_code = city_match.group(3)
            elif 'Pastor' in line_stripped and ':' in line_stripped:
                pastor = line_stripped.split(':', 1)[1].strip()
            elif 'Phone' in line_stripped and ':' in line_stripped:
                phone = line_stripped.split(':', 1)[1].strip()
            elif 'Email' in line_stripped and ':' in line_stripped:
                email_match = re.search(r'[\w.+-]+@[\w-]+\.[\w.]+', line_stripped)
                if email_match:
                    email = email_match.group(0)
            elif 'Website' in line_stripped and ':' in line_stripped:
                web_text = line_stripped.split(':', 1)[1].strip()
                web_url = re.search(r'href="([^"]+)"', line)
                if web_url:
                    website = web_url.group(1)
                elif web_text and not web_text.startswith('<'):
                    website = web_text
                    if not website.startswith('http'):
                        website = 'https://' + website
        
        kansas_churches.append({
            'name': name, 'address': street, 'city': city, 'state': state,
            'zip': zip_code, 'pastor': pastor, 'phone': phone,
            'website': website, 'email': email,
        })
    
    print(f'Found {len(kansas_churches)} churches in Kansas directory')
    for ch in kansas_churches:
        log(f'  {ch["name"]} | {ch["city"]}, {ch["state"]} | {ch["pastor"]} | {ch["website"]}')
        upsert_church(ch['name'], ch['city'], ch['state'], address=ch['address'],
                     website=ch['website'], email=ch['email'], phone=ch['phone'],
                     district='Kansas', pastor=ch['pastor'])
    
except Exception as e:
    print(f'  ERROR scraping Kansas: {e}')

# ── 2. Scrape South Carolina District (Nucleus) ─────────────────────────
print('\n--- 2. South Carolina District (scwesleyan.org/church-directory) ---')
try:
    html = fetch('https://www.scwesleyan.org/church-directory')
    
    # Extract church blocks from the clean HTML paragraphs
    # Pattern: Church name in bold/generic, then address, then email, phone, website
    lines = re.sub(r'<[^>]+>', '\n', html).split('\n')
    lines = [l.strip() for l in lines if l.strip()]
    
    sc_churches = []
    i = 0
    while i < len(lines):
        line = lines[i]
        # Look for a church name line (contains "WESLEYAN" or "CHURCH" in caps)
        if re.search(r'(?:WESLEYAN|CHURCH|CHAPEL|MINISTRY)', line) and len(line) > 5 and len(line) < 100:
            name = line.strip()
            # Skip if it's a header/section marker
            if name in ['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H', 'I', 'J', 'K', 'L', 'M',
                        'N', 'O', 'P', 'Q', 'R', 'S', 'T', 'U', 'V', 'W', 'X', 'Y', 'Z']:
                i += 1
                continue
            
            address = ''
            phone = ''
            email = ''
            website = ''
            
            # Next few lines contain address, email, phone, website
            j = i + 1
            while j < len(lines) and j < i + 8:
                next_line = lines[j]
                if next_line.startswith('A ') or next_line.startswith('B ') or next_line.startswith('C '):
                    break  # hit next section
                if 'Email:' in next_line:
                    email = next_line.replace('Email:', '').strip()
                elif 'Phone:' in next_line:
                    phone = next_line.replace('Phone:', '').strip()
                elif 'Website:' in next_line:
                    website = next_line.replace('Website:', '').strip()
                elif re.match(r'^[\d]+\s', next_line) or next_line.startswith('Mailing'):
                    address = next_line if not address else address + '; ' + next_line
                elif 'PO Box' in next_line or re.match(r'^[\d]', next_line):
                    address = next_line if not address else address + '; ' + next_line
                j += 1
            
            # Extract city from address
            city = ''
            city_match = re.search(r',\s*([A-Za-z\s]+),\s*SC\s', address)
            if city_match:
                city = city_match.group(1).strip()
            
            sc_churches.append({
                'name': name, 'address': address, 'phone': phone,
                'email': email, 'website': website,
                'city': city, 'state': 'SC'
            })
            i = j
        else:
            i += 1
    
    print(f'Found {len(sc_churches)} churches in SC directory')
    for ch in sc_churches:
        log(f'  {ch["name"]} | {ch["address"]} | {ch["phone"]}')
        upsert_church(ch['name'], ch['city'], 'SC', address=ch['address'],
                     phone=ch['phone'], email=ch['email'],
                     website=ch['website'], district='South Carolina')
    
except Exception as e:
    print(f'  ERROR scraping South Carolina: {e}')
    import traceback; traceback.print_exc()

# ── 3. Scrape South Coastal District (Weebly) ───────────────────────────
print('\n--- 3. South Coastal District (southcoastalwesleyan.com/our-churches) ---')
try:
    html = fetch('https://www.southcoastalwesleyan.com/our-churches')
    text = re.sub(r'<[^>]+>', '\n', html)
    text = re.sub(r'&#8203;', '', text)
    lines = [l.strip() for l in text.split('\n') if l.strip()]
    
    coastal_churches = []
    i = 0
    while i < len(lines):
        line = lines[i]
        # Church names: end with "Church" or "Church," and are not generic
        if re.search(r'(?:Wesleyan|Church)\s*$', line) and len(line) > 5 and len(line) < 80:
            name = line.rstrip(',').strip()
            # Skip known non-church entries
            if name in ['Our Churches', 'Church Planting', 'Ministerial Development']:
                i += 1
                continue
            
            address = ''
            pastor = ''
            website = ''
            
            j = i + 1
            while j < len(lines) and j < i + 5:
                next_line = lines[j]
                if re.search(r'(?:Wesleyan|Church)\s*$', next_line) and next_line != line:
                    break
                if 'Pastor' in next_line:
                    pastor = next_line
                elif next_line.startswith('http') or next_line.startswith('www'):
                    website = next_line if not website.startswith('http') else next_line
                elif 'Church Rd' in next_line or 'St' in next_line or 'Blvd' in next_line:
                    address = next_line
                elif ',' in next_line and len(next_line) < 50:
                    address = next_line if not address else address
                j += 1
            
            # Extract city/state from address
            city, state_code = '', ''
            addr_state_match = re.search(r',\s*([A-Z]{2})\s+\d', address)
            if addr_state_match:
                state_code = addr_state_match.group(1)
                city_match = re.search(r',\s*([^,]+),\s*[A-Z]{2}\s', address)
                if city_match:
                    city = city_match.group(1).strip()
            elif ',' in address:
                parts = address.rsplit(',', 1)
                state_code = parts[-1].strip()[:2].upper() if len(parts) > 1 else ''
                city = parts[0].rsplit(',', 1)[-1].strip() if ',' in parts[0] else ''
            
            coastal_churches.append({
                'name': name, 'address': address, 'pastor': pastor,
                'website': website, 'city': city, 'state': state_code
            })
            i = j
        else:
            i += 1
    
    print(f'Found {len(coastal_churches)} churches in South Coastal directory')
    for ch in coastal_churches:
        log(f'  {ch["name"]} | {ch["address"]} | {ch["city"]}, {ch["state"]} | {ch["pastor"]}')
        upsert_church(ch['name'], ch['city'], ch['state'], address=ch['address'],
                     website=ch['website'], district='South Coastal',
                     pastor=ch['pastor'])
    
except Exception as e:
    print(f'  ERROR scraping South Coastal: {e}')

# ── 4. Classify existing Wesleyan contacts by district ──────────────────
print('\n--- 4. Classify existing Wesleyan records by district ---')
c.execute("""
    SELECT id, name, city, state, district FROM churches
    WHERE denomination = 'Wesleyan Church' AND (district IS NULL OR district = '')
    AND state != ''
""")
unclassified = c.fetchall()
print(f'Found {len(unclassified)} unclassified Wesleyan records')

classified = 0
for row in unclassified:
    church_id, name, city, state_code, current_district = row
    # Find district by state
    for dname, dinfo in DISTRICTS.items():
        if state_code in dinfo['states']:
            if DRY_RUN:
                log(f'  [DRY] Would set district={dname} for ID={church_id}: {name} ({city}, {state_code})')
            else:
                c.execute("UPDATE churches SET district = ?, family = 'wesleyan' WHERE id = ?", (dname, church_id))
            classified += 1
            break

print(f'Classified {classified} records by district')

# ── 5. Ensure family is set for all Wesleyan records ────────────────────
print('\n--- 5. Set family=wesleyan for all Wesleyan denomination records ---')
c.execute("SELECT COUNT(*) FROM churches WHERE denomination = 'Wesleyan Church' AND (family IS NULL OR family = '')")
need_family = c.fetchone()[0]
if need_family > 0:
    if DRY_RUN:
        log(f'[DRY] Would set family=wesleyan for {need_family} records')
    else:
        c.execute("UPDATE churches SET family = 'wesleyan' WHERE denomination = 'Wesleyan Church' AND (family IS NULL OR family = '')")
        log(f'Set family=wesleyan for {c.rowcount} records')
else:
    log('All Wesleyan records already have family set')

# ── Summary ─────────────────────────────────────────────────────────────
print('\n' + '=' * 60)
c.execute("SELECT COUNT(*) FROM churches WHERE family = 'wesleyan'")
total = c.fetchone()[0]
print(f'Total Wesleyan family records: {total:,}')

c.execute("SELECT COUNT(*) FROM churches WHERE family = 'wesleyan' AND district != ''")
with_district = c.fetchone()[0]
print(f'With district assigned: {with_district:,}')

c.execute("SELECT district, COUNT(*) FROM churches WHERE family = 'wesleyan' AND district != '' GROUP BY district ORDER BY COUNT(*) DESC")
print('\nBy district:')
for r in c.fetchall():
    print(f'  {r[0]}: {r[1]}')

if not DRY_RUN:
    conn.commit()
    print('\nChanges COMMITTED.')
else:
    print('\nDry run — no changes made. Run without --dry-run to apply.')

conn.close()
