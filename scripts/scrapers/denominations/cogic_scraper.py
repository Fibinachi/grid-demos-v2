#!/usr/bin/env python3
"""
Scraper for Church of God in Christ (COGIC) national church directory.
Source: https://www.cogic.org/locator/
Output: data/denom/cogic_churches.csv
"""

import urllib.request, urllib.parse, ssl, json, csv, os, sys, re, time
from datetime import datetime
from pathlib import Path

BASE = 'https://www.cogic.org/locator/views/'
UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
OUT = Path('data/denom/cogic_churches.csv')
STATE_FILE = Path('data/denom/cogic_scraper_state.json')

ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

# US states and territories only (skip international)
US_STATES = {
    ' Alabama', ' Alaska', ' Arizona', ' Arkansas', ' California',
    ' Colorado', ' Connecticut', ' Delaware', ' District of Columbia',
    ' Florida', ' Georgia', ' Hawaii', ' Idaho', ' Illinois',
    ' Indiana', ' Iowa', ' Kansas', ' Kentucky', ' Louisiana',
    ' Maine', ' Maryland', ' Massachusetts', ' Michigan', ' Minnesota',
    ' Mississippi', ' Missouri', ' Montana', ' Nebraska', ' Nevada',
    ' New Hampshire', ' New Jersey', ' New Mexico', ' New York',
    ' North Carolina', ' North Dakota', ' Ohio', ' Oklahoma',
    ' Oregon', ' Pennsylvania', ' Rhode Island', ' South Carolina',
    ' South Dakota', ' Tennessee', ' Texas', ' Utah', ' Vermont',
    ' Virginia', ' Washington', ' West Virginia', ' Wisconsin', ' Wyoming',
    # Territories
    ' Puerto Rico', ' VI',
}

def log(msg):
    print(f'[{datetime.now().strftime("%H:%M:%S")}] {msg}', flush=True)

def post(script, data, timeout=15):
    """POST to a COGIC view script and return decoded HTML."""
    encoded = urllib.parse.urlencode(data).encode()
    req = urllib.request.Request(BASE + script, data=encoded, headers={'User-Agent': UA})
    for attempt in range(3):
        try:
            resp = urllib.request.urlopen(req, context=ctx, timeout=timeout)
            return resp.read().decode('utf-8', 'replace')
        except Exception as e:
            if attempt < 2:
                log(f'  Retry {attempt+1}/3: {e}')
                time.sleep(2)
            else:
                log(f'  Failed after 3 attempts: {e}')
    return ''

def extract_items(html, pattern):
    """Extract items with counts from HTML like 'CityName 12'."""
    return re.findall(pattern, html)

def parse_churches(html):
    """Parse church listing HTML into dicts."""
    churches = []
    # Each church is in an <li> with an <a class="displayStoreDetails" id="NNNN">
    # Structure: <a id="NNNN"><h3>Name</h3><div>Pastor info</div><p>Address City State Zip</p>...
    pattern = r'displayStoreDetails"\s+id="(\d+)".*?<h3>(.*?)</h3>.*?<div>(.*?)</div>.*?<p>(.*?)</p>'
    matches = re.findall(pattern, html, re.DOTALL)
    for store_id, name_html, pastor_html, addr_html in matches:
        name = re.sub(r'<[^>]+>', '', name_html).strip()
        name = re.sub(r'\s+', ' ', name)
        
        pastor = re.sub(r'<[^>]+>', '', pastor_html).strip()
        pastor = re.sub(r'\s+', ' ', pastor)
        # Remove leading "Inc." or similar
        if pastor.upper().startswith('INC'):
            pastor = pastor[3:].strip()
        if pastor.upper().startswith('PASTOR'):
            pastor = pastor[6:].strip()
        if pastor.upper().startswith('ELDER'):
            pastor = pastor[5:].strip()
        if pastor.upper().startswith('BISHOP'):
            pastor = pastor[6:].strip()
        pastor = pastor.strip()
        
        address = re.sub(r'<[^>]+>', '', addr_html).strip()
        address = re.sub(r'\s+', ' ', address)
        
        # Parse address: "1120 W 20th Street  Cheyenne  Wyoming 8201"
        parts = address.rsplit(' ', 2)
        church = {
            'store_id': store_id,
            'name': name,
            'pastor': pastor,
            'address_raw': address,
        }
        
        if len(parts) >= 3:
            church['zip'] = parts[-1]
            church['state_guess'] = parts[-2]
            church['city_guess'] = parts[-3]
            church['address'] = ' '.join(parts[:-3]) if len(parts) > 3 else ''
        
        # Phone from the listing (not always present)
        phone_match = re.search(r'(\d{3}[-\s.]?\d{3}[-\s.]?\d{4})', html)
        if phone_match:
            church['phone'] = phone_match.group(1)
        
        churches.append(church)
    return churches

