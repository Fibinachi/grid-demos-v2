"""Bulk import mosque datasets from multiple CKAN portals.
Resume-safe via scrape_log. Handles GeoJSON, CSV, XLSX, XLS, SHP.
"""
import sqlite3, requests, sys, os, json, tempfile, time, re, io, zipfile
from datetime import datetime, timezone
from urllib.parse import urljoin
import pandas as pd
import geopandas as gpd

DB = r"E:\grid\churches.db"
HEADERS = {"User-Agent": "GRID/1.0 (research project; contact@americanreligiousinfrastructure.org)"}
SCRIPT = "bulk_ckan_mosques"

def log(msg):
    print(f"[{datetime.now(timezone.utc).strftime('%H:%M:%S')}] {msg}", flush=True)

conn = sqlite3.connect(DB, timeout=120)
conn.execute("PRAGMA busy_timeout = 120000")
conn.execute("PRAGMA journal_mode = WAL")
c = conn.cursor()

c.execute("CREATE TABLE IF NOT EXISTS scrape_log (url TEXT PRIMARY KEY, scraped_at TEXT, status TEXT, rows_imported INTEGER)")
scraped = {r[0]: r[1] for r in c.execute("SELECT url, status FROM scrape_log WHERE status LIKE 'done%'").fetchall()}

# ── Source table for mosque imports ──
c.execute("""
    CREATE TABLE IF NOT EXISTS source_ckan_mosques (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT,
        location TEXT,
        city TEXT,
        state_region TEXT,
        country TEXT,
        lat REAL,
        lon REAL,
        source_url TEXT,
        source_dataset TEXT,
        raw_json TEXT,
        imported_at TEXT DEFAULT (datetime('now')),
        UNIQUE(name, lat, lon, source_dataset)
    )
""")
c.execute("CREATE INDEX IF NOT EXISTS idx_ckan_mosques_country ON source_ckan_mosques(country)")

# ── Parse GeoJSON features ──
def parse_geojson(data, source_name, country):
    inserted = 0
    if isinstance(data, dict):
        features = data.get('features', [data] if data.get('type') != 'FeatureCollection' else [])
    elif isinstance(data, list):
        features = data
    else:
        return 0
    
    for feat in features:
        props = feat.get('properties', {}) if isinstance(feat, dict) else {}
        geom = feat.get('geometry', {}) if isinstance(feat, dict) else {}
        
        # Extract name (try many possible field names)
        name = None
        for k in ['name', 'Name', 'NAME', 'mosque_name', 'facility_name', 'fclass', 'title', 'label']:
            if k in props:
                name = str(props[k]).strip()
                if name and name.lower() != 'none':
                    break
        
        if not name:
            continue
        
        # Location
        location = None
        for k in ['location', 'address', 'ward', 'lga', 'district', 'city', 'town', 'village']:
            if k in props and props[k]:
                location = str(props[k]).strip()
                if location.lower() != 'none':
                    break
        
        # City/state
        city = props.get('city', props.get('town', props.get('municipality')))
        state = props.get('state', props.get('state_name', props.get('region', props.get('lga'))))
        
        # Coordinates
        lat, lon = None, None
        coords = None
        if geom.get('type') == 'Point':
            coords = geom.get('coordinates', [])
        elif geom.get('type') == 'Polygon':
            # Use centroid-ish: first point
            ring = geom.get('coordinates', [[]])[0]
            if ring:
                coords = ring[0]
        
        if coords and len(coords) >= 2:
            lon, lat = coords[0], coords[1]
        else:
            # Try lat/lon in props
            lat = props.get('lat', props.get('latitude', props.get('y')))
            lon = props.get('lon', props.get('long', props.get('lng', props.get('x'))))
            try: lat = float(lat)
            except: lat = None
            try: lon = float(lon)
            except: lon = None
        
        try:
            c.execute("""
                INSERT OR IGNORE INTO source_ckan_mosques
                (name, location, city, state_region, country, lat, lon, source_url, source_dataset, raw_json)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (name[:500], str(location)[:500] if location else None,
                  str(city)[:200] if city else None, str(state)[:200] if state else None,
                  country, lat, lon, source_name, source_name, json.dumps(props, default=str)))
            if c.rowcount > 0:
                inserted += 1
        except Exception as e:
            pass
    
    return inserted

# ── Parse CSV/Excel ──
def parse_table(df, source_name, country):
    inserted = 0
    # Try to find name, location, lat, lon columns
    name_col = loc_col = lat_col = lon_col = city_col = state_col = None
    
    for col in df.columns:
        cl = str(col).lower().strip()
        if not name_col and any(w in cl for w in ('name', 'mosque', 'مسجد', 'اسم', 'facility')):
            name_col = col
        if not loc_col and any(w in cl for w in ('address', 'location', 'ward', 'lga', 'عنوان', 'موقع')):
            loc_col = col
        if not city_col and any(w in cl for w in ('city', 'town', 'municipality', 'مدينة')):
            city_col = col
        if not state_col and any(w in cl for w in ('state', 'region', 'province', 'governorate', 'محافظة', 'ولاية')):
            state_col = col
        if not lat_col and any(w in cl for w in ('lat', 'latitude', 'y', 'خط')):
            lat_col = col
        if not lon_col and any(w in cl for w in ('lon', 'long', 'lng', 'longitude', 'x', 'طول')):
            lon_col = col
    
    if not name_col:
        name_col = df.columns[0]
    if not loc_col and len(df.columns) > 1:
        loc_col = df.columns[1]
    
    for _, row in df.iterrows():
        name = str(row[name_col]).strip() if pd.notna(row[name_col]) else None
        if not name or name.lower() in ('none', 'nan', ''):
            continue
        
        lat = float(row[lat_col]) if lat_col and pd.notna(row[lat_col]) else None
        lon = float(row[lon_col]) if lon_col and pd.notna(row[lon_col]) else None
        loc = str(row[loc_col])[:500] if loc_col and pd.notna(row[loc_col]) else None
        city = str(row[city_col])[:200] if city_col and pd.notna(row[city_col]) else None
        state = str(row[state_col])[:200] if state_col and pd.notna(row[state_col]) else None
        
        try:
            c.execute("""
                INSERT OR IGNORE INTO source_ckan_mosques
                (name, location, city, state_region, country, lat, lon, source_url, source_dataset, raw_json)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (name[:500], loc, city, state, country, lat, lon, source_name, source_name,
                  json.dumps(row.to_dict(), default=str)))
            if c.rowcount > 0:
                inserted += 1
        except:
            pass
    
    return inserted

