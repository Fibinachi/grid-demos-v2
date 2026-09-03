#!/usr/bin/env python3
"""Scrape all US Catholic parishes from gcatholic.org.
Their diocese pages have comprehensive parish listings."""
import urllib.request, re, json, time, csv
from datetime import datetime
from pathlib import Path

UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
OUT = Path('data') / 'gcatholic_parishes.csv'

def log(msg):
    print(f'[{datetime.now().strftime("%H:%M:%S")}] {msg}', flush=True)

def fetch(url):
    try:
        r = urllib.request.Request(url, headers={'User-Agent': UA})
        with urllib.request.urlopen(r, timeout=15) as f:
            return f.read().decode('utf-8', 'replace')
    except Exception as e:
        return None

def get_diocese_links():
    """Get all US diocese links from gcatholic."""
    html = fetch('https://www.gcatholic.org/dioceses/country/US.htm')
    if not html:
        log('ERROR: Could not fetch diocese list')
        return []
    
    # Find all diocese links
    links = re.findall(r'<a[^>]*href="([^"]*diocese[^"]+)"[^>]*>([^<]+)</a>', html, re.I)
    log(f'Found {len(links)} diocese links')
    
    result = []
    for href, name in links:
        name = name.strip()
        if name.startswith('...'):  # skip navigation links
            continue
        full_url = 'https://www.gcatholic.org/dioceses/' + href.lstrip('../')
        result.append({'name': name, 'url': full_url})
    
    log(f'  Clean: {len(result)} dioceses')
    return result

def scrape_diocese_parishes(diocese_name, diocese_url):
    """Scrape parish data from a gcatholic diocese page."""
    html = fetch(diocese_url)
    if not html:
        return []
    
    parishes = []
    
    # gcatholic uses <li> for parish listings with links containing "church" in URL
    # Pattern: <li><a href="../church/church-name.htm">Church Name</a></li>
    
    # Find all church links 
    church_links = re.findall(
        r'<li[^>]*>.*?<a\s+href="([^"]*)"[^>]*>\s*([^<]+(?:Church|Parish|Shrine|Mission|Cathedral)[^<]*?)\s*</a>.*?</li>',
        html, re.DOTALL | re.I
    )
    
    for href, name in church_links:
        name = name.strip()
        # Clean up whitespace
        name = re.sub(r'\s+', ' ', name)
        if name and len(name) > 3:
            full_url = 'https://www.gcatholic.org/churches/' + href.lstrip('..')
            parishes.append({
                'diocese': diocese_name,
                'parish_name': name,
                'parish_url': full_url,
                'source': 'gcatholic'
            })
    
    # Also try the <a> inside <td> pattern (some dioceses use tables)
    if not church_links:
        td_links = re.findall(
            r'<td[^>]*>.*?<a\s+href="([^"]*)"[^>]*>\s*([^<]+?)\s*</a>.*?</td>',
            html, re.DOTALL | re.I
        )
        for href, name in td_links:
            name = name.strip()
            name = re.sub(r'\s+', ' ', name)
            if name and len(name) > 5 and not re.match(r'^\d', name):
                full_url = 'https://www.gcatholic.org/churches/' + href.lstrip('..')
                parishes.append({
                    'diocese': diocese_name,
                    'parish_name': name,
                    'parish_url': full_url,
                    'source': 'gcatholic'
                })
    
    return parishes

def main():
    log('GCatholic Parish Scraper')
    
    # Get all US dioceses
    dioceses = get_diocese_links()
    if not dioceses:
        return
    
    # Load existing if resuming
    existing = []
    if OUT.exists():
        with open(OUT, encoding='utf-8') as f:
            existing = list(csv.DictReader(f))
        log(f'Existing: {len(existing):,} parishes')
    
    existing_urls = {r['parish_url'].lower().rstrip('/') for r in existing}
    done_names = {r['diocese'] for r in existing}
    
    all_parishes = list(existing)
    
    for i, d in enumerate(dioceses):
        if d['name'] in done_names:
            continue
        
        log(f'[{i+1}/{len(dioceses)}] {d["name"][:50]:50s}')
        parishes = scrape_diocese_parishes(d['name'], d['url'])
        
        new = []
        for p in parishes:
            key = p['parish_url'].lower().rstrip('/')
            if key not in existing_urls:
                existing_urls.add(key)
                new.append(p)
        
        log(f'  Found: {len(parishes)}, New: {len(new)}')
        all_parishes.extend(new)
        
        # Save incrementally
        with open(OUT, 'w', newline='', encoding='utf-8') as f:
            w = csv.DictWriter(f, fieldnames=['diocese','parish_name','parish_url','source'])
            w.writeheader()
            w.writerows(all_parishes)
        
        done_names.add(d['name'])
        time.sleep(1)  # Be respectful
    
    log(f'\nDone! Total: {len(all_parishes):,} parishes from {len(done_names)} dioceses')

if __name__ == '__main__':
    main()
