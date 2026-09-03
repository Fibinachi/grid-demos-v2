"""Scrape visitamosque.us using Playwright — state pages → mosque detail pages."""
import asyncio, re, sqlite3
from datetime import datetime, timezone
from playwright.async_api import async_playwright

NOW = datetime.now(timezone.utc).isoformat()
SOURCE = "visitamosque_us"
DB = "E:/grid/churches.db"
BASE = "https://visitamosque.us"

# State slugs from the footer + known states
STATE_SLUGS = [
    "arizona", "california", "connecticut", "district-of-columbia", 
    "florida", "georgia", "hawaii", "illinois", "kansas", "louisiana",
    "maryland", "massachusetts", "michigan", "minnesota", "missouri",
    "nevada", "new-jersey", "new-york", "north-carolina", "ohio",
    "oregon", "pennsylvania", "texas", "virginia-va", "washington",
    "wisconsin",
]

async def scrape():
    mosques = []
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        
        # ── Step 1: Get all mosque URLs from state pages ──
        mosque_urls = set()
        for slug in STATE_SLUGS:
            try:
                url = f"{BASE}/mosque-item/{slug}/"
                await page.goto(url, timeout=15000)
                await page.wait_for_timeout(1000)
                
                # Extract mosque links
                links = await page.evaluate("""() => {
                    return Array.from(document.querySelectorAll('a[href*="mosque-item"]'))
                        .map(a => a.href)
                        .filter(h => !h.endsWith('/' + window.location.pathname.split('/').filter(Boolean).pop() + '/'));
                }""")
                mosque_urls.update(links)
                print(f"  {slug}: {len(links)} mosques")
            except Exception as e:
                print(f"  {slug}: ERROR - {e}")
        
        print(f"\n  Total mosque URLs: {len(mosque_urls)}")
        
        # ── Step 2: Scrape individual mosque pages ──
        for i, url in enumerate(sorted(mosque_urls)):
            try:
                await page.goto(url, timeout=15000)
                await page.wait_for_timeout(500)
                
                data = await page.evaluate("""() => {
                    const name = document.querySelector('h2')?.textContent?.trim() || '';
                    const iframe = document.querySelector('iframe[src*="google.com/maps"]');
                    let src = iframe ? iframe.src : '';
                    let lat = '', lon = '';
                    // Extract coordinates from maps embed URL
                    const llMatch = src.match(/!2d([-\d.]+)!3d([-\d.]+)/);
                    const qMatch = src.match(/q=([-\d.]+),([-\d.]+)/);
                    const pbMatch = src.match(/pb=!1m14.*?!3d([-\d.]+)!4d([-\d.]+)/);
                    if (llMatch) { lon = llMatch[1]; lat = llMatch[2]; }
                    else if (qMatch) { lat = qMatch[1]; lon = qMatch[2]; }
                    else if (pbMatch) { lat = pbMatch[1]; lon = pbMatch[2]; }
                    
                    return { name, lat: parseFloat(lat) || null, lon: parseFloat(lon) || null, iframe_src: src.substring(0, 200) };
                }""")
                
                if data['name']:
                    mosques.append({
                        'name': data['name'],
                        'lat': data['lat'],
                        'lon': data['lon'],
                        'url': url,
                    })
                
                if (i + 1) % 20 == 0:
                    print(f"  {i+1}/{len(mosque_urls)} scraped")
                    
            except Exception as e:
                print(f"  {url}: ERROR - {e}")
        
        await browser.close()
    
    return mosques

async def main():
    print("Step 1: Finding mosque URLs from state pages...")
    mosques = await scrape()
    print(f"\nStep 2: Scraped {len(mosques)} mosques with data")
    
    with_coords = sum(1 for m in mosques if m['lat'])
    print(f"  With coordinates: {with_coords}")
    
    # Sample
    for m in mosques[:5]:
        print(f"  {m['name'][:50]:50s} | {m['lat']} {m['lon']}")
    
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
    
    for m in mosques:
        lat, lon = m['lat'], m['lon']
        
        # Holy site
        if lat and lon:
            gl, gn = round(lat, 4), round(lon, 4)
            if (gl, gn) not in grid:
                c.execute("""
                    INSERT INTO holy_sites 
                    (name, faith, tradition, country, lat, lon, source_primary, is_landmark, landmark_type, confidence_score)
                    VALUES (?,?,?,?,?,?,?,?,?,?)
                """, (m['name'][:500], 'Islam', 'Ahmadiyya', 'US', lat, lon, SOURCE, 0, 'mosque', 0.9))
                hs_site_id = c.lastrowid
                grid.add((gl, gn))
            else:
                # Get existing site_id
                c.execute("SELECT site_id FROM holy_sites WHERE ROUND(lat,4)=? AND ROUND(lon,4)=? LIMIT 1", (gl, gn))
                existing = c.fetchone()
                if existing:
                    hs_site_id = existing[0]
                else:
                    # Just insert anyway
                    c.execute("""
                        INSERT INTO holy_sites 
                        (name, faith, tradition, country, lat, lon, source_primary, is_landmark, landmark_type, confidence_score)
                        VALUES (?,?,?,?,?,?,?,?,?,?)
                    """, (m['name'][:500], 'Islam', 'Ahmadiyya', 'US', lat, lon, SOURCE, 0, 'mosque', 0.9))
                    hs_site_id = c.lastrowid
                    grid.add((gl, gn))
        else:
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
            (name, faith, denomination, country, latitude, longitude, source, holy_site_id, landmark_type, mosque_type)
            VALUES (?,?,?,?,?,?,?,?,?,?)
        """, (m['name'][:500], 'Islam', 'Ahmadiyya', 'US', lat, lon, SOURCE, hs_site_id, 'mosque', 'ahmadiyya_mosque'))
        church_id = c.lastrowid
        ch_inserted += 1
        
        # Contacts (website URL)
        c.execute("""
            INSERT INTO church_contacts 
            (church_id, website, website_source, website_scrape_status)
            VALUES (?,?,?,?)
        """, (church_id, m['url'], SOURCE, 'found'))
    
    conn.commit()
    
    print(f"\n=== Results ===")
    print(f"  Mosques: {len(mosques)}")
    print(f"  holy_sites: {hs_inserted}")
    print(f"  churches: {ch_inserted}")
    print(f"  with coords: {with_coords}")
    
    c.execute("SELECT COUNT(*) FROM churches WHERE source=?", (SOURCE,))
    print(f"  DB total: {c.fetchone()[0]}")
    
    c.execute("""
        INSERT INTO provenance_log 
        (source, script_name, started_at, completed_at, churches_inserted,
         fields_populated, records_attempted, records_matched, status, notes)
        VALUES(?,?,?,?,?,?,?,?,'completed',?)
    """, (SOURCE, "scrape_visitamosque_playwright.py", NOW, datetime.now(timezone.utc).isoformat(),
         ch_inserted, "name,lat,lon,denomination,mosque_type,website",
         len(mosques), ch_inserted,
         f"visitamosque.us: {len(mosques)} Ahmadiyya mosques scraped via Playwright"))
    
    conn.commit()
    conn.close()
    print("\nDone.")

asyncio.run(main())
