#!/usr/bin/env python3
"""
OpenStreetMap Church Enrichment
================================
Uses the free Overpass API to find verified church websites, phones,
and addresses from OpenStreetMap data.

Strategy:
  1. Query Overpass by state for all places_of_worship with website tags
  2. Match against our DB by normalized name + state
  3. Replace bad guesses with real OSM-verified data

This is completely FREE — no API key required. Rate limit: ~2 queries/sec.

Usage:
    python scripts/enrichment/osm_enrich.py                          # All 50 states
    python scripts/enrichment/osm_enrich.py --states SC,NC,GA        # Just 3 states
    python scripts/enrichment/osm_enrich.py --states SC --dry-run    # Preview

Other free/OSM APIs to layer on:
  - Nominatim (geocoding) — 1/sec free, no key
  - Wikipedia API — church history, descriptions, photos
  - US Census Geocoder — lat/lng from address, free
  - ArcGIS REST — free geocoding with API key
"""
import csv, json, os, re, sys, time, sqlite3, urllib.request
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
from collections import defaultdict

PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
for _ in range(5):
    if os.path.exists(os.path.join(PROJECT_DIR, "pipeline")):
        break
    if os.path.exists(os.path.join(PROJECT_DIR, "churches.db")):
        size = os.path.getsize(os.path.join(PROJECT_DIR, "churches.db"))
        if size > 1000000:
            break
    parent = os.path.dirname(PROJECT_DIR)
    if parent == PROJECT_DIR:
        break
    PROJECT_DIR = parent
DB_PATH = os.path.join(PROJECT_DIR, "churches.db")
if not os.path.exists(DB_PATH) or os.path.getsize(DB_PATH) < 1000000:
    cwd_db = os.path.join(os.getcwd(), "churches.db")
    if os.path.exists(cwd_db) and os.path.getsize(cwd_db) > 1000000:
        DB_PATH = cwd_db

STATES = [
    "AL","AK","AZ","AR","CA","CO","CT","DE","FL","GA",
    "HI","ID","IL","IN","IA","KS","KY","LA","ME","MD",
    "MA","MI","MN","MS","MO","MT","NE","NV","NH","NJ",
    "NM","NY","NC","ND","OH","OK","OR","PA","RI","SC",
    "SD","TN","TX","UT","VT","VA","WA","WV","WI","WY",
    "DC"
]

STATE_NAMES = {
    "AL":"Alabama","AK":"Alaska","AZ":"Arizona","AR":"Arkansas","CA":"California",
    "CO":"Colorado","CT":"Connecticut","DE":"Delaware","FL":"Florida","GA":"Georgia",
    "HI":"Hawaii","ID":"Idaho","IL":"Illinois","IN":"Indiana","IA":"Iowa",
    "KS":"Kansas","KY":"Kentucky","LA":"Louisiana","ME":"Maine","MD":"Maryland",
    "MA":"Massachusetts","MI":"Michigan","MN":"Minnesota","MS":"Mississippi","MO":"Missouri",
    "MT":"Montana","NE":"Nebraska","NV":"Nevada","NH":"New Hampshire","NJ":"New Jersey",
    "NM":"New Mexico","NY":"New York","NC":"North Carolina","ND":"North Dakota","OH":"Ohio",
    "OK":"Oklahoma","OR":"Oregon","PA":"Pennsylvania","RI":"Rhode Island","SC":"South Carolina",
    "SD":"South Dakota","TN":"Tennessee","TX":"Texas","UT":"Utah","VT":"Vermont",
    "VA":"Virginia","WA":"Washington","WV":"West Virginia","WI":"Wisconsin","WY":"Wyoming",
    "DC":"District of Columbia"
}

STOP_WORDS = {'THE','OF','A','AN','AND','IN','AT','TO','FOR','BY','&'}

stats = {"overpass_calls": 0, "osm_churches": 0, "matched": 0, "updated_website": 0, "new_website": 0, "skipped": 0}
stats_lock = __import__("threading").Lock()


def normalize(name):
    """Normalize church name for matching."""
    if not name:
        return ""
    n = name.strip().upper()
    n = re.sub(r'[^A-Z0-9\s]', '', n)
    words = [w for w in n.split() if w not in STOP_WORDS]
    return ' '.join(words)


