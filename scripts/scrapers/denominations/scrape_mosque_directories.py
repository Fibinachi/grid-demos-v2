"""Scrape multiple mosque directories with Playwright."""
import asyncio, re, sqlite3
from datetime import datetime, timezone
from playwright.async_api import async_playwright

NOW = datetime.now(timezone.utc).isoformat()
DB = "E:/grid/churches.db"
TIMEOUT = 10000

async def scrape_visitamosque():
    """Scrape visitamosque.us — Ahmadiyya mosques."""
    SOURCE = "visitamosque_us"
    state_slugs = [
        "arizona", "california", "connecticut", "district-of-columbia",
        "florida", "georgia", "hawaii", "illinois", "kansas", "louisiana",
        "maryland", "massachusetts", "michigan", "minnesota", "missouri",
        "nevada", "new-jersey", "new-york", "north-carolina", "ohio",
        "oregon", "pennsylvania", "texas", "virginia-va", "washington", "wisconsin",
    ]
    
    mosques = []
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        
        # Get mosque URLs
        mosque_urls = set()
        for slug in state_slugs:
            try:
                await page.goto(f"https://visitamosque.us/mosque-item/{slug}/", timeout=TIMEOUT)
                await page.wait_for_timeout(800)
                links = await page.evaluate("""() => {
                    return Array.from(document.querySelectorAll('a[href*="mosque-item"]'))
                        .map(a => a.href)
                        .filter(h => h.includes('/mosque-item/') && h.split('/').filter(Boolean).length >= 5);
                }""")
                mosque_urls.update(links)
            except Exception as e:
                print(f"  {slug}: {e}")
        
        print(f"  visitamosque: {len(mosque_urls)} URLs")
        
        # Scrape individual pages
        for i, url in enumerate(sorted(mosque_urls)):
            try:
                await page.goto(url, timeout=TIMEOUT)
                await page.wait_for_timeout(500)
                data = await page.evaluate("""() => {
                    const h2 = document.querySelector('h2');
                    if (!h2) return null;
                    const name = h2.textContent.trim();
                    const iframe = document.querySelector('iframe[src*="maps"]');
                    let lat = null, lon = null;
                    if (iframe) {
                        const src = iframe.src;
                        const m = src.match(/!2d([-\d.]+)!3d([-\d.]+)/) || src.match(/q=([-\d.]+),([-\d.]+)/);
                        if (m) { lon = parseFloat(m[1]); lat = parseFloat(m[2]); }
                    }
                    return { name, lat, lon };
                }""")
                if data and data['name']:
                    mosques.append({'name': data['name'], 'lat': data['lat'], 'lon': data['lon'], 'url': url, 'source': SOURCE, 'denom': 'Ahmadiyya', 'country': 'US'})
                if (i+1) % 30 == 0:
                    print(f"    {i+1}/{len(mosque_urls)}")
            except Exception as e:
                print(f"    SKIP {url}: {e}")
        
        await browser.close()
    return mosques

async def scrape_mosquedirectory_uk():
    """Scrape mosquedirectory.co.uk."""
    SOURCE = "mosquedirectory_uk"
    mosques = []
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        
        try:
            await page.goto("https://www.mosquedirectory.co.uk/", timeout=TIMEOUT)
            await page.wait_for_timeout(2000)
            
            # Try to find listing page links
            links = await page.evaluate("""() => {
                return Array.from(document.querySelectorAll('a'))
                    .map(a => ({href: a.href, text: a.textContent.trim().substring(0, 50)}))
                    .filter(l => l.href.includes('mosque') || l.href.includes('masjid') || l.href.includes('listing'));
            }""")
            print(f"  mosquedirectory.co.uk: {len(links)} links found")
            
            for l in links[:10]:
                print(f"    {l['text'][:50]}: {l['href'][:80]}")
            
        except Exception as e:
            print(f"  mosquedirectory.co.uk ERROR: {e}")
        
        await browser.close()
    return mosques

