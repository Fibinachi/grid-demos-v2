"""
Import MAPS/DARMC historic Christian sites from ArcGIS REST API.
Routes to Historic Christianity taxonomy (763-767).
Uses landmark_type='historic_site' to separate from active churches.
"""
import sqlite3, time, json, urllib.request, urllib.error
from pathlib import Path
from datetime import datetime

PROJECT = Path(__file__).resolve().parent.parent.parent
DB_PATH = PROJECT / "churches.db"

BASE = "https://services1.arcgis.com/qN3V93cYGMKQCOxL/arcgis/rest/services"
CHUNK = 500
NOW = datetime.now().isoformat()

# Layer definitions: (name, feature_server_path, layer_id, taxonomy_id, tradition, era)
LAYERS = [
    # Monasteries
    ("Early Monastic Foundations", "DARMC_Medieval_World/FeatureServer/42", 765,
     "Early Monastic", "ca. 300-995 CE"),
    ("Celtic & Anglo-Saxon Monasteries", "DARMC_Medieval_World/FeatureServer/43", 765,
     "Celtic/Anglo-Saxon Monastic", "Early Medieval"),
    ("Cluniac Monasteries", "DARMC_Medieval_World/FeatureServer/45", 765,
     "Cluniac", "ca. 998-1109 CE"),
    ("Cistercian Monasteries", "DARMC_Medieval_World/FeatureServer/44", 765,
     "Cistercian", "ca. 1098-1487 CE"),
    ("Praemonstratensian Monasteries", "DARMC_Medieval_World/FeatureServer/46", 765,
     "Praemonstratensian", "ca. 1120-1409 CE"),
    ("Dominican Houses", "DARMC_Medieval_World/FeatureServer/48", 765,
     "Dominican", "ca. 1216-1500 CE"),
    ("Franciscan Houses", "DARMC_Medieval_World/FeatureServer/49", 765,
     "Franciscan", "ca. 1300 CE"),
    ("Regular Canons", "DARMC_Medieval_World/FeatureServer/61", 765,
     "Augustinian Canons", "ca. 1250 CE"),
    
    # Bishoprics
    ("Bishoprics ca. 600 CE", "DARMC_Medieval_World/FeatureServer/52", 764,
     "Early Medieval Bishopric", "ca. 600 CE"),
    ("Bishoprics ca. 900 CE", "DARMC_Medieval_World/FeatureServer/53", 764,
     "Medieval Bishopric", "ca. 900 CE"),
    ("Bishoprics ca. 1000 CE", "DARMC_Medieval_World/FeatureServer/54", 764,
     "Medieval Bishopric", "ca. 1000 CE"),
    ("Bishoprics ca. 1200 CE", "DARMC_Medieval_World/FeatureServer/55", 764,
     "Medieval Bishopric", "ca. 1200 CE"),
    ("Bishoprics ca. 1450 CE", "DARMC_Medieval_World/FeatureServer/56", 764,
     "Late Medieval Bishopric", "ca. 1450 CE"),
    
    # Holy Land
    ("Holy Land Christian Sites ca. 808", "DARMC_Medieval_World/FeatureServer/65", 767,
     "Holy Land Christian", "ca. 808 CE"),
    ("Jerusalem Main Shrines ca. 808", "DARMC_Medieval_World/FeatureServer/68", 767,
     "Jerusalem Shrine", "ca. 808 CE"),
    
    # Missions
    ("Great Moravia Sites", "DARMC_Medieval_World/FeatureServer/20", 764,
     "Great Moravian", "ca. 800-899 CE"),
    ("Slavic Mission Sites", "DARMC_Medieval_World/FeatureServer/23", 764,
     "Slavic Mission", "ca. 800-1200 CE"),
    
    # Roman temples (archaeological) - corrected to layer 26
    ("Roman Temples", "DARMC_Roman_World/FeatureServer/26", 618,
     "Roman Religion", "pre 550 BCE-640 CE"),
    
    # Major towns with bishopric flags (have POINT_X/POINT_Y)
    ("Major Towns ca. 814", "DARMC_Medieval_World/FeatureServer/4", 764,
     "Early Medieval Town", "ca. 814 CE"),
    ("Major Towns ca. 1000", "DARMC_Medieval_World/FeatureServer/7", 764,
     "Medieval Town", "ca. 1000 CE"),
    ("Major Towns ca. 1200", "DARMC_Medieval_World/FeatureServer/10", 764,
     "Medieval Town", "ca. 1200 CE"),
    ("Major Towns ca. 1450", "DARMC_Medieval_World/FeatureServer/13", 764,
     "Late Medieval Town", "ca. 1450 CE"),
]

def progress_bar(i, total, start, label=""):
    if total == 0: return
    elapsed = max(time.time() - start, 0.001)
    rate = (i+1)/elapsed
    eta = (total-i-1)/rate/60 if rate>0 else 0
    pct = (i+1)/total*100
    f = int(30*(i+1)/total)
    print(f"\r    {'█'*f}{'░'*(30-f)} {i+1:,}/{total:,} ({pct:.0f}%) {rate:.0f}/s ETA={eta:.0f}m {label}", end="", flush=True)