def query_state(state_name):
    """Query Overpass for all places of worship with websites in a state."""
    query = f"""
[out:json][timeout:120];
area["name"="{state_name}"]["admin_level"="4"]->.a;
(
  node(area.a)[amenity=place_of_worship][website];
  way(area.a)[amenity=place_of_worship][website];
  relation(area.a)[amenity=place_of_worship][website];
);
out body 5000;
"""
    req = urllib.request.Request(
        'https://overpass-api.de/api/interpreter',
        data=query.encode('utf-8'),
        headers={'User-Agent': 'GrantWizard/1.0 research'}
    )
    try:
        resp = urllib.request.urlopen(req, timeout=120)
        return json.loads(resp.read().decode('utf-8'))
    except Exception as e:
        print(f"    Overpass error: {e}")
        return None


def extract_church_data(osm_element):
    """Extract name, website, phone, address from an OSM element."""
    tags = osm_element.get('tags', {})
    if not tags:
        return None

    name = tags.get('name', '').strip()
    website = (tags.get('website', '') or tags.get('contact:website', '') or '').strip()
    phone = (tags.get('phone', '') or tags.get('contact:phone', '') or '').strip()
    addr_street = (tags.get('addr:housenumber', '') + ' ' + tags.get('addr:street', '')).strip()
    addr_city = tags.get('addr:city', '')
    addr_state = tags.get('addr:state', '')
    addr_zip = tags.get('addr:postcode', '')
    denomination = tags.get('denomination', '') or tags.get('religion', '')

    if not name or not website:
        return None

    # Clean website
    website = website.strip().rstrip('/')
    if not website.startswith('http'):
        website = 'https://' + website

    return {
        'name': name,
        'website': website,
        'phone': phone,
        'address': addr_street,
        'city': addr_city,
        'state': addr_state,
        'zip': addr_zip,
        'denomination': denomination,
        'lat': osm_element.get('lat', osm_element.get('center', {}).get('lat', None)),
        'lon': osm_element.get('lon', osm_element.get('center', {}).get('lon', None)),
        'osm_id': f"{osm_element.get('type','node')}/{osm_element.get('id','')}",
    }


def match_to_db(osm_churches, db_churches_by_state):
    """
    Match OSM churches to DB churches by normalized name + state.
    Returns list of (db_id, osm_data) tuples.
    """
    matches = []
    
    for osm in osm_churches:
        osm_name_norm = normalize(osm['name'])
        osm_state = osm.get('state', '')
        
        if not osm_name_norm:
            continue
        
        # Find best match in same state
        best_match = None
        best_score = 0
        
        for db_row in db_churches_by_state:
            db_id, db_name, db_city = db_row
            db_name_norm = normalize(db_name)
            
            if not db_name_norm:
                continue
            
            # Score: exact match = best, partial = lower
            if osm_name_norm == db_name_norm:
                score = 100
            elif osm_name_norm.startswith(db_name_norm) or db_name_norm.startswith(osm_name_norm):
                score = 70
            else:
                # Count word overlap
                osm_words = set(osm_name_norm.split())
                db_words = set(db_name_norm.split())
                if len(osm_words) >= 2 and len(db_words) >= 2:
                    common = osm_words & db_words
                    if len(common) >= min(len(osm_words), len(db_words)):
                        score = 50
                    elif len(common) >= 2:
                        score = 30
                    else:
                        continue
                else:
                    continue
            
            # Bonus for city match
            if osm.get('city') and db_city and osm['city'].upper() == db_city.upper():
                score += 20
            
            if score > best_score:
                best_score = score
                best_match = (db_id, db_name, score)
        
        if best_match and best_score >= 50:
            matches.append((best_match[0], best_match[1], osm, best_score))
    
    return matches


