"""
Import Mapping Saints data into GRID churches.db.

Source: Mapping Saints (https://saints.dh.gu.se/) — CC-BY-SA 4.0 / CC0
Project: Mapping Lived Religion — Medieval cults of saints in Sweden and Finland
API: Django REST Framework at https://saints.dh.gu.se/api/
GitHub: https://github.com/gu-gridh/saints

Classifications:
  - ACTIVE: Parish church, Cathedral, Town church, Church, Chapel, Abbey, Monastery,
            Modern church, Church (Religious Order), Chapel (Hospital)
  - ARCHAEOLOGICAL: Runestone, Holy Well, Wayside Shrine, Private church (ruined),
                    Village, Estate, Castle, Landscape feature, Unknown, Farm, Bridge, etc.

Matching strategy:
  1. Wikidata ID cross-reference (most reliable)
  2. Name + spatial proximity (<500m)
  3. Name + municipality
  4. Unmatched → new entry (tagged appropriately)

Usage: python scripts/enrichment/import_mapping_saints.py
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

import json
import time
import math
from collections import Counter, defaultdict
from datetime import datetime, timezone

import urllib.request
import urllib.error

from gw_db import connect, Provenance

# ── Configuration ──
API_BASE = "https://saints.dh.gu.se/api"
PAGE_SIZE = 200
CHUNK_SIZE = 500
REQUEST_DELAY = 0.3  # Be polite to their server

# ── Place type → GRID classification ──
# ACTIVE: currently-standing worship sites still potentially in use
ACTIVE_PLACE_TYPES = {
    'Parish church',       # 15 — sockenkyrka / pitäjänkirkko
    'Cathedral',           # 14 — domkyrka / katedraali
    'Town church',         # 18 — stadskyrka / kaupunginkirkko
    'Church',              # 54 — kyrka / kirkko (generic)
    'Chapel',              # 17 — kapell / kappeli
    'Abbey',               # 13 — kloster (abbey church)
    'Monastery',           # 34 — luostari
    'Modern church',       # 30 — modern kyrka / moderni kirkko
    'Church, Religious Order',  # 44 — ordenskyrka / sääntökuntakirkko
    'Chapel, Hospital',    # 24 — hospitalskapell
    'Priory',              # 32 — luostari
    'Religious House',     # 31 — ordenshus
    'Friary',              # 35 — franciskankonvent
    'Nunnery',             # 28 — nunnekloster
    'Other churches',      # 5  — andra kyrkor
}

# ARCHAEOLOGICAL: historical sites, not functioning worship spaces
ARCHAEOLOGICAL_PLACE_TYPES = {
    'Runestone',           # 45 — runsten / riimukivi
    'Holy Well',           # 19 — helig källa / pyhä lähde
    'Wayside Shrine',      # 20 — andaktsplats / pyhäkkö
    'Private church',      # 16 — gårdskyrka (often ruined)
    'Chapel, private',     # 25 — kappeli, yksityinen
    'Altar in church',     # 58 — sidoaltare (inside existing church, not standalone)
    'Chapel in church',    # 61 — sidokor (inside existing church)
    'Devotional site',     # 7  — kultplats (generic)
}

# NON-RELIGIOUS / CONTEXTUAL: places that aren't worship sites at all
NON_RELIGIOUS_PLACE_TYPES = {
    'Village', 'Town', 'City', 'Estate', 'Castle', 'Farm', 'Farmland',
    'Homestead', 'Manor Farm', 'Market place', 'Port', 'Bridge',
    'Mill', 'Mine', 'Foundry', 'School', 'Hospital', 'Tower',
    'Inn', 'Guild house', 'Lake', 'Sea', 'Sound', 'Stream',
    'Landscape feature', 'Natural Object', 'Province', 'Diocese',
    'Ecclesiastical Province', 'Unknown', 'Field', 'Pilgrim Shelter',
    'House of canons', 'Chapter house', 'Townhouse', 'Royal estate',
    'Thingstead', 'Gate', 'Harbour',
}

# Taxonomy mappings for archaeological sites
ARCHAEOLOGICAL_TAXONOMY = {
    'Runestone': 637,      # Megalithic Religion (runestones are memorial/ritual stones)
    'Holy Well': 53,        # Pagan (holy wells often pre-Christian)
    'Wayside Shrine': 53,   # Pagan
    'Devotional site': 53,  # Pagan
}

def fetch_json(url, retries=3):
    """Fetch JSON from Saints API with retry logic."""
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers={'User-Agent': 'GRID/1.0 (research project)'})
            with urllib.request.urlopen(req, timeout=30) as resp:
                data = json.loads(resp.read().decode())
            return data
        except Exception as e:
            if attempt < retries - 1:
                time.sleep(2 ** attempt)
            else:
                print(f"  ⚠ Failed: {url} — {e}")
                return None

def fetch_all(endpoint):
    """Fetch all pages from a paginated Saints API endpoint."""
    items = []
    url = f"{API_BASE}/{endpoint}/?limit={PAGE_SIZE}"
    page = 1
    while url:
        data = fetch_json(url)
        if not data:
            break
        items.extend(data.get('results', []))
        url = data.get('next')
        if url:
            page += 1
            time.sleep(REQUEST_DELAY)
            if page % 5 == 0:
                print(f"  Page {page}... ({len(items)} items)")
    return items

def classify_place(place_type_name):
    """Classify a Mapping Saints place type into GRID category."""
    if place_type_name in ACTIVE_PLACE_TYPES:
        return 'active'
    elif place_type_name in ARCHAEOLOGICAL_PLACE_TYPES:
        return 'archaeological'
    elif place_type_name in NON_RELIGIOUS_PLACE_TYPES:
        return 'non_religious'
    else:
        print(f"  ⚠ Unknown place type: '{place_type_name}' — treating as non_religious")
        return 'non_religious'

def haversine_km(lat1, lon1, lat2, lon2):
    """Haversine distance in km."""
    R = 6371
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat/2)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon/2)**2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

def extract_wikidata_id(wikidata_url):
    """Extract Wikidata Q-ID from URL like https://wikidata.org/wiki/Q4682106"""
    if not wikidata_url:
        return None
    if '/wiki/' in wikidata_url:
        qid = wikidata_url.split('/wiki/')[-1].strip()
        if qid.startswith('Q'):
            return qid
    return None

