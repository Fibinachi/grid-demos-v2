"""
Download Catholic Diocese Boundaries from OpenStreetMap via Overpass API.
Stores as GeoJSON + loads into SQLite with WKB geometry.

OSM tags:
  boundary=religious_administration
  denomination=roman_catholic
  religion=christian
  name=Diocese of X
  diocese=* (the canonical diocese name)

Usage:
    .venv\Scripts\python.exe scripts/geodata/ingest_diocese_boundaries.py
    .venv\Scripts\python.exe scripts/geodata/ingest_diocese_boundaries.py --country US  # specific country

Output:
    data/diocese_boundaries.geojson     — full GeoJSON
    data/natural_earth/world_borders.db — table diocese_boundaries (appended)
"""

import json, os, sys, sqlite3, time
import requests

# ── Config ──
OVERPASS_URL = 'https://overpass.osm.ch/api/interpreter'
DATA_DIR = os.path.join(os.path.dirname(__file__), '..', '..', 'data')
GEOJSON_PATH = os.path.join(DATA_DIR, 'diocese_boundaries.geojson')
DB_PATH = os.path.join(DATA_DIR, 'natural_earth', 'world_borders.db')
DB_PATH = os.path.abspath(DB_PATH)

UA = 'GRID/2.0 (Global Religious Infrastructure Database; academic research)'

# ── Step 1: Query Overpass API ──
def query_overpass(query, timeout=300):
    """Query Overpass API and return parsed JSON."""
    print(f'  Querying Overpass API ({len(query)} bytes)...', flush=True)
    start = time.time()
    resp = requests.post(OVERPASS_URL, data={'data': query},
                         headers={'User-Agent': UA, 'Accept': 'application/json'},
                         timeout=timeout)
    resp.raise_for_status()
    result = resp.json()
    elapsed = time.time() - start
    print(f'  Done in {elapsed:.0f}s — {len(result.get("elements", []))} elements')
    return result


def build_query():
    """Build Overpass QL query for Catholic hierarchy boundaries.
    Captures all admin levels: 6=diocese, 7=deanery, 8=sub-deanery, 10=parish."""
    return ('[out:json][timeout:300][maxsize:1073741824];'
            '('
            'relation["boundary"="religious_administration"]["denomination"="roman_catholic"];'
            'relation["boundary"="religious_administration"]["religion"="christian"]["denomination"];'
            ');'
            'out geom;')


# ── Step 2: Convert to GeoJSON ──
def osm_to_geojson(elements):
    """Convert OSM elements (relations with geometry) to GeoJSON FeatureCollection."""
    features = []
    nodes = {}

    # First pass: collect node coordinates
    for el in elements:
        if el['type'] == 'node':
            nodes[el['id']] = [el['lon'], el['lat']]

    # Second pass: convert relations to GeoJSON features using members' geometry
    for el in elements:
        if el['type'] != 'relation':
            continue

        tags = el.get('tags', {})
        name = tags.get('name', tags.get('diocese', tags.get('description', 'Unknown Diocese')))

        members = el.get('members', [])
        outer_rings = []
        inner_rings = []
        current_coords = []

        for member in members:
            geom = member.get('geometry')
            if not geom or member.get('type') != 'way':
                continue
            # Filter out null coordinates
            coords = [[p['lon'], p['lat']] for p in geom if p and p.get('lon') is not None and p.get('lat') is not None]
            if len(coords) < 3:
                continue
            role = member.get('role', 'outer')
            if role == 'inner':
                inner_rings.append(coords)
            else:
                outer_rings.append(coords)

        if not outer_rings:
            continue

        # Build polygon(s) from outer rings with optional inner rings
        if len(outer_rings) == 1:
            geom_type = 'Polygon'
            coords = [outer_rings[0]]
            if inner_rings:
                coords.extend(inner_rings)
        else:
            geom_type = 'MultiPolygon'
            # Group inner rings with their containing outer ring (simple approach: all separate)
            coords = [[ring] for ring in outer_rings]
            # Attach inner rings to first outer ring (imperfect but functional)
            if inner_rings and coords:
                coords[0].extend(inner_rings)

        # Determine hierarchy level from tags
        admin_level = tags.get('admin_level', '')
        hierarchy_type = 'diocese' if admin_level == '6' else (
            'deanery' if admin_level == '7' else (
                'sub_deanery' if admin_level == '8' else (
                    'parish' if admin_level == '10' else 'unknown'
                )
            )
        )

        features.append({
            'type': 'Feature',
            'properties': {
                'osm_id': el['id'],
                'name': name,
                'admin_level': admin_level,
                'hierarchy_type': hierarchy_type,
                'diocese': tags.get('diocese', ''),      # parent diocese name
                'deanery': tags.get('deanery', ''),       # parent deanery name
                'denomination': tags.get('denomination', 'roman_catholic'),
                'religion': tags.get('religion', 'christian'),
                'country': tags.get('is_in:country', tags.get('addr:country', '')),
                'website': tags.get('website', ''),
                'wikidata': tags.get('wikidata', ''),
                'source': 'openstreetmap_overpass',
            },
            'geometry': {
                'type': geom_type,
                'coordinates': coords,
            }
        })

    return {
        'type': 'FeatureCollection',
        'features': features,
        'metadata': {
            'source': 'OpenStreetMap via Overpass API',
            'query': 'boundary=religious_administration + denomination=roman_catholic',
            'generated_at': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
        }
    }


