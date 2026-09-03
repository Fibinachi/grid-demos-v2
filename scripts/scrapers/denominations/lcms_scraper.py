#!/usr/bin/env python3
"""LCMS church scraper using Playwright."""
import csv, json, time
from datetime import datetime
from pathlib import Path
from playwright.sync_api import sync_playwright

OUT = Path('data/denom/lcms_churches.csv')
STATES = [
    ["38D2D504-95C2-E811-A2E7-005056B6CA67","AL"],["39D2D504-95C2-E811-A2E7-005056B6CA67","AK"],
    ["3AD2D504-95C2-E811-A2E7-005056B6CA67","AZ"],["3BD2D504-95C2-E811-A2E7-005056B6CA67","AR"],
    ["3CD2D504-95C2-E811-A2E7-005056B6CA67","CA"],["3DD2D504-95C2-E811-A2E7-005056B6CA67","CO"],
    ["6DD2D504-95C2-E811-A2E7-005056B6CA67","CT"],["6ED2D504-95C2-E811-A2E7-005056B6CA67","DE"],
    ["6FD2D504-95C2-E811-A2E7-005056B6CA67","DC"],["70D2D504-95C2-E811-A2E7-005056B6CA67","FL"],
    ["71D2D504-95C2-E811-A2E7-005056B6CA67","GA"],["72D2D504-95C2-E811-A2E7-005056B6CA67","HI"],
    ["67D2D504-95C2-E811-A2E7-005056B6CA67","ID"],["68D2D504-95C2-E811-A2E7-005056B6CA67","IL"],
    ["69D2D504-95C2-E811-A2E7-005056B6CA67","IN"],["6AD2D504-95C2-E811-A2E7-005056B6CA67","IA"],
    ["6BD2D504-95C2-E811-A2E7-005056B6CA67","KS"],["6CD2D504-95C2-E811-A2E7-005056B6CA67","KY"],
    ["61D2D504-95C2-E811-A2E7-005056B6CA67","LA"],["62D2D504-95C2-E811-A2E7-005056B6CA67","ME"],
    ["63D2D504-95C2-E811-A2E7-005056B6CA67","MD"],["64D2D504-95C2-E811-A2E7-005056B6CA67","MA"],
    ["65D2D504-95C2-E811-A2E7-005056B6CA67","MI"],["66D2D504-95C2-E811-A2E7-005056B6CA67","MN"],
    ["5BD2D504-95C2-E811-A2E7-005056B6CA67","MS"],["5CD2D504-95C2-E811-A2E7-005056B6CA67","MO"],
    ["5DD2D504-95C2-E811-A2E7-005056B6CA67","MT"],["5ED2D504-95C2-E811-A2E7-005056B6CA67","NE"],
    ["5FD2D504-95C2-E811-A2E7-005056B6CA67","NV"],["60D2D504-95C2-E811-A2E7-005056B6CA67","NH"],
    ["55D2D504-95C2-E811-A2E7-005056B6CA67","NJ"],["56D2D504-95C2-E811-A2E7-005056B6CA67","NM"],
    ["57D2D504-95C2-E811-A2E7-005056B6CA67","NY"],["58D2D504-95C2-E811-A2E7-005056B6CA67","NC"],
    ["59D2D504-95C2-E811-A2E7-005056B6CA67","ND"],["5AD2D504-95C2-E811-A2E7-005056B6CA67","OH"],
    ["4FD2D504-95C2-E811-A2E7-005056B6CA67","OK"],["50D2D504-95C2-E811-A2E7-005056B6CA67","OR"],
    ["51D2D504-95C2-E811-A2E7-005056B6CA67","PA"],["48D2D504-95C2-E811-A2E7-005056B6CA67","PR"],
    ["52D2D504-95C2-E811-A2E7-005056B6CA67","RI"],["53D2D504-95C2-E811-A2E7-005056B6CA67","SC"],
    ["54D2D504-95C2-E811-A2E7-005056B6CA67","SD"],["49D2D504-95C2-E811-A2E7-005056B6CA67","TN"],
    ["4AD2D504-95C2-E811-A2E7-005056B6CA67","TX"],["4BD2D504-95C2-E811-A2E7-005056B6CA67","UT"],
    ["4CD2D504-95C2-E811-A2E7-005056B6CA67","VT"],["4DD2D504-95C2-E811-A2E7-005056B6CA67","VA"],
    ["4ED2D504-95C2-E811-A2E7-005056B6CA67","WA"],["43D2D504-95C2-E811-A2E7-005056B6CA67","WV"],
    ["44D2D504-95C2-E811-A2E7-005056B6CA67","WI"],["45D2D504-95C2-E811-A2E7-005056B6CA67","WY"],
]

def log(msg):
    print(f'[{datetime.now().strftime("%H:%M:%S")}] {msg}', flush=True)

def main():
    log('LCMS Scraper')
    all_churches = []
    
    with sync_playwright() as p:
        b = p.chromium.launch(headless=False, args=['--disable-blink-features=AutomationControlled'])
        page = b.new_page()
        page.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
        
        for guid, abbr in STATES:
            log(f'[{abbr}]')
            try:
                with page.expect_response(
                    lambda r: '/api/congregations' in r.url and r.ok, 
                    timeout=30000
                ) as resp_info:
                    page.goto(f'https://locator.lcms.org/church?distance=1000&stateId={guid}', 
                             wait_until='domcontentloaded', timeout=20000)
                
                import json as j
                data = j.loads(resp_info.value.body())
                for c in data.get('results', []):
                    a = c.get('preferredAddress') or {}
                    ph = c.get('preferredPhone') or {}
                    em = c.get('preferredEmail') or {}
                    all_churches.append({
                        'name': c.get('name',''), 'address': a.get('full',''),
                        'city': a.get('city',''), 'state': a.get('state',''),
                        'zip': a.get('zip',''), 'phone': ph.get('phoneNumber',''),
                        'email': em.get('email',''), 'website': c.get('website',''),
                        'district': c.get('district',''),
                    })
                cnt = len(data.get('results', []))
                log(f'  {cnt} ({len(all_churches)})')
            except Exception as e:
                log(f'  Error: {e}')
            time.sleep(0.3)
        
        b.close()
    
    log(f'Exporting {len(all_churches)}...')
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT, 'w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=['name','address','city','state','zip','phone','email','website','district'])
        w.writeheader()
        w.writerows(all_churches)
    log(f'Done: {OUT}')

if __name__ == '__main__':
    main()
