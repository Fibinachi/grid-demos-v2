"""
Import Canadian National Historic Sites from Wikidata SPARQL.
Creates nhl_ca_sites reference table and links to churches via spatial join.
"""
import requests, json, sqlite3, math, time

DB = r'e:\grid\churches.db'

# SPARQL: All Canadian NHS with coordinates
# Property P1435 (heritage designation) = Q1568567 (National Historic Site of Canada)
SPARQL_URL = "https://query.wikidata.org/sparql"

# Get all NHS with coordinates
query = """
SELECT ?item ?itemLabel ?lat ?lon ?location ?locationLabel WHERE {
  ?item wdt:P1435 wd:Q1568567.   # heritage designation = National Historic Site of Canada
  ?item wdt:P625 ?coord.          # coordinate location
  BIND(geof:latitude(?coord) AS ?lat)
  BIND(geof:longitude(?coord) AS ?lon)
  OPTIONAL { ?item wdt:P131 ?location. }  # located in administrative entity
  SERVICE wikibase:label { bd:serviceParam wikibase:language "en". }
}
"""

print("Querying Wikidata for Canadian NHS...")
r = requests.get(SPARQL_URL, params={'format': 'json', 'query': query}, 
                 headers={'User-Agent': 'GRID/1.0 (charlesaprescottjr@gmail.com)'},
                 timeout=60)

if r.status_code != 200:
    print(f"HTTP {r.status_code}: {r.text[:500]}")
    exit(1)

data = r.json()
bindings = data.get('results', {}).get('bindings', [])
print(f"Found {len(bindings)} NHS sites with coordinates")

if not bindings:
    print("No results. Trying alternate property...")
    exit(1)

# Parse results
sites = []
for b in bindings:
    name = b.get('itemLabel', {}).get('value', 'Unknown')
    item_url = b.get('item', {}).get('value', '')
    qid = item_url.split('/')[-1] if item_url else ''
    lat = float(b.get('lat', {}).get('value', 0))
    lon = float(b.get('lon', {}).get('value', 0))
    location = b.get('locationLabel', {}).get('value', '')
    sites.append({
        'qid': qid,
        'name': name,
        'latitude': lat,
        'longitude': lon,
        'location': location
    })

print(f"Parsed {len(sites)} sites")

# Create reference table
db = sqlite3.connect(DB)
db.execute("DROP TABLE IF EXISTS nhl_ca_sites")
db.execute("""
    CREATE TABLE nhl_ca_sites (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        wikidata_qid TEXT UNIQUE,
        name TEXT NOT NULL,
        designation TEXT DEFAULT 'National Historic Site of Canada',
        latitude REAL,
        longitude REAL,
        location_admin TEXT,
        source TEXT DEFAULT 'wikidata_sparql',
        created_at TEXT DEFAULT (datetime('now'))
    )
""")

CHUNK = 100
for i in range(0, len(sites), CHUNK):
    batch = sites[i:i+CHUNK]
    rows = [(s['qid'], s['name'], s['latitude'], s['longitude'], s['location']) 
            for s in batch]
    db.executemany(
        "INSERT OR IGNORE INTO nhl_ca_sites (wikidata_qid, name, latitude, longitude, location_admin) VALUES (?,?,?,?,?)",
        rows
    )

db.commit()

inserted = db.execute("SELECT COUNT(*) FROM nhl_ca_sites").fetchone()[0]
print(f"Inserted {inserted} NHS sites")

# Show sample
print("\nSample NHS sites:")
for r in db.execute("SELECT name, location_admin, latitude, longitude FROM nhl_ca_sites LIMIT 15").fetchall():
    print(f"  {r[0][:60]} | {r[1]} | ({r[2]:.4f}, {r[3]:.4f})")

# Now match to GRID churches via spatial join (within 500m)
print("\nMatching NHS sites to GRID churches (500m radius)...")
db.execute("DROP TABLE IF EXISTS church_nhl_ca")

