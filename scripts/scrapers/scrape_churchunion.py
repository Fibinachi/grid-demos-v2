"""
scrape_churchunion.py — Scrape churchunion.us church directory (~165K churches)
Pages: /branch-churches/page/1/ through /page/16512/
Output: data/churchunion_scraped.csv
"""
import requests
from bs4 import BeautifulSoup
import csv, time, json, os, re
from concurrent.futures import ThreadPoolExecutor, as_completed

BASE_URL = "https://www.churchunion.us/branch-churches/page/{}/"
OUTPUT_FILE = "E:/grid/data/churchunion_scraped.csv"
CHECKPOINT_FILE = "E:/grid/data/churchunion_checkpoint.json"
NUM_WORKERS = 2
BATCH_SIZE = 20
DELAY = 0.5

def parse_page(html):
    soup = BeautifulSoup(html, 'html.parser')
    churches = []
    for article in soup.find_all('article', class_='node-firma'):
        header = article.find('header')
        name_link = header.find('a') if header else None
        if not name_link: continue
        name = name_link.text.strip()
        url = name_link.get('href', '')
        nid = re.search(r'-(\d+)$', url)
        nid = nid.group(1) if nid else ''
        
        taxo_divs = article.find_all('div', class_='taxonomy-custom')
        city = state = ''
        if len(taxo_divs) >= 1:
            city_link = taxo_divs[0].find('a')
            if city_link:
                ct = city_link.text.strip()
                if ',' in ct:
                    parts = ct.rsplit(',', 1)
                    city, state = parts[0].strip(), parts[1].strip()
                else:
                    city = ct
        
        county = ''
        if len(taxo_divs) >= 2:
            cl = taxo_divs[1].find('a')
            county = cl.text.strip() if cl else ''
        
        address = ''
        gmap = article.find('div', class_='field-name-field-gmap')
        if gmap:
            addr_div = gmap.find('div', class_='field-item')
            address = addr_div.text.strip() if addr_div else ''
        
        if name:
            churches.append({'name': name, 'address': address, 'city': city,
                           'state': state, 'county': county, 'url': url, 'nid': nid})
    return churches

def scrape_page(page_num, session):
    try:
        resp = session.get(BASE_URL.format(page_num), timeout=30)
        resp.raise_for_status()
        churches = parse_page(resp.text)
        return page_num, churches, None
    except Exception as e:
        return page_num, [], str(e)

def load_ck():
    return json.load(open(CHECKPOINT_FILE)) if os.path.exists(CHECKPOINT_FILE) else {
        'last_page': 0, 'total_scraped': 0, 'total_pages': 0, 'errors': []}

def save_ck(d):
    json.dump(d, open(CHECKPOINT_FILE, 'w'))

def main():
    session = requests.Session()
    session.headers.update({
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        'Accept': 'text/html,application/xhtml+xml',
    })
    
    ck = load_ck()
    start = max(ck['last_page'] + 1, 1)
    total_pages = ck.get('total_pages', 0)
    total_scraped = ck['total_scraped']
    errors = ck.get('errors', [])
    
    if not total_pages:
        try:
            resp = session.get(BASE_URL.format(1), timeout=30)
            soup = BeautifulSoup(resp.text, 'html.parser')
            for a in soup.find_all('a', href=re.compile(r'/page/\d+/')):
                m = re.search(r'/page/(\d+)/', a['href'])
                if m: total_pages = max(total_pages, int(m.group(1)))
        except:
            total_pages = 16512
        ck['total_pages'] = total_pages
        save_ck(ck)
    
    print(f"ChurchUnion Scraper — {start} → {total_pages} pages, {NUM_WORKERS} workers")
    print(f"Output: {OUTPUT_FILE}")
    
    if not os.path.exists(OUTPUT_FILE) or os.path.getsize(OUTPUT_FILE) == 0:
        with open(OUTPUT_FILE, 'w', newline='', encoding='utf-8') as f:
            csv.DictWriter(f, ['name','address','city','state','county','url','nid']).writeheader()
    
    for batch_start in range(start, total_pages + 1, BATCH_SIZE):
        batch_end = min(batch_start + BATCH_SIZE - 1, total_pages)
        pages = list(range(batch_start, batch_end + 1))
        
        with ThreadPoolExecutor(max_workers=NUM_WORKERS) as ex:
            futures = {ex.submit(scrape_page, p, session): p for p in pages}
            batch_results, batch_errors = [], 0
            for f in as_completed(futures):
                page_num, churches, err = f.result()
                if err:
                    errors.append(f"p{page_num}: {err}"); batch_errors += 1
                else:
                    batch_results.extend(churches)
                    if len(batch_results) % 100 == 0:
                        print(f"    {len(batch_results)} churches so far...", end='\r')
            
            if batch_results:
                with open(OUTPUT_FILE, 'a', newline='', encoding='utf-8') as f:
                    csv.DictWriter(f, ['name','address','city','state','county','url','nid']).writerows(batch_results)
                total_scraped += len(batch_results)
        
        ck.update(last_page=batch_end, total_scraped=total_scraped, errors=errors[-200:])
        save_ck(ck)
        pct = batch_end / total_pages * 100
        print(f"  p{batch_start}-{batch_end}: +{len(batch_results):,} ({total_scraped:,} total) {pct:.1f}% | {batch_errors} err")
        time.sleep(DELAY * 2)
    
    print(f"\nDone! {total_scraped:,} churches → {OUTPUT_FILE}")

if __name__ == '__main__':
    main()
