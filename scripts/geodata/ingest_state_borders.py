"""
Download Natural Earth Admin 1 – States & Provinces (1:50m) and load into SQLite.
Appends to existing world_borders.db.

Usage:
    .venv\Scripts\python.exe scripts/geodata/ingest_state_borders.py
"""

import os, sys, sqlite3, tempfile, zipfile, shutil, urllib.request, time

DB_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'data', 'natural_earth', 'world_borders.db'))
DATA_DIR = os.path.join(os.path.dirname(__file__), '..', '..', 'data', 'natural_earth')
ZIP_PATH = os.path.join(DATA_DIR, 'ne_50m_admin_1_states_provinces.zip')
NE_URL = 'https://naciscdn.org/naturalearth/50m/cultural/ne_50m_admin_1_states_provinces.zip'

print("=== Natural Earth 1:50m States & Provinces ===")
os.makedirs(DATA_DIR, exist_ok=True)

# Download
if not os.path.exists(ZIP_PATH):
    print(f"  Downloading...")
    urllib.request.urlretrieve(NE_URL, ZIP_PATH)
    print(f"  Saved {os.path.getsize(ZIP_PATH)/1024:.0f} KB")
else:
    print(f"  Already downloaded: {os.path.getsize(ZIP_PATH)/1024:.0f} KB")

# Extract + load
import geopandas as gpd
from shapely import wkb

extract_dir = tempfile.mkdtemp(prefix='ne_states_')
try:
    with zipfile.ZipFile(ZIP_PATH) as zf:
        zf.extractall(extract_dir)

    shp = None
    for root, _, files in os.walk(extract_dir):
        for f in files:
            if f.endswith('.shp'):
                shp = os.path.join(root, f); break
        if shp: break

    gdf = gpd.read_file(shp)
    print(f"  Loaded {len(gdf):,} states/provinces")

    # Select key columns
    col_map = {
        'name': 'name', 'name_en': 'name_en', 'iso_a2': 'iso_a2',
        'iso_3166_2': 'iso_3166_2', 'admin': 'country_name',
        'woe_name': 'woe_name', 'type_en': 'type_en',
        'region': 'region', 'subregion': 'subregion',
        'postal': 'postal', 'abbrev': 'abbrev',
        'latitude': 'lat', 'longitude': 'lon',
        'geometry': 'geometry',
    }
    keep = {k: v for k, v in col_map.items() if k in gdf.columns}
    gdf = gdf[list(keep)].rename(columns=keep)

    # Write to SQLite
    conn = sqlite3.connect(DB_PATH, timeout=30)
    conn.execute("PRAGMA journal_mode=WAL")
    c = conn.cursor()

    c.execute("DROP TABLE IF EXISTS state_borders")
    c.execute("""
        CREATE TABLE state_borders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            name_en TEXT,
            iso_a2 TEXT,
            iso_3166_2 TEXT,
            country_name TEXT,
            type_en TEXT,
            region TEXT,
            subregion TEXT,
            postal TEXT,
            abbrev TEXT,
            lat REAL,
            lon REAL,
            geometry_wkb BLOB,
            geometry_type TEXT DEFAULT 'MULTIPOLYGON',
            source TEXT DEFAULT 'natural_earth_50m',
            created_at TEXT DEFAULT (datetime('now'))
        )
    """)
    c.execute("CREATE INDEX IF NOT EXISTS idx_sb_iso_a2 ON state_borders(iso_a2)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_sb_country ON state_borders(country_name)")

    rows = 0
    for _, row in gdf.iterrows():
        c.execute("""INSERT INTO state_borders
            (name, name_en, iso_a2, iso_3166_2, country_name, type_en,
             region, subregion, postal, abbrev, lat, lon, geometry_wkb)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""", (
            str(row.get('name', '')) if row.get('name') is not None else '',
            str(row.get('name_en', '')) if row.get('name_en') is not None else '',
            str(row.get('iso_a2', '')) if row.get('iso_a2') is not None else '',
            str(row.get('iso_3166_2', '')) if row.get('iso_3166_2') is not None else '',
            str(row.get('country_name', '')) if row.get('country_name') is not None else '',
            str(row.get('type_en', '')) if row.get('type_en') is not None else '',
            str(row.get('region', '')) if row.get('region') is not None else '',
            str(row.get('subregion', '')) if row.get('subregion') is not None else '',
            str(row.get('postal', '')) if row.get('postal') is not None else '',
            str(row.get('abbrev', '')) if row.get('abbrev') is not None else '',
            float(row['lat']) if row.get('lat') is not None else None,
            float(row['lon']) if row.get('lon') is not None else None,
            wkb.dumps(row['geometry']),
        ))
        rows += 1

    conn.commit()

    c.execute("SELECT COUNT(*) FROM state_borders"); total = c.fetchone()[0]
    c.execute("SELECT COUNT(DISTINCT iso_a2) FROM state_borders"); countries = c.fetchone()[0]
    c.execute("SELECT SUM(LENGTH(geometry_wkb)) FROM state_borders"); bytes = c.fetchone()[0] or 0

    print(f"  Inserted {total} state borders across {countries} countries")
    print(f"  Geometry: {bytes/1024/1024:.1f} MB WKB")

    # Top countries
    c.execute("SELECT country_name, COUNT(*) n FROM state_borders GROUP BY country_name ORDER BY n DESC LIMIT 10")
    print("  Top countries:")
    for r in c.fetchall():
        print(f"    {r[0] or '?':30s} {r[1]:4d}")

    # US states
    c.execute("SELECT name, postal, iso_3166_2 FROM state_borders WHERE iso_a2='US' ORDER BY name LIMIT 10")
    print("  US sample:")
    for r in c.fetchall():
        print(f"    {r[0][:30]:30s} {r[1] or '':5s} {r[2] or ''}")

    conn.close()
    print("\nDone! state_borders table ready in world_borders.db")

finally:
    shutil.rmtree(extract_dir, ignore_errors=True)
