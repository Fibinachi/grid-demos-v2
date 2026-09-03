#!/usr/bin/env python3
"""
Global Scientology Organization Scraper (OpenStreetMap)
=======================================================
Queries OSM's Overpass API for Scientology organizations worldwide.
OSM tags: religion=scientologist, denomination=scientology, name contains "Scientology"

For each org found, classifies by type using name patterns:
  Class V Org, Ideal Org, Advanced Org, Saint Hill, Flag Service,
  Flag Ship Service, Celebrity Centre, Mission, Support Organization

Usage:
    python scripts/enrichment/scrape_scientology_global.py --dry-run
    python scripts/enrichment/scrape_scientology_global.py
    python scripts/enrichment/scrape_scientology_global.py --merge
"""
import argparse, json, os, re, sqlite3, time, urllib.request, urllib.parse
from datetime import datetime

PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
OUTPUT = os.path.join(PROJECT_DIR, 'data', 'scientology_global.json')
DB_PATH = os.path.join(PROJECT_DIR, 'churches.db')
OVERAPSS_URL = "https://overpass-api.de/api/interpreter"

# Query ALL Scientology orgs globally via OSM
QUERY = """
[out:json][timeout:180];
(
  node["religion"="scientologist"]({{bbox}});
  way["religion"="scientologist"]({{bbox}});
  node["denomination"="scientology"]({{bbox}});
  way["denomination"="scientology"]({{bbox}});
  node["name"~"Church of Scientology|Scientology|Celebrity Centre|Narconon",i]({{bbox}});
  way["name"~"Church of Scientology|Scientology|Celebrity Centre|Narconon",i]({{bbox}});
);
out center meta;
"""

# We need to query continent by continent due to Overpass timeout limits
CONTINENTS = [
    ("North America", [-168, 5, -52, 85]),
    ("South America", [-82, -60, -32, 12]),
    ("Europe", [-25, 34, 40, 72]),
    ("Africa", [-20, -38, 52, 38]),
    ("Asia", [35, -12, 155, 55]),
    ("Oceania", [110, -50, 180, 0]),
]


def classify_type(name, tags):
    """Classify org type based on name and OSM tags."""
    nl = (name or '').lower()
    
    if re.search(r'\bflag\b.*\bservice\b|\bflag\s+land\s+base\b|clearwater.*flag', nl):
        return 'Flag Service Org'
    if re.search(r'\bfreewinds\b|\bflag\s+ship\b', nl):
        return 'Flag Ship Service Org'
    if re.search(r'\badvanced\s+(org|organization)\b|\badvanced.*saint.?hill\b', nl):
        return 'Advanced Org'
    if re.search(r'\bsaint.?hill\b|\bst\.?\s*hill\b', nl) and 'advanced' not in nl:
        return 'Saint Hill Org'
    if re.search(r'\bideal\b', nl):
        return 'Ideal Org'
    if re.search(r'\bcelebrity\s*(centre|center)\b', nl):
        return 'Celebrity Centre'
    if re.search(r'\bmission\b', nl):
        return 'Mission'
    if re.search(r'\bnarconon\b', nl):
        return 'Narconon'
    if re.search(r'\bcriminon\b', nl):
        return 'Criminon'
    if re.search(r'\bapplied\s*scholastics?\b', nl):
        return 'Applied Scholastics'
    if re.search(r'\bwise?\b', nl):
        return 'WISE'
    if re.search(r'\bgolden.?era\b|\bbridge\s+pub\b|\bnew.?era\b|\bscientology\s+media\b|\bdissemination\b', nl):
        return 'Support Organization'
    if re.search(r'\bcontinental\s+liaison\b|\bclo\b', nl):
        return 'Continental Liaison Office'
    return 'Class V Org'


