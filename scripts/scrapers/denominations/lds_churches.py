"""LDS Ward Scraper - searches cities for wards, scrapes details, imports to DB."""
import json, os, sqlite3
from playwright.sync_api import sync_playwright

PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if not os.path.exists(os.path.join(PROJECT_DIR, 'churches.db')):
    PROJECT_DIR = os.path.expanduser('~/grantwizard')
    if not os.path.exists(os.path.join(PROJECT_DIR, 'churches.db')):
        PROJECT_DIR = os.getcwd()
OUT_DIR = os.path.join(PROJECT_DIR, 'data', 'denom')
DB_PATH = os.path.join(PROJECT_DIR, 'churches.db')
os.makedirs(OUT_DIR, exist_ok=True)

CITIES = [
    "Columbia SC", "Charleston SC", "Greenville SC", "Spartanburg SC",
    "Anderson SC", "Rock Hill SC", "Florence SC", "Myrtle Beach SC",
    "Sumter SC", "Greenwood SC", "Aiken SC", "Beaufort SC",
    "Orangeburg SC", "Clemson SC", "Camden SC", "Georgetown SC",
    "Conway SC", "Gaffney SC", "Easley SC", "Newberry SC",
    "Hartsville SC", "Laurens SC", "Abbeville SC", "Union SC",
    "Chester SC", "Moncks Corner SC", "Lancaster SC", "Cheraw SC",
    "Dillon SC", "Marion SC", "Walterboro SC", "North Augusta SC",
    "Lexington SC", "Irmo SC", "Simpsonville SC", "Greer SC",
    "Seneca SC", "Fort Mill SC", "York SC", "Bennettsville SC",
    "Kingstree SC", "Winnsboro SC",
]

def run():
    all_wards = {}
    all_stakes = {}

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        ctx = browser.new_context()
        page = ctx.new_page()

        # Phase 1: Search cities to find wards and stakes
        for city in CITIES:
            try:
                page.goto('https://maps.churchofjesuschrist.org/', timeout=15000, wait_until='domcontentloaded')
                page.wait_for_timeout(2000)
                srch = page.locator('input[type="search"]')
                if srch.count() == 0: continue
                srch.click()
                page.wait_for_timeout(200)
                srch.fill('')
                srch.type(city, delay=20)
                page.wait_for_timeout(1500)
                srch.press('Enter')
                page.wait_for_timeout(3000)
                links = page.evaluate("""() => Array.from(document.querySelectorAll('a[href*="/wards/"], a[href*="/stakes/"]')).map(a => ({t: a.textContent.trim(), h: a.getAttribute('href')}))""")
                for link in links:
                    if '/wards/' in link['h']:
                        wid = link['h'].split('/wards/')[1].split('/')[0]
                        if wid not in all_wards:
                            all_wards[wid] = {'name': link['t'], 'id': wid}
                    elif '/stakes/' in link['h']:
                        sid = link['h'].split('/stakes/')[1].split('/')[0]
                        if sid not in all_stakes:
                            all_stakes[sid] = {'name': link['t'], 'id': sid}
                print("  %s: wards=%d stakes=%d" % (city.split()[0], len(all_wards), len(all_stakes)))
            except:
                pass

        print("\n=== Phase 2: Scraping stake pages for more wards ===")
        for sid in list(all_stakes.keys()):
            try:
                page.goto('https://maps.churchofjesuschrist.org/stakes/' + sid, timeout=15000, wait_until='domcontentloaded')
                page.wait_for_timeout(2000)
                links = page.evaluate("""() => Array.from(document.querySelectorAll('a[href*="/wards/"]')).map(a => ({t: a.textContent.trim(), h: a.getAttribute('href')}))""")
                for link in links:
                    wid = link['h'].split('/wards/')[1].split('/')[0]
                    if wid not in all_wards:
                        all_wards[wid] = {'name': link['t'], 'id': wid, 'stake': all_stakes[sid]['name']}
                    else:
                        all_wards[wid]['stake'] = all_stakes[sid]['name']
                print("  Stake %s: +%d wards (total %d)" % (all_stakes[sid]['name'][:25], len(links), len(all_wards)))
            except:
                pass

        # Phase 3: Scrape ward detail pages
        print("\n=== Phase 3: Scraping %d ward details ===" % len(all_wards))
        count = 0
        for wid, winfo in all_wards.items():
            try:
                page.goto('https://maps.churchofjesuschrist.org/wards/' + wid, timeout=15000, wait_until='domcontentloaded')
                page.wait_for_timeout(1000)
                details = page.evaluate("""() => {
                    const t = document.body.innerText;
                    const lines = t.split('\\n').map(l => l.trim());
                    let addr = '', phone = '', stake = '', time = '', bishop = '';
                    for (let i = 0; i < lines.length; i++) {
                        const l = lines[i];
                        if (l.includes('South Carolina') && l.match(/\\d{5}/)) addr = l;
                        if (l.startsWith('+1') && l.includes('-')) phone = l;
                        if (l.includes('Stake')) stake = l;
                        if (l.includes('Bishop')) bishop = l;
                        if (l.includes('Sacrament')) time = l;
                    }
                    return {addr: addr, phone: phone, stake: stake, time: time, bishop: bishop};
                }""")
                winfo['address'] = details.get('addr', '')
                winfo['phone'] = details.get('phone', '')
                winfo['time'] = details.get('time', '')
                winfo['bishop'] = details.get('bishop', '')
                if details.get('stake'):
                    winfo['stake'] = details.get('stake', winfo.get('stake', ''))
                count += 1
                if count % 25 == 0:
                    print("  %d/%d" % (count, len(all_wards)))
            except:
                pass

        browser.close()

    # Save
    fp = os.path.join(OUT_DIR, 'lds_sc_wards.json')
    with open(fp, 'w') as f:
        json.dump({'stakes': {k: v['name'] for k, v in all_stakes.items()}, 'wards': all_wards}, f, indent=2)
    print("\nSaved: %d stakes, %d wards" % (len(all_stakes), len(all_wards)))

    # Import to DB
    db = sqlite3.connect(DB_PATH)
    cur = db.cursor()
    ins = 0
    for wid, winfo in all_wards.items():
        name = winfo.get('name', '')
        if not name: continue
        city = ''
        addr = winfo.get('address', '')
        if addr:
            parts = addr.split(',')
            if len(parts) >= 2: city = parts[-3].strip() if len(parts) >= 3 else parts[0].split()[-1]
        existing = cur.execute("SELECT id FROM churches WHERE UPPER(name)=? AND state='SC'", (name.upper(),)).fetchone()
        if not existing:
            cur.execute("INSERT OR IGNORE INTO churches (name, address, city, state, denomination, faith_tradition, phone, source, notes, pastor_name) VALUES (?,?,?,?,?,?,?,?,?,?)",
                (name, addr, city, 'SC', 'Church of Jesus Christ of Latter-day Saints', 'mormon',
                 winfo.get('phone', ''), 'lds_scrape',
                 'Stake: ' + winfo.get('stake', '') + ' | Ward ID: ' + wid + ' | Time: ' + winfo.get('time', ''),
                 winfo.get('bishop', '')))
            ins += 1
    db.commit()
    db.close()
    print("Imported %d new LDS wards" % ins)
    print("Done!")

if __name__ == '__main__':
    run()