def get_store_details(store_id):
    """Get detailed info for a single church (lat/lng)."""
    criteria = json.dumps({'feed': 'store', 'id': int(store_id)})
    html = post('display_store_details.php', {'criteria': criteria})
    if not html:
        return {}
    
    details = {'store_id': store_id}
    
    # Parse JSON response
    try:
        data = json.loads(html)
        if isinstance(data, dict):
            details['lat'] = data.get('lat', '')
            details['lng'] = data.get('lng', '')
    except:
        pass
    
    return details

def load_state():
    """Load scraper state for resume."""
    if STATE_FILE.exists():
        with open(STATE_FILE) as f:
            return json.load(f)
    return {'states_done': [], 'churches': [], 'seen_ids': set()}

def save_state(state):
    """Save scraper state."""
    state['seen_ids'] = list(state['seen_ids'])  # Convert set for JSON
    with open(STATE_FILE, 'w') as f:
        json.dump(state, f)
    state['seen_ids'] = set(state['seen_ids'])  # Convert back

def main():
    resume = '--resume' in sys.argv
    state = load_state() if resume else {'states_done': [], 'churches': [], 'seen_ids': set()}
    
    if isinstance(state.get('seen_ids'), list):
        state['seen_ids'] = set(state['seen_ids'])
    
    log(f'COGIC Church Scraper')
    log(f'Resume mode: {resume}')
    log(f'Existing churches: {len(state["churches"]):,}')
    log(f'Existing seen IDs: {len(state["seen_ids"]):,}')
    
    # Get all states
    states_html = post('display_states_page.php', {})
    
    # Extract state names and counts from links
    state_pattern = r'data-state="([^"]+)"[^>]*>([^<]+)<span[^>]*>.*?<font[^>]*>(\d+)<'
    state_matches = re.findall(state_pattern, states_html, re.DOTALL)
    
    us_states_found = []
    for ds, name, count in state_matches:
        state_name = ds.strip()
        if ds in US_STATES:  # ds has leading space
            us_states_found.append((ds, name.strip(), int(count)))
    
    log(f'Found {len(us_states_found)} US states with {sum(s[2] for s in us_states_found):,} total churches')
    
    for ds, name, total in us_states_found:
        if ds in state['states_done']:
            log(f'[{name}] Skipping (already done)')
            continue
        
        log(f'[{name}] {total:,} churches - getting cities...')
        
        # Get cities for this state
        cities_html = post('display_cities_page.php', {'state': ds})
        if not cities_html:
            log(f'  No cities response for {name}, skipping')
            state['states_done'].append(ds)
            save_state(state)
            continue
        
        # Extract cities: data-city=" Cheyenne"> Cheyenne<span...
        city_pattern = r'data-city="([^"]+)"[^>]*>([^<]+)<span'
        city_matches = re.findall(city_pattern, cities_html)
        
        state_churches = 0
        for idx, (dc, city_name) in enumerate(city_matches):
            city = dc.strip()
            if not city:
                continue
            
            if idx % 20 == 0:
                log(f'  [{name}] City {idx+1}/{len(city_matches)}: {city}')
            
            # Get churches in this city
            criteria = json.dumps({'city': dc, 'nb_display': 500})
            list_html = post('display_stores_list.php', {'criteria': criteria})
            
            if not list_html:
                continue
            
            churches = parse_churches(list_html)
            if not churches:
                continue
            
            for ch in churches:
                if ch['store_id'] not in state['seen_ids']:
                    state['seen_ids'].add(ch['store_id'])
                    state['churches'].append(ch)
                    state_churches += 1
            
            # Brief pause between cities to be polite
            time.sleep(0.1)
        
        state['states_done'].append(ds)
        log(f'  +{state_churches} new churches (total: {len(state["churches"])})')
        
        # Save progress after each state
        save_state(state)
    
    # Export to CSV
    log(f'\nExporting {len(state["churches"]):,} churches to CSV...')
    
    OUT.parent.mkdir(parents=True, exist_ok=True)
    fields = ['store_id', 'name', 'address', 'city_guess', 'state_guess', 'zip', 'pastor', 'phone', 'address_raw']
    with open(OUT, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=fields, extrasaction='ignore')
        writer.writeheader()
        for ch in state['churches']:
            writer.writerow(ch)
    
    log(f'Done! {len(state["churches"]):,} churches saved to {OUT}')

if __name__ == '__main__':
    main()
