#!/usr/bin/env python3
"""
Nationwide Catholic Parish Scraper
==================================
Scrapes ALL US Catholic parishes from the masstimes.org API
(apiv4.updateparishdata.org/Churchs/) which powers the USCCB mass times finder.

Queries from major US cities to cover all dioceses, deduplicates by church ID.
Returns name, address, phone, website, email, diocese, pastor, coordinates, etc.

Usage:
    python scripts/scrapers/denominations/catholic_us_scraper.py
    python scripts/scrapers/denominations/catholic_us_scraper.py --resume
"""
import urllib.request, json, csv, time, os, sys
from datetime import datetime
from pathlib import Path
from collections import Counter

OUT_DIR = Path('data') / 'denom'
OUT_DIR.mkdir(parents=True, exist_ok=True)
STATE_FILE = Path('data') / 'masstimes_harvest_state.json'
UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'

def log(msg):
    print(f'[{datetime.now().strftime("%H:%M:%S")}] {msg}', flush=True)

# Major US cities covering all population centers
# Format: (lat, lon, label)
QUERY_POINTS = [
    # Northeast
    (40.7128, -74.0060, 'New York City'),
    (42.3601, -71.0589, 'Boston'),
    (39.9526, -75.1652, 'Philadelphia'),
    (38.9072, -77.0369, 'Washington DC'),
    (39.2904, -76.6122, 'Baltimore'),
    (40.4406, -79.9959, 'Pittsburgh'),
    (43.1566, -77.6088, 'Rochester NY'),
    (42.6526, -73.7562, 'Albany NY'),
    (41.7658, -72.6734, 'Hartford CT'),
    # Southeast
    (33.7490, -84.3880, 'Atlanta'),
    (25.7617, -80.1918, 'Miami'),
    (28.5383, -81.3792, 'Orlando'),
    (30.3322, -81.6557, 'Jacksonville'),
    (35.2271, -80.8431, 'Charlotte'),
    (36.1627, -86.7816, 'Nashville'),
    (35.1495, -90.0490, 'Memphis'),
    (32.3182, -86.9023, 'Montgomery AL'),
    (32.7767, -79.9311, 'Charleston SC'),
    (30.2672, -97.7431, 'Austin TX'),
    (32.7767, -96.7970, 'Dallas'),
    (29.7604, -95.3698, 'Houston'),
    (29.4241, -98.4936, 'San Antonio'),
    (31.7619, -106.4850, 'El Paso'),
    # Midwest
    (41.8781, -87.6298, 'Chicago'),
    (42.3314, -83.0458, 'Detroit'),
    (41.4993, -81.6944, 'Cleveland'),
    (39.9612, -82.9988, 'Columbus OH'),
    (39.7684, -86.1581, 'Indianapolis'),
    (43.0389, -87.9065, 'Milwaukee'),
    (44.9778, -93.2650, 'Minneapolis'),
    (38.6270, -90.1994, 'St. Louis'),
    (39.0997, -94.5786, 'Kansas City'),
    (41.2565, -95.9345, 'Omaha'),
    (41.6032, -93.6091, 'Des Moines'),
    (42.8782, -97.3928, 'Sioux Falls'),
    # West
    (39.7392, -104.9903, 'Denver'),
    (35.0844, -106.6504, 'Albuquerque'),
    (36.1699, -115.1398, 'Las Vegas'),
    (33.4484, -112.0740, 'Phoenix'),
    (40.7608, -111.8910, 'Salt Lake City'),
    # Pacific
    (34.0522, -118.2437, 'Los Angeles'),
    (37.7749, -122.4194, 'San Francisco'),
    (37.3382, -121.8863, 'San Jose'),
    (32.7157, -117.1611, 'San Diego'),
    (45.5202, -122.6819, 'Portland OR'),
    (47.6062, -122.3321, 'Seattle'),
    (38.5816, -121.4944, 'Sacramento'),
    # Remote
    (61.2181, -149.9003, 'Anchorage AK'),
    (21.3069, -157.8583, 'Honolulu HI'),
    (43.6150, -116.2023, 'Boise ID'),
    (46.8797, -110.3626, 'Montana'),
]

def fetch_page(lat, lon, page=1):
    url = f'https://apiv4.updateparishdata.org/Churchs/?lat={lat}&long={lon}&pg={page}'
    try:
        r = urllib.request.Request(url, headers={'User-Agent': UA})
        resp = urllib.request.urlopen(r, timeout=15)
        return json.loads(resp.read().decode())
    except:
        return None

def main():
    resume = '--resume' in sys.argv
    
    log('Nationwide Catholic Parish Scraper')
    
    # Load existing state
    seen_ids = set()
    existing_parishes = []
    if resume and STATE_FILE.exists():
        with open(STATE_FILE) as f:
            state = json.load(f)
        seen_ids = set(state.get('ids', []))
        log(f'Resuming with {len(seen_ids):,} existing IDs')
    
    if resume and Path('data/denom/us_catholic_parishes.csv').exists():
        with open('data/denom/us_catholic_parishes.csv', encoding='utf-8') as f:
            existing_parishes = list(csv.DictReader(f))
        log(f'Loaded {len(existing_parishes):,} existing records')
    
    all_parishes = list(existing_parishes)
    new_count = 0
    
    for idx, (lat, lon, label) in enumerate(QUERY_POINTS):
        log(f'\n[{idx+1}/{len(QUERY_POINTS)}] {label} ({lat}, {lon})')
        
        for page in range(1, 100):  # Max 100 pages
            data = fetch_page(lat, lon, page)
            if not data or len(data) == 0:
                break
            
            for p in data:
                pid = p.get('id', '')
                if pid and pid not in seen_ids:
                    seen_ids.add(pid)
                    all_parishes.append(p)
                    new_count += 1
            
            if len(data) < 30:
                break
            time.sleep(0.3)
        
        log(f'  Total: {len(seen_ids):,} unique parishes')
        
        # Save progress every 5 points
        if (idx + 1) % 5 == 0:
            save_csv(all_parishes, 'us_catholic_parishes.csv')
            save_state(seen_ids)
    
    # Final save
    save_csv(all_parishes, 'us_catholic_parishes.csv')
    save_state(seen_ids)
    
    log(f'\n{"="*60}')
    log(f'COMPLETE! Total unique parishes: {len(seen_ids):,}')
    log(f'Total records: {len(all_parishes):,}')
    
    # Summary by diocese
    dios = Counter(p.get('diocese_name', '') or 'Unknown' for p in all_parishes)
    log('\nTop dioceses:')
    for d, n in dios.most_common(20):
        log(f'  {n:>5,}  {d[:55]}')

def save_csv(parishes, filename):
    path = OUT_DIR / filename
    with open(path, 'w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=[
            'name', 'address', 'city', 'state', 'zip', 'phone', 'website', 'email',
            'diocese', 'diocese_type', 'church_type', 'pastor', 'latitude', 'longitude',
            'rite', 'language', 'mass_times',
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
                'mass_times': str(p.get('church_worship_times', '')),
            })
    log(f'Saved {len(parishes):,} to {path}')

def save_state(ids):
    with open(STATE_FILE, 'w') as f:
        json.dump({'ids': list(ids), 'count': len(ids), 'updated': datetime.now().isoformat()}, f)

if __name__ == '__main__':
    main()