# ── Import a CKAN resource ──
def import_resource(url, name, fmt, source_name, country):
    if url in scraped:
        return 0
    
    log(f"    Downloading: {name} ({fmt})")
    try:
        r = requests.get(url, headers=HEADERS, timeout=90, allow_redirects=True)
        r.raise_for_status()
    except Exception as e:
        log(f"      Download error: {e}")
        c.execute("INSERT OR REPLACE INTO scrape_log VALUES (?,?,?,0)", (url, datetime.now(timezone.utc).isoformat(), f"error:{e}"))
        conn.commit()
        return 0
    
    fmt = fmt.upper()
    inserted = 0
    
    try:
        if fmt in ('GEOJSON', 'JSON'):
            data = r.json()
            inserted = parse_geojson(data, source_name, country)
        
        elif fmt in ('SHP', 'ZIP'):
            # Shapefile in zip
            with zipfile.ZipFile(io.BytesIO(r.content)) as zf:
                shp_files = [f for f in zf.namelist() if f.endswith('.shp')]
                if shp_files:
                    with tempfile.TemporaryDirectory() as tmpdir:
                        zf.extractall(tmpdir)
                        gdf = gpd.read_file(os.path.join(tmpdir, shp_files[0]))
                        inserted = parse_geojson(json.loads(gdf.to_json()), source_name, country)
        
        elif fmt in ('XLS', 'XLSX'):
            tmp = tempfile.NamedTemporaryFile(suffix='.xlsx', delete=False)
            tmp.write(r.content)
            tmp.close()
            df = pd.read_excel(tmp.name)
            os.unlink(tmp.name)
            inserted = parse_table(df, source_name, country)
        
        elif fmt == 'CSV':
            df = pd.read_csv(io.StringIO(r.text))
            inserted = parse_table(df, source_name, country)
        
        else:
            log(f"      Unknown format: {fmt}")
    
    except Exception as e:
        log(f"      Parse error: {e}")
    
    c.execute("INSERT OR REPLACE INTO scrape_log VALUES (?,?,?,?)",
              (url, datetime.now(timezone.utc).isoformat(), f"done:{inserted}", inserted))
    conn.commit()
    return inserted

# ── Import all resources from a CKAN package ──
def import_package(portal_url, package_id, country):
    api_url = f"{portal_url}/api/3/action/package_show?id={package_id}"
    log(f"  API: {api_url}")
    try:
        r = requests.get(api_url, headers=HEADERS, timeout=15)
        r.raise_for_status()
        pkg = r.json()['result']
    except Exception as e:
        log(f"    API error: {e}")
        return 0
    
    title = pkg.get('title', package_id)
    resources = pkg.get('resources', [])
    log(f"    {title}: {len(resources)} resources")
    
    total = 0
    for res in resources:
        url = res.get('url', '')
        name = res.get('name', 'unknown')
        fmt = (res.get('format', '') or '').upper()
        if not url:
            continue
        n = import_resource(url, name, fmt, f"{portal_url}/{package_id}", country)
        total += n
    
    return total