def main():
    start_time = time.time()
    db = connect()
    db.row_factory = None  # Use tuple mode for faster processing
    
    # ── Step 1: Fetch all Mapping Saints data ──
    print("=" * 70)
    print("Mapping Saints → GRID Import")
    print("=" * 70)
    
    print("\n[1/6] Fetching places from Saints API...")
    places_raw = fetch_all("place")
    print(f"  ✅ {len(places_raw)} places fetched")
    
    print("\n[2/6] Fetching reference data...")
    place_types_raw = fetch_all("placetype")
    dioceses_raw = fetch_all("diocese")
    print(f"  ✅ {len(place_types_raw)} place types, {len(dioceses_raw)} dioceses")
    
    # Build lookup maps
    place_type_map = {pt['id']: pt for pt in place_types_raw}
    diocese_map = {d['id']: d['name'] for d in dioceses_raw}
    
    # ── Step 2: Classify and filter places ──
    print("\n[3/6] Classifying places...")
    
    stats = Counter()
    active_places = []
    archaeological_places = []
    skipped = []
    
    for p in places_raw:
        pt = place_type_map.get(p.get('place_type', {}).get('id', 0), {})
        pt_name = pt.get('name', 'Unknown')
        category = classify_place(pt_name)
        stats[category] += 1
        
        # Skip non-religious
        if category == 'non_religious':
            skipped.append(p)
            continue
        
        # Extract coordinates
        geom = p.get('geometry', {})
        if not geom or geom.get('type') != 'Point':
            continue
        lon, lat = geom['coordinates']
        if not lat or not lon:
            continue
        
        # Extract Wikidata ID
        wikidata_id = extract_wikidata_id(p.get('wikidata', ''))
        
        # Extract parish/diocese info
        parish = p.get('parish', {}) or {}
        diocese_id = None
        diocese_name = None
        if parish.get('medival_organization'):
            diocese_id = parish['medival_organization']['id']
            diocese_name = parish['medival_organization']['name']
        
        # Extract saint dedications from cult relations
        saints = []
        for cult in p.get('relation_cult_place', []):
            saint_name = cult.get('relation_cult_agent', '')
            cult_type = cult.get('cult_type', '')
            minyear = cult.get('minyear', '')
            maxyear = cult.get('maxyear', '')
            if saint_name:
                saints.append({
                    'saint': saint_name,
                    'type': cult_type,
                    'from': minyear,
                    'to': maxyear,
                })
        
        entry = {
            'mapping_saints_id': p['id'],
            'name': p['name'],
            'latitude': lat,
            'longitude': lon,
            'place_type': pt_name,
            'category': category,
            'country': p.get('country', ''),
            'county': p.get('county', ''),
            'municipality': p.get('municipality', ''),
            'construction_date': p.get('construction_date', ''),
            'not_before': p.get('not_before', ''),
            'not_after': p.get('not_after', ''),
            'comment': p.get('comment', ''),
            'wikidata_id': wikidata_id,
            'wikidata_url': p.get('wikidata', ''),
            'bebr_id': p.get('bebr_id', ''),
            'fmis_id': p.get('fmis_id', ''),
            'diocese_name': diocese_name,
            'diocese_id': diocese_id,
            'parish_name': parish.get('name', ''),
            'saints': saints,
            'certainty': p.get('certainty', True),
        }
        
        if category == 'active':
            active_places.append(entry)
        else:
            archaeological_places.append(entry)
    
    print(f"\n  Active worship sites:     {len(active_places):>5}")
    print(f"  Archaeological/heritage:  {len(archaeological_places):>5}")
    print(f"  Non-religious (skipped):  {len(skipped):>5}")
    print(f"  Total:                    {len(places_raw):>5}")
    
    # Breakdown of active types
    active_types = Counter(p['place_type'] for p in active_places)
    print(f"\n  Active place types:")
    for t, n in active_types.most_common():
        print(f"    {t:30s} {n:>4}")
    
    arch_types = Counter(p['place_type'] for p in archaeological_places)
    print(f"\n  Archaeological place types:")
    for t, n in arch_types.most_common():
        print(f"    {t:30s} {n:>4}")
    
    # ── Step 3: Build GRID lookup structures ──
    print("\n[4/6] Building GRID lookup indexes...")
    
    # Load existing GRID churches in Sweden, Finland, Norway
    target_countries = ('SE', 'FI', 'NO', 'DK', 'DE', 'EE')
    
    # Wikidata index — sources contain wikidata URLs like 'https://www.wikidata.org/wiki/Q4682106'
    print("  Building Wikidata index...")
    wd_index = {}
    cur = db.execute("""
        SELECT id, name, latitude, longitude, country, source
        FROM churches
        WHERE source LIKE '%wikidata%wiki/Q%'
    """)
    for row in cur.fetchall():
        qid = extract_wikidata_id(row[5])
        if qid:
            wd_index[qid] = {
                'grid_id': row[0], 'name': row[1],
                'lat': row[2], 'lon': row[3], 'country': row[4],
            }
    print(f"  ✅ {len(wd_index):,} Wikidata-linked GRID entries")
    
    # Spatial index for SE/FI/NO
    print("  Building spatial index (SE/FI/NO)...")
    spatial_index = []
    cur = db.execute("""
        SELECT id, name, latitude, longitude, country, city
        FROM churches
        WHERE country IN ('SE', 'FI', 'NO', 'DK', 'DE', 'EE')
          AND latitude IS NOT NULL AND longitude IS NOT NULL
    """)
    for row in cur.fetchall():
        spatial_index.append({
            'grid_id': row[0], 'name': row[1],
            'lat': row[2], 'lon': row[3],
            'country': row[4], 'city': row[5] or '',
        })
    print(f"  ✅ {len(spatial_index):,} geo-indexed entries in target countries")
    
    # ── Step 4: Match active places to GRID ──
    print("\n[5/6] Matching active places to GRID churches...")
    
    SPATIAL_THRESHOLD_KM = 0.5  # 500m
    matched = []
    unmatched_active = []
    
    for p in active_places:
        match = None
        match_method = None
        
        # Try 1: Wikidata ID match
        if p['wikidata_id'] and p['wikidata_id'] in wd_index:
            match = wd_index[p['wikidata_id']]
            match_method = 'wikidata'
        
        # Try 2: Name + spatial proximity
        if not match:
            best_dist = SPATIAL_THRESHOLD_KM
            for entry in spatial_index:
                # Quick country filter
                ms_country = p['country']
                if ms_country == 'Sweden':
                    iso2 = 'SE'
                elif ms_country == 'Finland':
                    iso2 = 'FI'
                elif ms_country == 'Norway':
                    iso2 = 'NO'
                elif ms_country == 'Denmark':
                    iso2 = 'DK'
                elif ms_country == 'Germany':
                    iso2 = 'DE'
                elif ms_country == 'Estonia':
                    iso2 = 'EE'
                else:
                    continue
                
                if entry['country'] != iso2:
                    continue
                
                dist = haversine_km(p['latitude'], p['longitude'], entry['lat'], entry['lon'])
                if dist < best_dist:
                    # Name similarity check
                    ms_name = p['name'].lower().strip()
                    grid_name = (entry['name'] or '').lower().strip()
                    if ms_name == grid_name or ms_name in grid_name or grid_name in ms_name:
                        best_dist = dist
                        match = entry
                        match_method = f'spatial_{dist*1000:.0f}m'
        
        if match:
            matched.append((p, match, match_method))
            print(f"  ✅ {p['name'][:40]:40s} | {p['country'][:10]:10s} → GRID #{match['grid_id']:>10} ({match_method})")
        else:
            unmatched_active.append(p)
            print(f"  ⬜ {p['name'][:40]:40s} | {p['country'][:10]:10s} → UNMATCHED")
    
    print(f"\n  Matched:   {len(matched)}")
    print(f"  Unmatched: {len(unmatched_active)}")
    
    # ── Step 6: Apply enrichments ──
    print("\n[6/6] Applying enrichments to matched churches...")
    
    # Collect all fields to add
    enrichment_count = 0
    new_entries_active = []
    new_entries_archaeological = []
    
    with Provenance(db, "import_mapping_saints.py", source="mapping_saints",
                    action="enriched", fields="mapping_saints_id,construction_date,"
                    "mapping_saints_place_type,mapping_saints_diocese,"
                    "mapping_saints_saints,comment"):
        
        # Enrich matched churches
        for p, match, method in matched:
            grid_id = match['grid_id']
            saints_json = json.dumps(p['saints'], ensure_ascii=False) if p['saints'] else None
            
            # Build UPDATE with only non-empty fields
            updates = []
            params = []
            
            if p['construction_date']:
                # Use building_year for construction date
                # Mapping Saints format varies: '1170-1199', '1777-1779', '1058-1058'
                cd = p['construction_date'].strip()
                if '-' in cd:
                    # Take the first year from a range
                    parts = cd.split('-')
                    try:
                        year = int(parts[0])
                        updates.append("building_year = ?")
                        params.append(year)
                    except ValueError:
                        pass
                elif cd.isdigit():
                    updates.append("building_year = ?")
                    params.append(int(cd))
            
            updates.append("mapping_saints_id = ?")
            params.append(p['mapping_saints_id'])
            
            updates.append("mapping_saints_place_type = ?")
            params.append(p['place_type'])
            
            if p['diocese_name']:
                updates.append("mapping_saints_diocese = ?")
                params.append(p['diocese_name'])
            
            if saints_json:
                updates.append("mapping_saints_saints = ?")
                params.append(saints_json)
            
            if p['comment']:
                # Truncate HTML comments to 2000 chars
                comment = p['comment'][:2000]
                updates.append("notes = COALESCE(notes || CHAR(10) || CHAR(10) || ?, ?)")
                params.extend([f"[Mapping Saints] {comment}", f"[Mapping Saints] {comment}"])
            
            if p['bebr_id']:
                updates.append("mapping_saints_bebr = ?")
                params.append(p['bebr_id'])
            
            if p['fmis_id']:
                updates.append("mapping_saints_fmis = ?")
                params.append(p['fmis_id'])
            
            updates.append("mapping_saints_matched = ?")
            params.append(method)
            
            updates.append("mapping_saints_updated = ?")
            params.append(datetime.now(timezone.utc).isoformat())
            
            params.append(grid_id)
            sql = f"UPDATE churches SET {', '.join(updates)} WHERE id = ?"
            db.execute(sql, params)
            enrichment_count += 1
        
        # ── Create new entries for unmatched active places ──
        if unmatched_active:
            # Get max ID
            cur = db.execute("SELECT MAX(id) FROM churches")
            next_id = (cur.fetchone()[0] or 0) + 1
            
            print(f"\n  Creating {len(unmatched_active)} new active entries...")
            
            for p in unmatched_active:
                saints_json = json.dumps(p['saints'], ensure_ascii=False) if p['saints'] else None
                
                # Map country
                country_map = {
                    'Sweden': 'SE', 'Finland': 'FI', 'Norway': 'NO',
                    'Denmark': 'DK', 'Germany': 'DE', 'Estonia': 'EE',
                }
                iso2 = country_map.get(p['country'], p['country'][:2].upper() if p['country'] else '')
                
                # Parse construction date to building_year
                build_year = None
                if p['construction_date']:
                    cd = p['construction_date'].strip()
                    if '-' in cd:
                        try:
                            build_year = int(cd.split('-')[0])
                        except ValueError:
                            pass
                    elif cd.isdigit():
                        build_year = int(cd)

                db.execute("""
                    INSERT INTO churches (id, name, latitude, longitude, country,
                        county, city, taxonomy_id, faith, source,
                        mapping_saints_id, mapping_saints_place_type,
                        mapping_saints_diocese, mapping_saints_saints,
                        building_year, notes,
                        mapping_saints_matched, mapping_saints_updated)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                            ?, ?, ?, ?, ?, ?,
                            ?, ?)
                """, (
                    next_id,
                    p['name'],
                    p['latitude'],
                    p['longitude'],
                    iso2,
                    p['county'],
                    p['municipality'],
                    2,  # Christian (default for medieval European churches)
                    'Christian',
                    'mapping_saints',
                    p['mapping_saints_id'],
                    p['place_type'],
                    p['diocese_name'],
                    saints_json,
                    build_year,
                    f"[Mapping Saints] {p['comment'][:2000]}" if p['comment'] else None,
                    'new_entry',
                    datetime.now(timezone.utc).isoformat(),
                ))
                new_entries_active.append(next_id)
                print(f"  🆕 #{next_id} | {p['name'][:40]:40s} | {p['country']}")
                next_id += 1
        
        # ── Create entries for archaeological sites (separate, not in active churches table) ──
        if archaeological_places:
            print(f"\n  Creating {len(archaeological_places)} archaeological entries...")
            
            for p in archaeological_places:
                # Assign taxonomy
                tax_id = ARCHAEOLOGICAL_TAXONOMY.get(p['place_type'], 637)  # Default: Megalithic
                
                country_map = {
                    'Sweden': 'SE', 'Finland': 'FI', 'Norway': 'NO',
                    'Denmark': 'DK', 'Germany': 'DE', 'Estonia': 'EE',
                }
                iso2 = country_map.get(p['country'], p['country'][:2].upper() if p['country'] else '')
                
                # Parse construction date
                build_year = None
                if p['construction_date']:
                    cd = p['construction_date'].strip()
                    if '-' in cd:
                        try:
                            build_year = int(cd.split('-')[0])
                        except ValueError:
                            pass
                    elif cd.isdigit():
                        build_year = int(cd)
                if not build_year and p.get('not_before'):
                    nb = str(p['not_before']).strip()
                    if '-' in nb:
                        try:
                            build_year = int(nb.split('-')[0])
                        except ValueError:
                            pass
                    elif nb.isdigit() and len(nb) == 4:
                        build_year = int(nb)

                db.execute("""
                    INSERT INTO churches (id, name, latitude, longitude, country,
                        county, city, taxonomy_id, faith, source,
                        mapping_saints_id, mapping_saints_place_type,
                        mapping_saints_diocese,
                        building_year, notes,
                        landmark_type, mapping_saints_matched,
                        mapping_saints_updated)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                            ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    next_id,
                    p['name'],
                    p['latitude'],
                    p['longitude'],
                    iso2,
                    p['county'],
                    p['municipality'],
                    tax_id,
                    'Pagan',
                    'mapping_saints',
                    p['mapping_saints_id'],
                    p['place_type'],
                    p['diocese_name'],
                    build_year,
                    f"[Mapping Saints] {p['comment'][:2000]}" if p['comment'] else None,
                    p['place_type'].lower().replace(' ', '_').replace(',', ''),
                    'archaeological_new',
                    datetime.now(timezone.utc).isoformat(),
                ))
                new_entries_archaeological.append(next_id)
                icon = '🪨' if p['place_type'] == 'Runestone' else '💧' if p['place_type'] == 'Holy Well' else '🏛️'
                print(f"  {icon} #{next_id} | {p['name'][:40]:40s} | {p['place_type']:25s} | {p['country']}")
                next_id += 1
    
    db.commit()
    
    # ── Summary ──
    elapsed = time.time() - start_time
    print("\n" + "=" * 70)
    print("IMPORT COMPLETE")
    print("=" * 70)
    print(f"  Active places fetched:           {len(active_places):>5}")
    print(f"  Matched to existing GRID:        {len(matched):>5}")
    print(f"  Enriched (fields updated):       {enrichment_count:>5}")
    print(f"  New active entries created:      {len(new_entries_active):>5}")
    print(f"  New archaeological entries:      {len(new_entries_archaeological):>5}")
    print(f"  Non-religious skipped:           {len(skipped):>5}")
    print(f"  Total new GRID entries:          {len(new_entries_active) + len(new_entries_archaeological):>5}")
    print(f"\n  Elapsed: {elapsed:.1f}s")

if __name__ == '__main__':
    main()
