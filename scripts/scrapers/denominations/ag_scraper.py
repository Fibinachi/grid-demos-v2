#!/usr/bin/env python3
"""AG Church Directory Scraper using Playwright with Cloudflare bypass."""
import csv, json, re, sys, time
from datetime import datetime
from pathlib import Path
from playwright.sync_api import sync_playwright

OUT = Path('data/denom/ag_churches.csv')
STATE_FILE = Path('data/denom/ag_scraper_state.json')
BASE = 'https://ag.org/Resources/Directories/Church-Directory'

DISTRICTS = [
    ("01","Alabama"),("51","Alaska"),("02","Appalachian"),("03","Arizona"),
    ("04","Arkansas"),("59","Brazilian"),("71","Central District"),
    ("68","Central Pacific"),("56","Florida Multicultural"),("06","Georgia"),
    ("53","Hawaii"),("07","Illinois"),("08","Indiana"),("39","Iowa"),
    ("09","Kansas"),("10","Kentucky"),("57","Korean"),("11","Louisiana"),
    ("12","Michigan"),("73","Midwest"),("13","Minnesota"),("14","Mississippi"),
    ("15","Montana"),("62","National Slavic"),("16","Nebraska"),("18","New Jersey"),
    ("19","New Mexico"),("20","New York"),("21","North Carolina"),
    ("22","North Dakota"),("38","North Texas"),("23","Northern California-Nevada"),
    ("45","Northern Missouri"),("17","Northern New England"),("24","Northwest"),
    ("75","Northwest Hispanic"),("25","Ohio"),("26","Oklahoma"),("27","Oregon"),
    ("32","Peninsular Florida"),("05","PennDel"),("28","Potomac"),
    ("55","Puerto Rico"),("29","Rocky Mountain"),("52","Samoan"),
    ("61","Second Korean"),("34","SoCal Network"),("30","South Carolina"),
    ("54","South Central Hispanic"),("31","South Dakota"),("33","South Texas"),
    ("35","Southern Idaho"),("74","Southern Latin"),("36","Southern Missouri"),
    ("44","Southern New England"),("70","Southern Pacific"),("67","Southwest"),
    ("69","Spanish Eastern"),("37","Tennessee"),("64","Texas Gulf Hispanic"),
    ("66","Texas Louisiana Hispanic"),("40","West Florida"),("41","West Texas"),
    ("65","West Texas and Plains"),("42","Wisconsin-Northern Michigan"),("43","Wyoming"),
]

def log(msg):
    print(f'[{datetime.now().strftime("%H:%M:%S")}] {msg}', flush=True)

def load_state():
    if STATE_FILE.exists():
        with open(STATE_FILE) as f:
            return json.load(f)
    return {'done': [], 'churches': [], 'seen': []}

def save_state(state):
    with open(STATE_FILE, 'w') as f:
        json.dump(state, f)

def main():
    resume = '--resume' in sys.argv
    state = load_state() if resume else {'done': [], 'churches': [], 'seen': []}
    log(f'Start | {len(state["churches"])} existing')
    
    with sync_playwright() as pw:
        browser = pw.chromium.launch(
            headless=True,
            args=['--disable-blink-features=AutomationControlled', '--no-sandbox']
        )
        ctx = browser.new_context(
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/148.0.0.0 Safari/537.36',
            viewport={'width': 1920, 'height': 1080}
        )
        page = ctx.new_page()
        page.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
        
        for code, dname in DISTRICTS:
            if code in state['done']:
                continue
            
            log(f'[{dname}]')
            district_churches = []
            pnum = 1
            empty_run = 0
            
            while empty_run < 2:
                url = BASE + f'?D={code}' + (f'&page={pnum}' if pnum > 1 else '')
                try:
                    page.goto(url, wait_until='commit', timeout=20000)
                    page.wait_for_timeout(5000)
                except Exception as e:
                    log(f'  nav error: {e}')
                    empty_run += 1; pnum += 1; continue
                
                # Handle Cloudflare challenge - wait on same page
                for cf_wait in range(6):
                    if 'Just a moment' in page.title():
                        if cf_wait == 0:
                            log(f'  Cloudflare challenge, waiting...')
                        page.wait_for_timeout(5000)
                    else:
                        break
                
                html = page.content()
                found = []
                pat = r'panel-heading[^"]*"[^>]*href="[^"]*g=([a-f0-9-]+)[^"]*"[^>]*>.*?<h3>(.*?)</h3>.*?church-info[^>]*>.*?<h4>([^<]*)</h4>.*?address[^>]*>.*?>\s*([^<]+)'
                for m in re.finditer(pat, html, re.DOTALL):
                    guid, name, pastor, addr = m.group(1), m.group(2).strip(), m.group(3).strip(), m.group(4).strip()
                    if 'Ministry Network' in name or 'Network Office' in name: continue
                    pastor = pastor.replace('Reverend ', '').replace('Rev. ', '').strip()
                    found.append({'name': name, 'pastor': pastor, 'guid': guid, 'address': addr})
                
                if not found:
                    empty_run += 1
                else:
                    empty_run = 0
                    for ch in found:
                        if ch['guid'] not in [x['guid'] for x in district_churches]:
                            district_churches.append(ch)
                
                pnum += 1
                time.sleep(0.3)
            
            newc = 0
            for ch in district_churches:
                if ch['guid'] not in state['seen']:
                    state['seen'].append(ch['guid'])
                    state['churches'].append(ch)
                    newc += 1
            
            state['done'].append(code)
            log(f'  +{newc} ({len(state["churches"])})')
            save_state(state)
        
        browser.close()
    
    log(f'Exporting {len(state["churches"])} churches...')
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT, 'w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=['name','pastor','address','guid'])
        w.writeheader()
        for ch in state['churches']:
            w.writerow(ch)
    log(f'Done: {OUT}')

if __name__ == '__main__':
    main()