# ══════════════════════════════════════════════════════════════════════════
# BULK IMPORT TARGETS
# ══════════════════════════════════════════════════════════════════════════

TARGETS = [
    # Jordan — open data portal
    ("https://opendata.gov.jo", "mosques-2490-2023", "Jordan"),
    ("https://opendata.gov.jo", "mosques-2488-2023", "Jordan"),
    
    # Nigeria — openAFRICA (state-level GeoJSON)
    ("https://bulk.openafrica.net", "kano-mosques", "Nigeria"),
    ("https://bulk.openafrica.net", "imo-mosques", "Nigeria"),
    ("https://bulk.openafrica.net", "delta-mosques", "Nigeria"),
    ("https://bulk.openafrica.net", "oyo-mosques", "Nigeria"),
    ("https://bulk.openafrica.net", "sokoto-mosques", "Nigeria"),
    ("https://bulk.openafrica.net", "cameroon-mosques", "Cameroon"),
    
    # Nigeria — openAFRICA (dataset groups — try as regular datasets)
    ("https://bulk.openafrica.net", "nigerian-mosques1", "Nigeria"),
    ("https://bulk.openafrica.net", "nigerian-mosques", "Nigeria"),
    ("https://bulk.openafrica.net", "abia-mosques", "Nigeria"),
    ("https://bulk.openafrica.net", "ogun-mosques", "Nigeria"),
    ("https://bulk.openafrica.net", "enugu-mosques", "Nigeria"),
    ("https://bulk.openafrica.net", "borno-mosques", "Nigeria"),
    ("https://bulk.openafrica.net", "yobe-mosques", "Nigeria"),
]

log(f"=== Bulk importing {len(TARGETS)} datasets ===")
grand_total = 0

for portal, pkg_id, country in TARGETS:
    source_key = f"{portal}/{pkg_id}"
    if source_key in scraped:
        log(f"\nSKIP {source_key} (already done: {scraped[source_key]})")
        continue
    
    log(f"\n── {country}: {pkg_id} ──")
    
    # Also search for mosque datasets on this portal
    try:
        search_url = f"{portal}/api/3/action/package_search?q=mosques&rows=50"
        sr = requests.get(search_url, headers=HEADERS, timeout=10)
        if sr.status_code == 200:
            pkgs = sr.json()['result']['results']
            mosque_pkgs = [p for p in pkgs if 'mosque' in p.get('title','').lower() or 'mosque' in p.get('name','').lower()]
            if len(mosque_pkgs) > 1:
                log(f"  Portal has {len(mosque_pkgs)} mosque datasets total")
    except:
        pass
    
    n = import_package(portal, pkg_id, country)
    grand_total += n
    if n > 0:
        log(f"  → {n} new mosques")

# ── Summary ──
log(f"\n{'='*60}")
log(f"Bulk import complete")
log(f"  Datasets processed: {len(TARGETS)}")
log(f"  New mosques: {grand_total}")
total = c.execute("SELECT COUNT(*) FROM source_ckan_mosques").fetchone()[0]
log(f"  Total in source_ckan_mosques: {total:,}")

# ── Quick match with churches ──
log(f"\n=== Matching with churches ===")
matched = c.execute("""
    INSERT OR IGNORE INTO church_external_ids (church_id, source, id_value)
    SELECT c.id, 'ckan_mosques', sm.name || '|' || sm.country
    FROM source_ckan_mosques sm
    JOIN churches c ON c.name = sm.name AND c.country = sm.country AND c.faith = 'Islam'
""").rowcount
log(f"  Matched by name+country: {matched}")

matched2 = c.execute("""
    INSERT OR IGNORE INTO church_external_ids (church_id, source, id_value)
    SELECT c.id, 'ckan_mosques_proximity', sm.name || '|' || sm.country
    FROM source_ckan_mosques sm
    JOIN churches c ON ABS(c.latitude - sm.lat) < 0.005 AND ABS(c.longitude - sm.lon) < 0.005
    WHERE c.country = sm.country AND c.faith = 'Islam' AND sm.lat IS NOT NULL
""").rowcount
log(f"  Matched by proximity: {matched2}")

conn.commit()
conn.close()
log("\nDone!")