# Create bridge table
db.execute("""
    CREATE TABLE church_nhl_ca (
        church_id INTEGER,
        nhl_id INTEGER,
        distance_m REAL,
        PRIMARY KEY (church_id, nhl_id),
        FOREIGN KEY (church_id) REFERENCES churches(id),
        FOREIGN KEY (nhl_id) REFERENCES nhl_ca_sites(id)
    )
""")

# Spatial join using haversine approximation (fast enough for small datasets)
# For 1,000 NHS sites x 94K CA churches, this would be 94M comparisons - too many
# Instead: pre-filter by rough lat/lon bounding box

# Get all CA churches with GPS
churches = db.execute("""
    SELECT id, latitude, longitude FROM churches 
    WHERE country='CA' AND latitude IS NOT NULL AND latitude != 0
""").fetchall()

print(f"  CA churches with GPS: {len(churches):,}")

nhl_sites = db.execute("SELECT id, latitude, longitude FROM nhl_ca_sites").fetchall()

def haversine_km(lat1, lon1, lat2, lon2):
    R = 6371
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat/2)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon/2)**2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))

matches = []
MATCH_RADIUS_KM = 0.5  # 500m

# Build spatial index: round lat/lon to 0.1 degree buckets (~11km)
# Much faster than full pairwise comparison
from collections import defaultdict

nhl_buckets = defaultdict(list)
for nhl_id, nlat, nlon in nhl_sites:
    bucket = (round(nlat, 1), round(nlon, 1))
    nhl_buckets[bucket].append((nhl_id, nlat, nlon))

pbar_every = max(1, len(churches) // 20)
matched = 0
for i, (ch_id, clat, clon) in enumerate(churches):
    if i % pbar_every == 0:
        print(f"    Progress: {i:,}/{len(churches):,} ({100*i/len(churches):.0f}%) — {matched:,} matched")
    
    bucket = (round(clat, 1), round(clon, 1))
    # Check this bucket + neighbors
    for dlat in (-0.1, 0, 0.1):
        for dlon in (-0.1, 0, 0.1):
            nb = (bucket[0] + dlat, bucket[1] + dlon)
            for nhl_id, nlat, nlon in nhl_buckets.get(nb, []):
                dist = haversine_km(clat, clon, nlat, nlon)
                if dist <= MATCH_RADIUS_KM:
                    matches.append((ch_id, nhl_id, round(dist * 1000)))
                    matched += 1
                    break  # one NHS per church
            if matches and matches[-1][0] == ch_id:
                break
        if matches and matches[-1][0] == ch_id:
            break

print(f"  Total matches: {len(matches):,}")

# Batch insert
CHUNK = 500
for i in range(0, len(matches), CHUNK):
    batch = matches[i:i+CHUNK]
    db.executemany("INSERT OR IGNORE INTO church_nhl_ca VALUES (?,?,?)", batch)

db.commit()

matched_churches = db.execute("SELECT COUNT(DISTINCT church_id) FROM church_nhl_ca").fetchone()[0]
print(f"  Matched churches: {matched_churches:,}")

# Show examples
print("\nExample matches:")
for r in db.execute("""
    SELECT c.id, c.name, n.name, nch.distance_m
    FROM church_nhl_ca nch
    JOIN churches c ON c.id = nch.church_id
    JOIN nhl_ca_sites n ON n.id = nch.nhl_id
    LIMIT 15
""").fetchall():
    print(f"  Church #{r[0]} '{r[1][:50]}' -> NHS: '{r[2][:60]}' ({r[3]:.0f}m)")

# Update catalog
db.execute("""
    INSERT OR REPLACE INTO church_census_catalog 
    (country, table_name, category, geo_unit, description, variable_count, row_count, source_date, refresh_date)
    VALUES ('CA', 'nhl_ca_sites', 'heritage', 'point',
            'National Historic Sites of Canada from Wikidata, matched to churches within 500m',
            ?, ?, '2026-07', datetime('now'))
""", (len(nhl_sites), matched_churches))

db.commit()
db.close()

print("\nDone. Created nhl_ca_sites + church_nhl_ca tables.")