async def scrape_australia():
    """Scrape mosque-finder.com.au."""
    SOURCE = "mosque_finder_au"
    mosques = []
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        
        try:
            await page.goto("https://www.mosque-finder.com.au/", timeout=TIMEOUT)
            await page.wait_for_timeout(2000)
            
            text = await page.text_content('body')
            # Check if it has a search form or listing
            if 'search' in text.lower() or 'find' in text.lower():
                print(f"  mosque-finder.com.au: search-based site, {len(text):,} chars")
                # Try state-based searches
                states = ['NSW', 'VIC', 'QLD', 'WA', 'SA', 'TAS', 'ACT', 'NT']
                for state in states:
                    try:
                        await page.fill('input[type="text"], input[type="search"]', state)
                        await page.keyboard.press('Enter')
                        await page.wait_for_timeout(2000)
                        results = await page.text_content('body')
                        if 'mosque' in results.lower():
                            print(f"    {state}: results found")
                    except:
                        pass
            else:
                links = await page.evaluate("""() => {
                    return Array.from(document.querySelectorAll('a'))
                        .map(a => a.href)
                        .filter(h => h.includes('mosque') || h.includes('masjid'));
                }""")
                print(f"  mosque-finder.com.au: {len(links)} mosque links")
                
        except Exception as e:
            print(f"  mosque-finder.com.au ERROR: {e}")
        
        await browser.close()
    return mosques

def insert_into_db(all_mosques):
    """Insert scraped mosques into DB."""
    conn = sqlite3.connect(DB)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=30000")
    c = conn.cursor()
    
    c.execute("SELECT ROUND(lat,4), ROUND(lon,4) FROM holy_sites WHERE lat IS NOT NULL")
    grid = set(c.fetchall())
    
    total_ch = 0
    total_hs = 0
    
    for m in all_mosques:
        lat, lon = m.get('lat'), m.get('lon')
        source = m['source']
        
        if lat and lon:
            gl, gn = round(lat, 4), round(lon, 4)
            if (gl, gn) not in grid:
                c.execute("INSERT INTO holy_sites (name,faith,tradition,country,lat,lon,source_primary,is_landmark,landmark_type,confidence_score) VALUES (?,?,?,?,?,?,?,?,?,?)",
                         (m['name'][:500], 'Islam', m.get('denom',''), m['country'], lat, lon, source, 0, 'mosque', 0.9))
                grid.add((gl, gn))
            hs_site_id = c.lastrowid
        else:
            c.execute("INSERT INTO holy_sites (name,faith,tradition,country,source_primary,is_landmark,landmark_type,confidence_score) VALUES (?,?,?,?,?,?,?,?)",
                     (m['name'][:500], 'Islam', m.get('denom',''), m['country'], source, 0, 'mosque', 0.9))
            hs_site_id = c.lastrowid
        total_hs += 1
        
        c.execute("INSERT INTO churches (name,faith,denomination,country,latitude,longitude,source,holy_site_id,landmark_type) VALUES (?,?,?,?,?,?,?,?,?)",
                 (m['name'][:500], 'Islam', m.get('denom',''), m['country'], lat, lon, source, hs_site_id, 'mosque'))
        church_id = c.lastrowid
        total_ch += 1
        
        if m.get('url'):
            c.execute("INSERT INTO church_contacts (church_id,website,website_source,website_scrape_status) VALUES (?,?,?,?)",
                     (church_id, m['url'], source, 'found'))
    
    conn.commit()
    
    # Provenance
    c.execute("INSERT INTO provenance_log (source,script_name,started_at,completed_at,churches_inserted,fields_populated,records_attempted,records_matched,status,notes) VALUES(?,?,?,?,?,?,?,?,'completed',?)",
             ("multi_directory", "scrape_mosque_directories.py", NOW, datetime.now(timezone.utc).isoformat(),
              total_ch, "name,lat,lon,denomination,country", len(all_mosques), total_ch,
              f"Multi-directory scrape: {len(all_mosques)} mosques total"))
    
    source_counts = {}
    for m in all_mosques:
        source_counts[m['source']] = source_counts.get(m['source'], 0) + 1
    
    conn.commit()
    conn.close()
    
    print(f"\n=== DB Insert ===")
    print(f"  Total churches: {total_ch}")
    print(f"  Total holy_sites: {total_hs}")
    for src, cnt in source_counts.items():
        print(f"  {src}: {cnt}")

async def main():
    print("Scraping mosque directories...\n")
    
    all_mosques = []
    
    # visitamosque.us
    print("[1/3] visitamosque.us")
    vam = await scrape_visitamosque()
    all_mosques.extend(vam)
    print(f"  Got {len(vam)} mosques\n")
    
    # UK
    print("[2/3] mosquedirectory.co.uk")
    uk = await scrape_mosquedirectory_uk()
    all_mosques.extend(uk)
    print(f"  Got {len(uk)} mosques\n")
    
    # AU
    print("[3/3] mosque-finder.com.au")
    au = await scrape_australia()
    all_mosques.extend(au)
    print(f"  Got {len(au)} mosques\n")
    
    if all_mosques:
        insert_into_db(all_mosques)
    else:
        print("No mosques scraped!")

asyncio.run(main())