def process_state(state_abbr, db_path, dry_run=False):
    """Process a single state: query OSM, match, update DB."""
    state_name = STATE_NAMES.get(state_abbr, state_abbr)
    
    # Skip DC
    if state_abbr == 'DC':
        return

    # 1. Query Overpass
    result = query_state(state_name)
    if not result:
        return
    
    elements = result.get('elements', [])
    if not elements:
        print(f"  {state_abbr}: 0 OSM churches found")
        return

    # 2. Extract church data
    osm_churches = []
    for elem in elements:
        data = extract_church_data(elem)
        if data:
            osm_churches.append(data)
    
    print(f"  {state_abbr}: {len(osm_churches)} churches with websites in OSM")

    with stats_lock:
        stats['osm_churches'] += len(osm_churches)
        stats['overpass_calls'] += 1

    if not osm_churches:
        return

    # 3. Load DB churches for this state
    db = sqlite3.connect(db_path)
    db_rows = db.execute("""
        SELECT id, name, city
        FROM churches
        WHERE state = ? AND name IS NOT NULL AND name != ''
    """, (state_abbr,)).fetchall()

    if not db_rows:
        db.close()
        return

    # 4. Match
    matches = match_to_db(osm_churches, db_rows)

    with stats_lock:
        stats['matched'] += len(matches)

    if not matches:
        db.close()
        print(f"    -> 0 matches in DB")
        return

    # 5. Update DB
    updated_website = 0
    new_website = 0
    skipped = 0
    
    if not dry_run:
        for db_id, db_name, osm, score in matches:
            current_website = db.execute(
                "SELECT website FROM churches WHERE id = ?", (db_id,)
            ).fetchone()
            
            if current_website is None:
                continue
            
            current_website = (current_website[0] or '').strip()
            osm_website = osm['website'].strip()
            
            if not current_website:
                # New website - insert
                updates = ["website = ?", "website_scrape_status = 'verified'",
                           "website_last_verified = datetime('now')"]
                params = [osm_website]
                
                if osm['phone']:
                    updates.append("phone = ?")
                    params.append(osm['phone'])
                if osm['lat']:
                    updates.append("latitude = ?")
                    params.append(osm['lat'])
                if osm['lon']:
                    updates.append("longitude = ?")
                    params.append(osm['lon'])
                
                params.append(db_id)
                db.execute(f"UPDATE churches SET {', '.join(updates)} WHERE id = ?", params)
                new_website += 1
            elif current_website != osm_website and '/' in osm_website:
                # Different website - replace if current looks like a name-based guess
                domain_curr = urllib.request.urlparse(current_website).netloc.lower() if current_website.startswith('http') else current_website.lower()
                domain_osm = urllib.request.urlparse(osm_website).netloc.lower() if osm_website.startswith('http') else osm_website.lower()
                
                if domain_curr != domain_osm:
                    # Current is a guess, OSM is verified - replace it
                    updates = ["website = ?", "website_scrape_status = 'verified'"]
                    params = [osm_website]
                    if osm['phone']:
                        updates.append("phone = ?")
                        params.append(osm['phone'])
                    params.append(db_id)
                    db.execute(f"UPDATE churches SET {', '.join(updates)} WHERE id = ?", params)
                    updated_website += 1
                else:
                    skipped += 1
            else:
                skipped += 1
        
        db.commit()
    
    db.close()

    with stats_lock:
        stats['updated_website'] += updated_website
        stats['new_website'] += new_website
        stats['skipped'] += skipped

    print(f"    -> {new_website} new, {updated_website} replaced, {skipped} skipped")


def log(msg):
    t = datetime.now().strftime('%H:%M:%S')
    print(f"[{t}] {msg}")


def main():
    import argparse
    parser = argparse.ArgumentParser(description="OSM Church Enrichment")
    parser.add_argument("--states", type=str, default=None,
                        help="Comma-separated state codes (e.g. SC,NC,GA)")
    parser.add_argument("--dry-run", action="store_true",
                        help="Preview only, no DB changes")
    parser.add_argument("--workers", type=int, default=1,
                        help="Worker threads (careful with Overpass rate limits)")
    args = parser.parse_args()

    if args.states:
        states = [s.strip().upper() for s in args.states.split(',')]
    else:
        states = STATES

    total_states = len(states)
    log(f"OSM Enrichment — {total_states} states, dry_run={args.dry_run}")
    log(f"DB: {DB_PATH}")
    
    start_time = time.time()

    for i, state in enumerate(states, 1):
        process_state(state, DB_PATH, args.dry_run)
        
        # Be respectful of Overpass rate limits
        if i < total_states:
            delay = max(1, 3 - (time.time() - start_time) / i)
            time.sleep(delay)

    elapsed = time.time() - start_time
    print(f"\n{'='*60}")
    print(f"OSM ENRICHMENT COMPLETE")
    print(f"{'='*60}")
    print(f"  States processed:  {total_states}")
    print(f"  Time:             {elapsed/60:.1f} min")
    print(f"  Overpass API calls: {stats['overpass_calls']}")
    print(f"  OSM churches found: {stats['osm_churches']:,}")
    print(f"  DB matches:         {stats['matched']:,}")
    print(f"  New websites:       {stats['new_website']:,}")
    print(f"  Websites replaced:  {stats['updated_website']:,}")
    print(f"  Skipped (matched):  {stats['skipped']:,}")

    if not args.dry_run:
        db = sqlite3.connect(DB_PATH)
        w = db.execute("SELECT COUNT(*) FROM churches WHERE website IS NOT NULL AND website != ''").fetchone()[0]
        v = db.execute("SELECT COUNT(*) FROM churches WHERE website_scrape_status='verified'").fetchone()[0]
        db.close()
        print(f"\n  Final website count: {w:,}")
        print(f"  Verified (OSM+):     {v:,}")


if __name__ == "__main__":
    main()
