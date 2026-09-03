#!/usr/bin/env python3
"""
LDS Meetinghouse Scraper (OpenStreetMap)
=========================================
Queries OpenStreetMap's Overpass API for LDS meetinghouses in each US state,
then matches them against existing churches in the database.

OSM tags used:
  - denomination=mormon
  - denomination=church_of_jesus_christ_of_latter_day_saints
  - name contains "Church of Jesus Christ of Latter-day Saints" or "LDS"

Usage:
    # Preview (first state only)
    python scripts/enrichment/scrape_lds_osm.py --dry-run

    # Scrape and merge all US states
    python scripts/enrichment/scrape_lds_osm.py

    # Scrape specific states
    python scripts/enrichment/scrape_lds_osm.py --states UT,ID,AZ
"""
import argparse, json, os, sqlite3, sys, time, urllib.request, urllib.parse
from datetime import datetime

PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DB_PATH = os.path.join(PROJECT_DIR, 'churches.db')

# US states with ISO codes and FIPS for OSM area queries
STATES = [
    ('AL','01','Alabama'), ('AK','02','Alaska'), ('AZ','04','Arizona'),
    ('AR','05','Arkansas'), ('CA','06','California'), ('CO','08','Colorado'),
    ('CT','09','Connecticut'), ('DE','10','Delaware'), ('DC','11','District of Columbia'),
    ('FL','12','Florida'), ('GA','13','Georgia'), ('HI','15','Hawaii'),
    ('ID','16','Idaho'), ('IL','17','Illinois'), ('IN','18','Indiana'),
    ('IA','19','Iowa'), ('KS','20','Kansas'), ('KY','21','Kentucky'),
    ('LA','22','Louisiana'), ('ME','23','Maine'), ('MD','24','Maryland'),
    ('MA','25','Massachusetts'), ('MI','26','Michigan'), ('MN','27','Minnesota'),
    ('MS','28','Mississippi'), ('MO','29','Missouri'), ('MT','30','Montana'),
    ('NE','31','Nebraska'), ('NV','32','Nevada'), ('NH','33','New Hampshire'),
    ('NJ','34','New Jersey'), ('NM','35','New Mexico'), ('NY','36','New York'),
    ('NC','37','North Carolina'), ('ND','38','North Dakota'), ('OH','39','Ohio'),
    ('OK','40','Oklahoma'), ('OR','41','Oregon'), ('PA','42','Pennsylvania'),
    ('RI','44','Rhode Island'), ('SC','45','South Carolina'), ('SD','46','South Dakota'),
    ('TN','47','Tennessee'), ('TX','48','Texas'), ('UT','49','Utah'),
    ('VT','50','Vermont'), ('VA','51','Virginia'), ('WA','53','Washington'),
    ('WV','54','West Virginia'), ('WI','55','Wisconsin'), ('WY','56','Wyoming'),
]

OVERAPSS_URL = "https://overpass-api.de/api/interpreter"

QUERY_TEMPLATE = """
[out:json][timeout:120];
area["name"="{state_name}"][admin_level=4]->.state;
(
  node["religion"="christian"]["denomination"="mormon"](area.state);
  way["religion"="christian"]["denomination"="mormon"](area.state);
  node["amenity"="place_of_worship"]["denomination"="church_of_jesus_christ_of_latter_day_saints"](area.state);
  way["amenity"="place_of_worship"]["denomination"="church_of_jesus_christ_of_latter_day_saints"](area.state);
  node["amenity"="place_of_worship"]["denomination"="lds"](area.state);
  way["amenity"="place_of_worship"]["denomination"="lds"](area.state);
  node["name"~"Church of Jesus Christ of Latter.day Saints|Latter.day Saints|LDS Meetinghouse",i](area.state);
  way["name"~"Church of Jesus Christ of Latter.day Saints|Latter.day Saints|LDS Meetinghouse",i](area.state);
);
out center meta;
"""


def query_state(state_name):
    """Query Overpass API for LDS meetinghouses in a state."""
    query = QUERY_TEMPLATE.format(state_name=state_name)
    
    data = urllib.parse.urlencode({'data': query}).encode()
    req = urllib.request.Request(OVERAPSS_URL, data=data, headers={
        'User-Agent': 'GrantWizard/1.0',
        'Content-Type': 'application/x-www-form-urlencoded',
    })
    
    with urllib.request.urlopen(req, timeout=180) as resp:
        result = json.loads(resp.read())
    
    elements = result.get('elements', [])
    
    # Extract useful info from each element
    records = []
    for e in elements:
        tags = e.get('tags', {})
        name = tags.get('name', '').strip()
        if not name:
            name = "The Church of Jesus Christ of Latter-day Saints"
        
        # Get coordinates
        lat = e.get('lat')
        lon = e.get('lon')
        if lat is None:
            center = e.get('center', {})
            lat = center.get('lat')
            lon = center.get('lon')
        
        addr = ' '.join(filter(None, [
            tags.get('addr:housenumber', ''),
            tags.get('addr:street', ''),
        ]))
        city = tags.get('addr:city', '')
        state = tags.get('addr:state', '')
        
        records.append({
            'osm_id': f"{e['type'][0]}{e['id']}",
            'name': name,
            'latitude': lat,
            'longitude': lon,
            'address': addr,
            'city': city,
            'state': state,
            'denomination': 'Church of Jesus Christ of Latter-day Saints',
        })
    
    return records