# ── Step 3: Load into SQLite ──
def load_into_sqlite(geojson):
    """Load diocese boundaries into world_borders.db as WKB."""
    print(f'\n=== Loading {len(geojson["features"])} diocese boundaries into {DB_PATH} ===')

    from shapely.geometry import shape
    from shapely import wkb

    conn = sqlite3.connect(DB_PATH, timeout=30)
    conn.execute("PRAGMA journal_mode=WAL")
    c = conn.cursor()

    # Create table (drop old schema if exists)
    c.execute("DROP TABLE IF EXISTS diocese_boundaries")
    c.execute("""
        CREATE TABLE IF NOT EXISTS diocese_boundaries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            osm_id INTEGER,
            name TEXT,
            admin_level TEXT,
            hierarchy_type TEXT,
            diocese TEXT,
            deanery TEXT,
            country TEXT,
            website TEXT,
            wikidata TEXT,
            geometry_wkb BLOB,
            geometry_type TEXT,
            source TEXT DEFAULT 'openstreetmap_overpass',
            created_at TEXT DEFAULT (datetime('now'))
        )
    """)

    # Create indexes
    c.execute("CREATE INDEX IF NOT EXISTS idx_db_name ON diocese_boundaries(name)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_db_diocese ON diocese_boundaries(diocese)")

    inserted = 0
    for feat in geojson['features']:
        props = feat['properties']
        geom = shape(feat['geometry'])
        geom_wkb = wkb.dumps(geom)

        c.execute("""
            INSERT INTO diocese_boundaries
                (osm_id, name, admin_level, hierarchy_type, diocese, deanery,
                 country, website, wikidata, geometry_wkb, geometry_type)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            props['osm_id'],
            props['name'],
            props.get('admin_level', ''),
            props.get('hierarchy_type', ''),
            props.get('diocese', ''),
            props.get('deanery', ''),
            props.get('country', ''),
            props.get('website', ''),
            props.get('wikidata', ''),
            geom_wkb,
            geom.geom_type,
        ))
        inserted += 1

    conn.commit()

    # Stats
    c.execute("""
        SELECT hierarchy_type, COUNT(*) FROM diocese_boundaries
        GROUP BY hierarchy_type ORDER BY COUNT(*) DESC
    """)
    print('  Hierarchy breakdown:')
    for row in c.fetchall():
        print(f'    {row[0]:15s} {row[1]:5d}')

    c.execute("SELECT COUNT(DISTINCT diocese) FROM diocese_boundaries WHERE diocese != ''")
    n_dioceses = c.fetchone()[0]
    print(f'  Unique parent dioceses: {n_dioceses}')

    c.execute("SELECT SUM(LENGTH(geometry_wkb)) FROM diocese_boundaries")
    total_bytes = c.fetchone()[0] or 0

    print(f'  Inserted {inserted} hierarchy boundaries')
    print(f'  Geometry: {total_bytes / 1024 / 1024:.1f} MB WKB')

    conn.close()


# ── Main ──
def main():
    country_code = None
    if '--country' in sys.argv:
        idx = sys.argv.index('--country')
        country_code = sys.argv[idx + 1].upper()

    print('=== OSM Catholic Diocese Boundaries ===')
    if country_code:
        print(f'  Target country: {country_code}')

    # Query Overpass for diocese-level boundaries (admin_level=6)
    query = build_query()
    result = query_overpass(query)

    if not result.get('elements'):
        print('  No elements found!')
        return

    # Convert to GeoJSON
    geojson = osm_to_geojson(result['elements'])
    n_features = len(geojson['features'])
    print(f'  Converted to {n_features} GeoJSON features')

    # Save GeoJSON
    with open(GEOJSON_PATH, 'w', encoding='utf-8') as f:
        json.dump(geojson, f, ensure_ascii=False)
    size_mb = os.path.getsize(GEOJSON_PATH) / 1024 / 1024
    print(f'  Saved to {GEOJSON_PATH} ({size_mb:.1f} MB)')

    # Load into SQLite
    if geojson['features']:
        load_into_sqlite(geojson)

    print('\nDone!')


if __name__ == '__main__':
    main()
