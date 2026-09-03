"""Quick sync Playwright scrape of visitamosque.us."""
import re, sqlite3, time
from datetime import datetime, timezone
from playwright.sync_api import sync_playwright

NOW = datetime.now(timezone.utc).isoformat()
SOURCE = "visitamosque_us"
DB = "E:/grid/churches.db"
TIMEOUT = 12000

states = [
    "arizona", "california", "connecticut", "district-of-columbia",
    "florida", "georgia", "hawaii", "illinois", "kansas", "louisiana",
    "maryland", "massachusetts", "michigan", "minnesota", "missouri",
    "nevada", "new-jersey", "new-york", "north-carolina", "ohio",
    "oregon", "pennsylvania", "texas", "virginia-va", "washington", "wisconsin",
]

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page()
    
    # Step 1: Get mosque URLs
    urls = set()
    for slug in states:
        try:
            page.goto(f"https://visitamosque.us/mosque-item/{slug}/", timeout=TIMEOUT)
            page.wait_for_timeout(1000)
            links = page.evaluate("""() => {
                return [...document.querySelectorAll('a[href*="mosque-item"]')]
                    .map(a => a.href)
                    .filter(h => {
                        const parts = h.split('/').filter(Boolean);
                        return parts.length >= 5;
                    });
            }""")
            urls.update(links)
            print(f"  {slug}: {len(links)} links")
        except Exception as e:
            print(f"  {slug}: SKIP - {e}")
    
    urls = sorted(urls)
    print(f"\n  Total unique mosques: {len(urls)}")
    
    # Step 2: Scrape individual pages
    mosques = []
    for i, url in enumerate(urls):
        try:
            page.goto(url, timeout=TIMEOUT)
            page.wait_for_timeout(600)
            data = page.evaluate("""() => {
                const h2 = document.querySelector('h2');
                if (!h2) return null;
                const name = h2.textContent.trim();
                const iframe = document.querySelector('iframe[src*="maps"]');
                let lat = null, lon = null;
                if (iframe) {
                    const m = iframe.src.match(/!2d([-\\d.]+)!3d([-\\d.]+)/);
                    if (m) { lon = parseFloat(m[1]); lat = parseFloat(m[2]); }
                }
                return {name, lat, lon};
            }""")
            if data and data['name']:
                mosques.append(data)
            if (i+1) % 20 == 0:
                print(f"  {i+1}/{len(urls)} scraped")
        except Exception as e:
            print(f"  SKIP: {e}")
    
    browser.close()
    print(f"\n  Scraped {len(mosques)} mosques, {sum(1 for m in mosques if m['lat'])} with coords")

# Insert
if mosques:
    conn = sqlite3.connect(DB)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=30000")
    c = conn.cursor()
    
    c.execute("SELECT ROUND(lat,4), ROUND(lon,4) FROM holy_sites WHERE lat IS NOT NULL")
    grid = set(c.fetchall())
    
    ch = hs = 0
    for m in mosques:
        lat, lon = m.get('lat'), m.get('lon')
        if lat and lon:
            gl, gn = round(lat,4), round(lon,4)
            if (gl, gn) not in grid:
                c.execute("INSERT INTO holy_sites(name,faith,tradition,country,lat,lon,source_primary,is_landmark,landmark_type,confidence_score) VALUES(?,?,?,?,?,?,?,?,?,?)",
                         (m['name'][:500],'Islam','Ahmadiyya','US',lat,lon,SOURCE,0,'mosque',0.9))
                grid.add((gl,gn))
            hs_id = c.lastrowid or 0
        else:
            c.execute("INSERT INTO holy_sites(name,faith,tradition,country,source_primary,is_landmark,landmark_type,confidence_score) VALUES(?,?,?,?,?,?,?,?)",
                     (m['name'][:500],'Islam','Ahmadiyya','US',SOURCE,0,'mosque',0.9))
            hs_id = c.lastrowid or 0
        hs += 1
        
        c.execute("INSERT INTO churches(name,faith,denomination,country,latitude,longitude,source,holy_site_id,landmark_type,mosque_type) VALUES(?,?,?,?,?,?,?,?,?,?)",
                 (m['name'][:500],'Islam','Ahmadiyya','US',lat,lon,SOURCE,hs_id,'mosque','ahmadiyya_mosque'))
        ch += 1
    
    conn.commit()
    c.execute("INSERT INTO provenance_log(source,script_name,started_at,completed_at,churches_inserted,fields_populated,records_attempted,records_matched,status,notes) VALUES(?,?,?,?,?,?,?,?,'completed',?)",
             (SOURCE,"scrape_visitamosque_sync.py",NOW,datetime.now(timezone.utc).isoformat(),ch,"name,lat,lon,denomination,mosque_type",len(mosques),ch,f"visitamosque.us: {len(mosques)} mosques"))
    conn.commit()
    conn.close()
    print(f"Inserted: {ch} churches, {hs} holy_sites")
else:
    print("Nothing to insert")
