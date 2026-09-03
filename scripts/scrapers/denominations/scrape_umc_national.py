#!/usr/bin/env python3
"""
UMC National Church Scraper
===========================
Scrapes all ~30,000 UMC churches via the GetChurches API endpoint.
Uses a grid search across the continental US to find all churches.

Usage:
    python scripts/scrapers/denominations/scrape_umc_national.py
    python scripts/scrapers/denominations/scrape_umc_national.py --limit=5
    python scripts/scrapers/denominations/scrape_umc_national.py --grid=coarse
"""

import csv, json, os, sys, time, urllib.request, ssl
from datetime import datetime
from pathlib import Path
from collections import OrderedDict

PROJECT_DIR = Path(r"E:\grid")
DATA_DIR = PROJECT_DIR / "data"
OUTPUT_CSV = DATA_DIR / "umc_national_churches.csv"
STATE_FILE = DATA_DIR / "umc_scraper_state.json"

API_URL = "https://www.umc.org/ChurchesFeature/Churches/GetChurches"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
ssl_ctx = ssl.create_default_context()
ssl_ctx.check_hostname = False
ssl_ctx.verify_mode = ssl.CERT_NONE

# Major US cities as search centers (covers all 50 states + DC)
CITIES = [
    # Northeast
    (42.36, -71.06, "Boston"), (41.76, -72.67, "Hartford"), (41.38, -73.45, "Danbury"),
    (40.71, -74.01, "New York"), (40.22, -74.76, "Trenton"), (39.95, -75.17, "Philadelphia"),
    (38.90, -77.04, "Washington"), (39.29, -76.61, "Baltimore"), (39.74, -75.55, "Wilmington"),
    # Southeast
    (38.63, -90.20, "St Louis"), (37.54, -77.44, "Richmond"), (36.85, -76.29, "Norfolk"),
    (35.78, -78.64, "Raleigh"), (35.23, -80.84, "Charlotte"), (34.84, -82.40, "Greenville"),
    (33.75, -84.39, "Atlanta"), (33.46, -86.81, "Birmingham"), (32.30, -86.26, "Montgomery"),
    (30.44, -84.28, "Tallahassee"), (30.33, -81.66, "Jacksonville"), (28.54, -81.38, "Orlando"),
    (27.95, -82.46, "Tampa"), (25.76, -80.19, "Miami"), (32.78, -79.93, "Charleston"),
    (35.05, -85.31, "Chattanooga"), (36.16, -86.78, "Nashville"), (35.15, -90.05, "Memphis"),
    (33.52, -86.80, "Birmingham"), (34.73, -86.59, "Huntsville"), (32.37, -88.70, "Meridian"),
    (31.56, -84.16, "Albany"), (30.84, -83.98, "Thomasville"),
    # Midwest
    (41.88, -87.63, "Chicago"), (40.44, -86.93, "Lafayette"), (39.77, -86.16, "Indianapolis"),
    (42.33, -83.05, "Detroit"), (42.96, -85.67, "Grand Rapids"), (41.50, -81.70, "Cleveland"),
    (39.96, -83.00, "Columbus"), (39.10, -84.51, "Cincinnati"), (40.76, -82.52, "Mansfield"),
    (40.09, -82.81, "Newark"), (40.43, -80.00, "Pittsburgh"), (42.10, -79.24, "Jamestown"),
    (43.08, -79.07, "Niagara Falls"), (43.16, -77.61, "Rochester"), (43.05, -76.15, "Syracuse"),
    (44.98, -93.26, "Minneapolis"), (45.53, -94.18, "St Cloud"), (46.82, -92.08, "Duluth"),
    (43.04, -87.91, "Milwaukee"), (43.08, -89.38, "Madison"), (42.52, -92.34, "Waterloo"),
    (41.59, -93.60, "Des Moines"), (40.81, -91.11, "Burlington"), (38.97, -95.71, "Topeka"),
    (39.09, -94.58, "Kansas City"), (41.26, -95.94, "Omaha"), (40.82, -96.69, "Lincoln"),
    (38.63, -90.20, "St Louis"), (38.71, -88.09, "Olney"), (37.69, -97.34, "Wichita"),
    (35.47, -97.52, "Oklahoma City"), (36.14, -95.94, "Tulsa"),
    # South Central
    (29.76, -95.37, "Houston"), (29.42, -98.49, "San Antonio"), (30.27, -97.74, "Austin"),
    (32.78, -96.80, "Dallas"), (32.76, -97.33, "Fort Worth"), (31.76, -106.49, "El Paso"),
    (33.45, -112.07, "Phoenix"), (32.22, -110.97, "Tucson"), (35.08, -106.65, "Albuquerque"),
    (34.05, -118.24, "Los Angeles"), (32.72, -117.16, "San Diego"), (33.13, -117.10, "Escondido"),
    (34.41, -119.67, "Santa Barbara"), (36.74, -119.79, "Fresno"), (38.58, -121.49, "Sacramento"),
    (37.77, -122.42, "San Francisco"), (37.34, -121.89, "San Jose"), (36.60, -121.89, "Monterey"),
    (45.52, -122.68, "Portland"), (47.61, -122.33, "Seattle"), (47.65, -117.42, "Spokane"),
    (43.62, -116.20, "Boise"), (40.76, -111.89, "Salt Lake City"), (39.74, -104.99, "Denver"),
    (38.27, -104.62, "Pueblo"), (41.14, -104.82, "Cheyenne"), (46.88, -96.79, "Fargo"),
    (44.37, -100.35, "Pierre"), (45.81, -108.41, "Billings"), (48.15, -103.62, "Williston"),
    (47.50, -111.31, "Great Falls"), (46.60, -112.02, "Helena"),
    # Pacific
    (61.22, -149.90, "Anchorage"), (64.84, -147.72, "Fairbanks"),
    (21.30, -157.82, "Honolulu"), (20.88, -156.47, "Kahului"),
]