def fetch_layer(url, max_retries=3):
    """Fetch all features from an ArcGIS FeatureServer layer (paginated)."""
    features = []
    offset = 0
    page_size = 1000
    
    while True:
        query_url = f"{BASE}/{url}/query?where=1%3D1&outFields=*&returnGeometry=false&resultOffset={offset}&resultRecordCount={page_size}&f=json"
        
        for attempt in range(max_retries):
            try:
                req = urllib.request.Request(query_url)
                with urllib.request.urlopen(req, timeout=30) as resp:
                    data = json.loads(resp.read())
                break
            except Exception as e:
                if attempt == max_retries - 1:
                    print(f"\n  ERROR fetching {url}: {e}")
                    return features
                time.sleep(2 ** attempt)
        
        if 'features' not in data:
            print(f"\n  No features in response: {data.get('error', 'unknown')}")
            break
        
        batch = data['features']
        features.extend(batch)
        offset += len(batch)
        
        if len(batch) < page_size or offset >= 50000:  # safety cap
            break
    
    return features


def extract_name(attrs):
    """Extract best name from attribute dictionary."""
    for key in ['NAME', 'Display_Name', 'Name', 'CITYNAME', 'DISP_NAME', 'NAME1', 'Old_Name']:
        val = attrs.get(key)
        if val and str(val).strip() and str(val).strip() != ' ':
            return str(val).strip()
    return None


def extract_coords(attrs):
    """Extract lat/lon from various field name conventions."""
    for lat_key, lon_key in [
        ('POINT_Y', 'POINT_X'), ('Latitude', 'Longitude'), ('Lat', 'Long'),
        ('Lat', 'Long_'), ('DECLAT', 'DECLONG'), ('LATITUDE', 'LONGITUDE'),
        ('DEC_LAT', 'DEC_LONG'), ('lat', 'lon'), ('LAT', 'LONG'),
    ]:
        lat = attrs.get(lat_key)
        lon = attrs.get(lon_key)
        if lat and lon:
            try:
                return float(lat), float(lon)
            except (ValueError, TypeError):
                continue
    return None, None


def extract_country(attrs):
    """Extract modern country."""
    for key in ['NAT', 'CNTRYNAME', 'COUNTRY', 'Country_Mo', 'country']:
        val = attrs.get(key)
        if val and str(val).strip():
            return str(val).strip()[:3]
    return None


print("=== MAPS/DARMC HISTORIC CHRISTIAN IMPORT ===\n")

db = sqlite3.connect(str(DB_PATH), timeout=120, isolation_level=None)
db.row_factory = sqlite3.Row
db.execute("PRAGMA journal_mode=MEMORY")
db.execute("PRAGMA synchronous=OFF")
db.execute("PRAGMA busy_timeout=60000")
db.execute("PRAGMA cache_size=-500000")  # 500MB cache

# Get next church ID
next_id = db.execute("SELECT MAX(id) FROM churches").fetchone()[0] + 1
print(f"Next church ID: {next_id:,}\n")

total_imported = 0
by_layer = {}

for label, url, tax_id, tradition, era in LAYERS:
    print(f"\n--- {label} ---")
    print(f"  Fetching from {BASE}/{url}...")
    
    features = fetch_layer(url)
    print(f"  {len(features):,} features received")
    
    if not features:
        continue
    
    layer_count = 0
    skipped_no_name = 0
    skipped_no_coords = 0
    skipped_duplicate = 0
    
    # Get existing names for dedup
    existing_names = set()
    
    for i in range(0, len(features), CHUNK):
        batch = features[i:i+CHUNK]
        inserts = []
        
        for feat in batch:
            attrs = feat.get('attributes', {})
            
            name = extract_name(attrs)
            if not name:
                skipped_no_name += 1
                continue
            
            lat, lon = extract_coords(attrs)
            if lat is None or not (-90 <= lat <= 90 and -180 <= lon <= 180):
                skipped_no_coords += 1
                continue
            
            country = extract_country(attrs)
            
            # Determine landmark_type based on tax_id
            if tax_id == 765:
                ltype = 'historic_monastery'
            elif tax_id == 767:
                ltype = 'historic_shrine'
            elif tax_id == 618:
                ltype = 'archaeological_site'
            else:
                ltype = 'historic_site'
            
            inserts.append((next_id, name, ltype, country, lat, lon, tax_id, tradition, era))
            next_id += 1
        
        # Dedup check and insert
        valid_inserts = []
        for ins in inserts:
            if ins[1] not in existing_names:
                existing_names.add(ins[1])
                valid_inserts.append(ins)
            else:
                skipped_duplicate += 1
        
        if valid_inserts:
            db.executemany("""INSERT OR IGNORE INTO churches 
                (id, name, landmark_type, country, latitude, longitude, 
                 taxonomy_id, tradition, faith, source, last_updated)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'Christian', 'maps_darmc_import', ?)""",
                [(ins[0], ins[1], ins[2], ins[3], ins[4], ins[5], ins[6], ins[7], NOW) 
                 for ins in valid_inserts])

    by_layer[label] = layer_count
    total_imported += layer_count

# Summary
print(f"\n{'='*60}")
print(f"TOTAL IMPORTED: {total_imported:,}")
print(f"{'='*60}")
for label, count in sorted(by_layer.items(), key=lambda x: -x[1]):
    print(f"  {count:>6,}  {label}")

# Show taxonomy distribution
print(f"\n--- Taxonomy Distribution ---")
for r in db.execute("""
    SELECT t.id, t.name, COUNT(*) n 
    FROM churches c JOIN taxonomy t ON c.taxonomy_id=t.id
    WHERE c.source='maps_darmc_import'
    GROUP BY t.id ORDER BY n DESC
""").fetchall():
    print(f"  {r['n']:>6,}  id={r['id']:>4}  {r['name']}")

db.close()
print("\nDone.")
