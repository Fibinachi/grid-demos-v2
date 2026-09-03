"""Scrape all ~2,300 KY Baptist Convention churches - FIXED VERSION"""
import urllib.request, re, ssl, sqlite3, time
from concurrent.futures import ThreadPoolExecutor as TPE, as_completed

DB = r'E:\grid\churches.db'
UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

DENOM = "Southern Baptist Convention"
FAMILY = "Baptist"
SOURCE = "Kentucky Baptist Convention (kybaptist.org)"

def fetch_text(url, timeout=15):
    req = urllib.request.Request(url, headers={'User-Agent': UA})
    resp = urllib.request.urlopen(req, timeout=timeout, context=ctx)
    return resp.read().decode('utf-8', 'replace')

# Step 1: Scrape all listing pages
print("=== STEP 1: Scraping listing pages ===")
all_churches = []
total_pages = 46

for page in range(1, total_pages + 1):
    url = f'http://www.kybaptist.org/churches/page/{page}/' if page > 1 else 'http://www.kybaptist.org/churches/'
    try:
        html = fetch_text(url)
    except:
        print(f'  Page {page}: ERROR')
        continue
    
    entries = re.findall(
        r'<a class="church" href="(https://www\.kybaptist\.org/churches/[^/]+/)">'
        r'\s*<h6 class="church-name">([^<]+)</h6>'
        r'\s*<span class="church-address">([\s\S]*?)</span>',
        html
    )
    
    for detail_url, name, address_block in entries:
        name = name.strip()
        addr_lines = [l.strip() for l in address_block.split('<br') if l.strip()]
        last_line = addr_lines[-1].strip() if addr_lines else ''
        
        zip_match = re.search(r'(\d{5}(?:-\d{4})?)$', last_line)
        zip_code = zip_match.group(1) if zip_match else ''
        state_match = re.search(r'([A-Z]{2})\s+\d', last_line)
        state = state_match.group(1) if state_match else ''
        city = ''
        if state:
            city = re.sub(r'\s*' + state + r'\s*' + re.escape(zip_code) + r'$', '', last_line).strip()
            city = re.sub(r',\s*$', '', city).strip()
        street = ' '.join(addr_lines[:-1]).strip() if len(addr_lines) > 1 else ''
        
        all_churches.append({
            'name': name, 'street': street, 'city': city,
            'state': state, 'zip': zip_code, 'detail_url': detail_url,
        })
    
    print(f'  Page {page}: {len(entries)} churches')

print(f'\nTotal churches: {len(all_churches)}')

# Step 2: Scrape detail pages
print('\n=== STEP 2: Scraping detail pages ===')

def scrape_detail(church):
    try:
        html = fetch_text(church['detail_url'], timeout=15)
    except:
        church['website'] = ''
        church['phone'] = ''
        church['email'] = ''
        return church
    
    wm = re.search(r'class="church_website"[^>]*>.*?<a href="([^"]+)"', html, re.DOTALL)
    church['website'] = wm.group(1).strip() if wm else ''
    
    pm = re.search(r'class="church_phone"[^>]*>.*?<a href="tel:([^"]+)">([^<]+)</a>', html, re.DOTALL)
    church['phone'] = pm.group(1).strip() if pm else ''
    
    em = re.search(r'class="church_email"[^>]*>.*?<a href="mailto:([^"]+)"', html, re.DOTALL)
    if em:
        church['email'] = em.group(1).strip()
    else:
        em2 = re.search(r'class="church_email"[^>]*>([\s\S]*?)</div>', html, re.DOTALL)
        if em2:
            email_text = re.sub(r'<[^>]+>', '', em2.group(1))
            em3 = re.search(r'[\w.+-]+@[\w-]+\.[\w.]+', email_text)
            church['email'] = em3.group(0) if em3 else ''
        else:
            church['email'] = ''
    
    return church

all_detailed = []
for i in range(0, len(all_churches), 50):
    batch = all_churches[i:i+50]
    with TPE(max_workers=20) as exe:
        futures = {exe.submit(scrape_detail, c): c for c in batch}
        for f in as_completed(futures):
            try:
                all_detailed.append(f.result())
            except:
                all_detailed.append(futures[f])
    print(f'  Batch {i//50 + 1}/{len(all_churches)//50 + 1}: {len(batch)} ({len(all_detailed)} total)')

with_web = sum(1 for c in all_detailed if c.get('website'))
with_ph = sum(1 for c in all_detailed if c.get('phone'))
with_em = sum(1 for c in all_detailed if c.get('email'))
print(f'\nStats: {len(all_detailed)} total, {with_web} websites, {with_ph} phones, {with_em} emails')

# Step 3: Import
print('\n=== STEP 3: Importing ===')
conn = sqlite3.connect(DB)
c = conn.cursor()

imported = 0
skipped = 0
for ch in all_detailed:
    name = ch['name']
    parts = [p for p in [ch.get('street',''), ch.get('city',''), ch.get('state',''), ch.get('zip','')] if p]
    address = ', '.join(parts)
    
    c.execute("SELECT COUNT(*) FROM churches WHERE name = ? AND source = ?", (name, SOURCE))
    if c.fetchone()[0] > 0:
        skipped += 1
        continue
    
    try:
        c.execute("""
            INSERT INTO churches 
            (name, address, city, state, zip, website, phone, email,
             denomination, family, source)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (name, address, ch.get('city',''), ch.get('state',''), ch.get('zip',''),
              ch.get('website',''), ch.get('phone',''), ch.get('email',''),
              DENOM, FAMILY, SOURCE))
        imported += 1
    except Exception as e:
        print(f'  Insert error for {name}: {e}')
        skipped += 1

conn.commit()
conn.close()

print(f'\nImported: {imported}')
print(f'Skipped: {skipped}')