def fetch_churches(lat, lng, page=1, search='USA'):
    """Call the GetChurches API and return parsed response."""
    body = json.dumps({
        'latitude': lat,
        'longitude': lng,
        'search': search,
        'Page': page,
        'hasResults': False,
    }).encode()
    
    req = urllib.request.Request(API_URL, data=body, headers={
        'User-Agent': UA,
        'Content-Type': 'application/json',
    })
    
    try:
        resp = urllib.request.urlopen(req, timeout=20, context=ssl_ctx)
        return json.loads(resp.read().decode())
    except Exception as e:
        print(f"  API error: {e}")
        return None


def extract_church(data):
    """Extract clean fields from API church object."""
    pref_name = data.get('Preferred_Name__c', '') or ''
    alt_name = data.get('name', '') or ''
    name = pref_name if pref_name else alt_name
    
    return {
        'id': data.get('id', ''),
        'name': name[:200],
        'alt_name': alt_name[:200] if alt_name and alt_name != name else '',
        'address': (data.get('address_line_1') or '')[:200],
        'address_2': (data.get('address_line_2') or '')[:200],
        'city': (data.get('address_city') or '')[:100],
        'state': (data.get('address_statecode') or '')[:10],
        'state_full': (data.get('address_state') or '')[:50],
        'zip': (data.get('address_zip') or '')[:20],
        'country': (data.get('address_country') or '')[:50],
        'phone': (data.get('phone_number') or '')[:50],
        'email': (data.get('primary_email') or '')[:200],
        'website': (data.get('church_url') or '')[:500],
        'latitude': data.get('latitude', ''),
        'longitude': data.get('longitude', ''),
        'conference': (data.get('conference') or '')[:100],
        'district': (data.get('district') or '')[:100],
        'attendance': data.get('attendance', 0),
        'ethnicity': (data.get('ethnicity') or '')[:50],
        'english': data.get('english', False),
        'spanish': data.get('spanish', False),
        'korean': data.get('korean', False),
        'image_url': (data.get('image_url') or '')[:500],
    }


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--grid', choices=['fine', 'coarse'], default='coarse',
                       help='Grid density (fine=1deg, coarse=2deg)')
    parser.add_argument('--limit', type=int, help='Limit grid points')
    parser.add_argument('--resume', action='store_true', help='Resume from saved state')
    args = parser.parse_args()
    
    selected = CITIES
    if args.limit:
        selected = selected[:args.limit]
    
    print(f"Cities: {len(selected)}")
    
    # Load state
    state = {'scraped_ids': set(), 'grid_index': 0}
    if args.resume and STATE_FILE.exists():
        with open(STATE_FILE) as f:
            saved = json.load(f)
            state['scraped_ids'] = set(saved.get('scraped_ids', []))
            state['grid_index'] = saved.get('grid_index', 0)
        print(f"Resuming: {len(state['scraped_ids'])} churches, grid index {state['grid_index']}")
    
    all_churches = []
    # Load existing results
    if OUTPUT_CSV.exists():
        with open(OUTPUT_CSV, encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                aid = row.get('id', '')
                if aid and aid not in state['scraped_ids']:
                    state['scraped_ids'].add(aid)
                    all_churches.append(row)
        print(f"Existing results: {len(all_churches)} churches")
    
    start_time = time.time()
    grid_hits = 0
    
    try:
        for gi, (lat, lng, city) in enumerate(CITIES):
            if gi < state['grid_index']:
                continue
            
            elapsed = time.time() - start_time
            minutes_per = elapsed / max(1, gi - state['grid_index'] + 1) / 60
            remaining = (len(CITIES) - gi) * minutes_per
            print(f"\n[{gi+1}/{len(CITIES)}] {city:20s} ({lat:.2f}, {lng:.2f}) ~{remaining:.1f}m remain")
            
            page = 1
            point_churches = 0
            api_errors = 0
            
            while True:
                data = fetch_churches(lat, lng, page, city)
                if not data:
                    api_errors += 1
                    if api_errors >= 3:
                        print(f"  Skipping (too many errors)")
                        break
                    time.sleep(2)
                    continue
                
                api_errors = 0
                churches = data.get('churches', [])
                if not churches and page == 1:
                    print(f"  No results")
                    break
                
                new_for_point = 0
                for ch in churches:
                    cid = ch.get('id', '')
                    if cid and cid not in state['scraped_ids']:
                        state['scraped_ids'].add(cid)
                        entry = extract_church(ch)
                        all_churches.append(entry)
                        new_for_point += 1
                        point_churches += 1
                
                if new_for_point > 0:
                    print(f"  Page {page}: +{new_for_point}")
                
                if not data.get('hasMoreItems') or not churches:
                    break
                
                page += 1
                time.sleep(0.2)
            
            if point_churches > 0:
                grid_hits += 1
            
            # Save progress periodically
            if (gi + 1) % 5 == 0 or point_churches > 0:
                save_results(all_churches)
                state['grid_index'] = gi
                with open(STATE_FILE, 'w') as f:
                    json.dump({
                        'scraped_ids': list(state['scraped_ids']),
                        'grid_index': gi,
                        'total': len(all_churches),
                    }, f)
    
    except KeyboardInterrupt:
        print("\nInterrupted, saving progress...")
    
    # Final save
    save_results(all_churches)
    with open(STATE_FILE, 'w') as f:
        json.dump({
            'scraped_ids': list(state['scraped_ids']),
            'grid_index': len(grid_points) - 1,
            'total': len(all_churches),
        }, f)
    
    elapsed = time.time() - start_time
    print(f"\n{'='*60}")
    print(f"Done! {len(all_churches)} churches from {grid_hits} grid points")
    print(f"Time: {elapsed/60:.1f} min")
    print(f"Saved to: {OUTPUT_CSV}")


def save_results(churches):
    """Save all churches to CSV."""
    if not churches:
        return
    fields = ['id', 'name', 'alt_name', 'address', 'address_2', 'city', 'state',
              'state_full', 'zip', 'country', 'phone', 'email', 'website',
              'latitude', 'longitude', 'conference', 'district', 'attendance',
              'ethnicity', 'english', 'spanish', 'korean', 'image_url']
    
    with open(OUTPUT_CSV, 'w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for ch in churches:
            w.writerow({k: ch.get(k, '') for k in fields})
    
    print(f"  Saved {len(churches)} churches to CSV")


if __name__ == '__main__':
    main()