def query_bbox(continent, bbox):
    """Query OSM for Scientology orgs in a bounding box."""
    bbox_str = f"{bbox[1]},{bbox[0]},{bbox[3]},{bbox[2]}"
    query = QUERY.replace('{{bbox}}', bbox_str)
    
    data = urllib.parse.urlencode({'data': query}).encode()
    req = urllib.request.Request(OVERAPSS_URL, data=data, headers={
        'User-Agent': 'GrantWizard/1.0',
        'Content-Type': 'application/x-www-form-urlencoded',
    })
    
    with urllib.request.urlopen(req, timeout=200) as resp:
        result = json.loads(resp.read())
    
    elements = result.get('elements', [])
    records = []
    for e in elements:
        tags = e.get('tags', {})
        name = tags.get('name', '').strip()
        if not name:
            continue
        
        lat = e.get('lat')
        lon = e.get('lon')
        if lat is None:
            center = e.get('center', {})
            lat = center.get('lat')
            lon = center.get('lon')
        
        org_type = classify_type(name, tags)
        
        records.append({
            'name': name.replace('\u00a0', ' '),
            'type': org_type,
            'latitude': lat,
            'longitude': lon,
            'address': tags.get('addr:housenumber', '') + ' ' + tags.get('addr:street', ''),
            'city': tags.get('addr:city', ''),
            'state': tags.get('addr:state', ''),
            'country': tags.get('addr:country', ''),
            'website': tags.get('website', ''),
            'osm_id': f"{e['type'][0]}{e['id']}",
        })
    
    return records


def main():
    parser = argparse.ArgumentParser(description='Global Scientology scraper')
    parser.add_argument('--dry-run', action='store_true')
    parser.add_argument('--merge', action='store_true')
    args = parser.parse_args()

    all_orgs = {}
    for continent, bbox in CONTINENTS:
        print(f'\n{continent}...', end=' ', flush=True)
        try:
            records = query_bbox(continent, bbox)
            # Deduplicate by name+coords
            for r in records:
                key = f"{r['name']}|{r['latitude']:.3f}|{r['longitude']:.3f}"
                if key not in all_orgs:
                    all_orgs[key] = r
            print(f'{len(records):,} found ({len(all_orgs):,} unique so far)')
        except Exception as e:
            print(f'ERROR: {e}')
        time.sleep(3)

    orgs = list(all_orgs.values())
    print(f'\n\nTotal unique Scientology orgs found: {len(orgs):,}')

    types = {}
    for o in orgs:
        types[o['type']] = types.get(o['type'], 0) + 1
    print(f'\n{"Type":30s} {"Count":>6s}')
    print('-' * 40)
    for t, c in sorted(types.items(), key=lambda x: -x[1]):
        print(f'{t:30s} {c:>6,}')

    # Country breakdown
    countries = {}
    for o in orgs:
        c = o['country'] or 'Unknown'
        countries[c] = countries.get(c, 0) + 1
    print(f'\nBy country:')
    for c, cnt in sorted(countries.items(), key=lambda x: -x[1])[:20]:
        print(f'  {c:30s} {cnt:>4}')

    # Save
    os.makedirs(os.path.dirname(OUTPUT), exist_ok=True)
    with open(OUTPUT, 'w') as f:
        json.dump(orgs, f, indent=2)
    print(f'\nSaved to {OUTPUT}')

    if args.dry_run:
        for o in orgs[:20]:
            print(f'  {o["name"][:50]:50s} | {o["type"]:20s} | ({o["latitude"]:.3f}, {o["longitude"]:.3f})')
        return

    if args.merge and orgs:
        db = sqlite3.connect(DB_PATH, timeout=60)
        matched, inserted = 0, 0
        for o in orgs:
            # Try proximity match first (lat/lng within 0.01 deg)
            nearby = db.execute("""
                SELECT id FROM churches
                WHERE ABS(latitude - ?) < 0.01 AND ABS(longitude - ?) < 0.01
                LIMIT 1
            """, (o['latitude'], o['longitude'])).fetchone()
            
            if nearby:
                db.execute("""UPDATE churches SET
                    faith_tradition='other', family='Scientology', denomination=?,
                    website = CASE WHEN website='' OR website IS NULL THEN ? ELSE website END,
                    last_updated=datetime('now') WHERE id=?""",
                    (o['type'], o.get('website',''), nearby[0]))
                matched += 1
            else:
                db.execute("""INSERT INTO churches
                    (name, city, state, faith_tradition, family, denomination,
                     latitude, longitude, website, source, last_updated)
                    VALUES (?,?,?,'other','Scientology',?,?,?,?,'scientology_osm_scraper',datetime('now'))""",
                    (o['name'], o.get('city',''), o.get('state',''),
                     o['type'], o['latitude'], o['longitude'], o.get('website','')))
                inserted += 1
        db.commit()
        print(f'\nMerge: {matched} matched, {inserted} new records inserted')
        print(f'Total Scientology in DB: {matched + inserted + 74:,}')
        db.close()


if __name__ == '__main__':
    main()