def ensure_columns(db):
    existing = {r[1] for r in db.execute('PRAGMA table_info(churches)').fetchall()}
    for col, dtype in [
        ('lds_type', 'TEXT'),
        ('lds_confidence', 'REAL'),
        ('lds_source', 'TEXT'),
        ('lds_osm_id', 'TEXT'),
    ]:
        if col not in existing:
            db.execute(f'ALTER TABLE churches ADD COLUMN {col} {dtype}')


def main():
    parser = argparse.ArgumentParser(description='LDS OSM Scraper')
    parser.add_argument('--dry-run', action='store_true', help='First state only, preview')
    parser.add_argument('--states', help='Comma-separated state abbreviations')
    parser.add_argument('--match-radius', type=float, default=0.05,
                       help='Match radius in degrees (~5km, default: 0.05)')
    args = parser.parse_args()

    if args.states:
        state_list = [s.strip().upper() for s in args.states.split(',')]
        state_filter = [s for s in STATES if s[0] in state_list]
    else:
        state_filter = STATES[:1] if args.dry_run else STATES

    print(f'Scraping {len(state_filter)} states for LDS meetinghouses...')
    
    total_found = 0
    all_records = []
    
    for abbr, fips, name in state_filter:
        print(f'\n  {abbr} ({name})...', end=' ', flush=True)
        try:
            records = query_state(name)
            print(f'{len(records):,} meetinghouses', flush=True)
            all_records.extend(records)
            total_found += len(records)
            time.sleep(2)  # Be nice to Overpass
        except Exception as e:
            print(f'ERROR: {e}')
    
    print(f'\nTotal LDS meetinghouses found: {total_found:,}')
    
    if args.dry_run:
        for r in all_records[:10]:
            print(f'  {r["name"][:50]:50s} | ({r["latitude"]:.4f}, {r["longitude"]:.4f}) | {r["city"]:18s} {r["state"]}')
        print(f'  ... {len(all_records) - 10} more')
        return
    
    # Match against DB
    db = sqlite3.connect(DB_PATH, timeout=60)
    ensure_columns(db)
    
    matched = 0
    new_lds = 0
    radius = args.match_radius
    
    print(f'\nMatching {total_found:,} OSM records against DB (radius={radius}°)...')
    
    for rec in all_records:
        lat = rec['latitude']
        lon = rec['longitude']
        if lat is None or lon is None:
            continue
        
        # Try to find matching church by proximity
        nearby = db.execute("""
            SELECT id, name FROM churches
            WHERE ABS(latitude - ?) < ? AND ABS(longitude - ?) < ?
            LIMIT 1
        """, (lat, radius, lon, radius)).fetchone()
        
        if nearby:
            # Update existing church
            db.execute("""
                UPDATE churches SET
                    lds_type = COALESCE(NULLIF(lds_type, ''), 'LDS (General)'),
                    lds_confidence = COALESCE(lds_confidence, 0.85),
                    lds_source = COALESCE(lds_source, 'osm_match'),
                    lds_osm_id = ?,
                    denomination = COALESCE(NULLIF(denomination, ''), ?),
                    last_updated = datetime('now')
                WHERE id = ?
            """, (rec['osm_id'], 'Church of Jesus Christ of Latter-day Saints', nearby[0]))
            matched += 1
        else:
            # Could insert new record, but skip for now (complex)
            new_lds += 1
    
    db.commit()
    print(f'  Matched existing: {matched:,}')
    print(f'  New (not matched): {new_lds:,}')
    
    # Report
    rs = db.execute("""
        SELECT lds_type, COUNT(*) as c, ROUND(AVG(lds_confidence), 2) as conf
        FROM churches WHERE lds_type != '' GROUP BY lds_type ORDER BY c DESC
    """).fetchall()
    print(f'\n{"Type":25s} {"Count":>6s} {"Conf":>6s}')
    print('-' * 40)
    for r in rs:
        print(f'{r[0]:25s} {r[1]:>6,} {r[2]:>6.2f}')
    
    db.close()
    print('\nDone!')


if __name__ == '__main__':
    main()
