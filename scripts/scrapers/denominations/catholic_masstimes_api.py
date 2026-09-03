#!/usr/bin/env python3
"""
Scrape all parishes from masstimes.org API
API: apiv4.updateparishdata.org/Churchs/?lat=...&long=...&pg=...
Returns 30 parishes per page with name, address, diocese, phone, website, etc.
"""
import urllib.request, json, csv, time, os
from datetime import datetime
from pathlib import Path

OUT_DIR = Path('data') / 'denom'
OUT_DIR.mkdir(parents=True, exist_ok=True)
UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'

def log(msg):
    print(f'[{datetime.now().strftime("%H:%M:%S")}] {msg}', flush=True)

def fetch_parishes(lat, lon, page=1):
    url = f'https://apiv4.updateparishdata.org/Churchs/?lat={lat}&long={lon}&pg={page}'
    try:
        r = urllib.request.Request(url, headers={'User-Agent': UA})
        resp = urllib.request.urlopen(r, timeout=15)
        return json.loads(resp.read().decode())
    except Exception as e:
        log(f'  Error: {e}')
        return None

def scrape_area(lat, lon, label, max_pages=20):
    """Scrape all pages for a given coordinate."""
    all_parishes = []
    seen_ids = set()
    
    for page in range(1, max_pages + 1):
        data = fetch_parishes(lat, lon, page)
        if not data:
            break
        if len(data) == 0:
            break
        
        new = 0
        for p in data:
            pid = p.get('id', '')
            if pid and pid not in seen_ids:
                seen_ids.add(pid)
                all_parishes.append(p)
                new += 1
        
        log(f'  Page {page}: {len(data)} results, {new} new (total: {len(all_parishes)})')
        
        if len(data) < 30:
            break  # Last page
        
        time.sleep(0.5)
    
    log(f'{label}: {len(all_parishes)} total parishes')
    return all_parishes

def save_parishes(parishes, filename):
    path = OUT_DIR / filename
    with open(path, 'w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=[
            'name', 'address', 'city', 'state', 'zip', 'phone', 'website', 'email',
            'diocese', 'diocese_type', 'church_type', 'pastor', 'latitude', 'longitude',
            'rite', 'language',
        ])
        w.writeheader()
        for p in parishes:
            w.writerow({
                'name': p.get('name', ''),
                'address': p.get('church_address_street_address', ''),
                'city': p.get('church_address_city_name', ''),
                'state': p.get('church_address_providence_name', ''),
                'zip': p.get('church_address_postal_code', ''),
                'phone': p.get('phone_number', ''),
                'website': p.get('url', ''),
                'email': p.get('email', ''),
                'diocese': p.get('diocese_name', ''),
                'diocese_type': p.get('diocese_type_name', ''),
                'church_type': p.get('church_type_name', ''),
                'pastor': p.get('pastors_name', ''),
                'latitude': p.get('latitude', ''),
                'longitude': p.get('longitude', ''),
                'rite': p.get('rite_type_name', ''),
                'language': p.get('language_name', ''),
            })
    log(f'Saved {len(parishes)} to {path}')
    return path

def main():
    log('Masstimes Parish API Scraper')
    
    # LA Archdiocese - multiple query points to cover the vast territory
    la_points = [
        (34.0522, -118.2437, 'Downtown LA'),
        (33.9425, -118.4081, 'LAX/South Bay'),
        (34.1686, -118.6056, 'San Fernando Valley'),
        (34.1478, -117.9819, 'San Gabriel Valley'),
        (33.7224, -118.0010, 'Orange County line'),
        (34.7296, -118.1443, 'Antelope Valley'),
        (34.4208, -119.6982, 'Santa Barbara'),
        (34.4390, -119.7136, 'Ventura'),
        (34.9513, -120.4343, 'Santa Maria'),
    ]
    
    all_parishes = []
    seen_ids = set()
    
    for lat, lon, label in la_points:
        log(f'\n--- {label} ({lat}, {lon}) ---')
        parishes = scrape_area(lat, lon, label)
        for p in parishes:
            pid = p.get('id', '')
            if pid and pid not in seen_ids:
                seen_ids.add(pid)
                all_parishes.append(p)
    
    log(f'\n{"="*60}')
    log(f'Total unique parishes: {len(all_parishes)}')
    
    if all_parishes:
        save_parishes(all_parishes, 'la_archdiocese_parishes.csv')
    
    # Also try NYC area for comparison
    log('\n--- NYC (Manhattan) ---')
    nyc = scrape_area(40.7128, -74.0060, 'NYC')
    if nyc:
        save_parishes(nyc, 'nyc_archdiocese_parishes.csv')

if __name__ == '__main__':
    main()
