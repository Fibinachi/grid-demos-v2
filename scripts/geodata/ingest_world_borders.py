"""
Download Natural Earth Admin 0 – Countries (1:50m) and load into SQLite
as a world_borders table with WKB geometry.

Natural Earth 1:50m is the standard free global borders dataset.
~241 countries, ~5 MB zipped. Good detail-to-size ratio for maps.

Usage:
    .venv\Scripts\python.exe scripts\geodata\ingest_world_borders.py

Output:
    File `data/natural_earth/world_borders.db` with table `world_borders`:
    - id           INTEGER PRIMARY KEY
    - name         TEXT     (country name, e.g. "France")
    - iso_a3       TEXT     (ISO 3166-1 alpha-3, e.g. "FRA")
    - iso_a2       TEXT     (ISO 3166-1 alpha-2, e.g. "FR")
    - continent    TEXT     (continent name)
    - region_un    TEXT     (UN sub-region)
    - subregion    TEXT     (UN sub-region)
    - pop_est      REAL     (population estimate)
    - gdp_md_est   REAL     (GDP in millions USD)
    - economy      TEXT     (income group)
    - geometry_wkb BLOB     (MULTIPOLYGON as Well-Known Binary)
"""

import os, sys, sqlite3, urllib.request, zipfile, tempfile, shutil

# ── Config ──
# Separate DB to avoid lock contention with main churches.db (620MB, often in use)
DB_PATH = os.path.join(os.path.dirname(__file__), '..', '..', 'data', 'natural_earth', 'world_borders.db')
DB_PATH = os.path.abspath(DB_PATH)

NE_URL = (
    'https://www.naturalearthdata.com/http//www.naturalearthdata.com/'
    'download/50m/cultural/ne_50m_admin_0_countries.zip'
)
DATA_DIR = os.path.join(os.path.dirname(__file__), '..', '..', 'data', 'natural_earth')
ZIP_PATH = os.path.join(DATA_DIR, 'ne_50m_admin_0_countries.zip')

# ── Step 1: Download ──
print("=== Step 1: Download Natural Earth 1:50m Countries ===")
os.makedirs(DATA_DIR, exist_ok=True)

if not os.path.exists(ZIP_PATH):
    print(f"  Downloading from naturalearthdata.com...")
    def report(block_num, block_size, total_size):
        if block_num % 20 == 0 and total_size > 0:
            pct = block_num * block_size / total_size * 100
            print(f"    {pct:.0f}% ({block_num * block_size / 1024 / 1024:.1f} MB)", flush=True)
    try:
        urllib.request.urlretrieve(NE_URL, ZIP_PATH, report)
    except Exception as e:
        print(f"  Download failed: {e}")
        print(f"  Trying direct URL...")
        # Fallback: Natural Earth sometimes redirects
        NE_URL_ALT = (
            'https://naciscdn.org/naturalearth/50m/cultural/'
            'ne_50m_admin_0_countries.zip'
        )
        urllib.request.urlretrieve(NE_URL_ALT, ZIP_PATH, report)
    print(f"  Saved to {ZIP_PATH}")
else:
    size_mb = os.path.getsize(ZIP_PATH) / 1024 / 1024
    print(f"  Already downloaded: {size_mb:.1f} MB")

# ── Step 2: Extract and load with geopandas ──
print("\n=== Step 2: Load into GeoDataFrame ===")
import geopandas as gpd

extract_dir = tempfile.mkdtemp(prefix='ne_borders_')
try:
    with zipfile.ZipFile(ZIP_PATH, 'r') as zf:
        zf.extractall(extract_dir)

    # Find the .shp file
    shp_path = None
    for root, _, files in os.walk(extract_dir):
        for f in files:
            if f.endswith('.shp'):
                shp_path = os.path.join(root, f)
                break
        if shp_path:
            break

    if not shp_path:
        print("  ERROR: No .shp file found in archive!")
        sys.exit(1)

    print(f"  Reading {shp_path}")
    gdf = gpd.read_file(shp_path)
    print(f"  Loaded {len(gdf):,} countries, {len(gdf.columns)} columns")
    print(f"  CRS: {gdf.crs}")

    # ── Step 3: Select and normalize columns ──
    print("\n=== Step 3: Normalize columns ===")

    # Map Natural Earth columns to our schema
    col_map = {
        'NAME': 'name',
        'SOVEREIGNT': 'sovereign',
        'ISO_A3': 'iso_a3',
        'ISO_A2': 'iso_a2',
        'CONTINENT': 'continent',
        'REGION_UN': 'region_un',
        'SUBREGION': 'subregion',
        'POP_EST': 'pop_est',
        'GDP_MD_EST': 'gdp_md_est',
        'ECONOMY': 'economy',
        'geometry': 'geometry',
    }

    # Keep only columns that exist in the shapefile
    keep_cols = {}
    for src, dst in col_map.items():
        if src in gdf.columns:
            keep_cols[src] = dst
        elif dst != 'geometry':
            print(f"  ⚠ Column '{src}' not found in shapefile, skipping")

    gdf = gdf[list(keep_cols.keys())].rename(columns=keep_cols)

    # Drop Antarctica (not useful for church mapping, and skews map extent)
    gdf = gdf[gdf['name'] != 'Antarctica'].copy()

    # Drop -99 placeholder values
    for col in ['pop_est', 'gdp_md_est']:
        if col in gdf.columns:
            gdf.loc[gdf[col] < 0, col] = None

    print(f"  {len(gdf)} countries after dropping Antarctica")
    print(f"  Columns: {list(gdf.columns)}")

    # ── Step 4: Write to SQLite ──
    print(f"\n=== Step 4: Write to {DB_PATH} ===")

    # Convert geometry to WKB for SQLite storage
    from shapely import wkb

    # Use 30s timeout — other agents may hold brief locks
    conn = sqlite3.connect(DB_PATH, timeout=30)
    c = conn.cursor()

    # Enable WAL and busy timeout for resilience
    c.execute("PRAGMA journal_mode=WAL")
    c.execute("PRAGMA busy_timeout=30000")

    # Drop existing table if present
    c.execute("DROP TABLE IF EXISTS world_borders")

    # Create table
    c.execute("""
        CREATE TABLE world_borders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            sovereign TEXT,
            iso_a3 TEXT,
            iso_a2 TEXT,
            continent TEXT,
            region_un TEXT,
            subregion TEXT,
            pop_est REAL,
            gdp_md_est REAL,
            economy TEXT,
            geometry_wkb BLOB NOT NULL,
            geometry_type TEXT DEFAULT 'MULTIPOLYGON',
            source TEXT DEFAULT 'natural_earth_50m',
            created_at TEXT DEFAULT (datetime('now'))
        )
    """)

    # Create indexes
    c.execute("CREATE INDEX IF NOT EXISTS idx_wb_name ON world_borders(name)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_wb_iso_a3 ON world_borders(iso_a3)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_wb_continent ON world_borders(continent)")

    # Insert rows
    rows_written = 0
    for _, row in gdf.iterrows():
        geom_wkb = wkb.dumps(row['geometry'])
        values = (
            row.get('name'),
            row.get('sovereign'),
            row.get('iso_a3'),
            row.get('iso_a2'),
            row.get('continent'),
            row.get('region_un'),
            row.get('subregion'),
            row.get('pop_est'),
            row.get('gdp_md_est'),
            row.get('economy'),
            geom_wkb,
        )
        c.execute("""
            INSERT INTO world_borders
                (name, sovereign, iso_a3, iso_a2, continent, region_un,
                 subregion, pop_est, gdp_md_est, economy, geometry_wkb)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, values)
        rows_written += 1

    conn.commit()

    # ── Step 5: Verify ──
    print(f"\n=== Step 5: Verify ===")
    c.execute("SELECT COUNT(*) FROM world_borders")
    count = c.fetchone()[0]
    print(f"  Rows in world_borders: {count:,}")

    c.execute("SELECT name, iso_a3, continent FROM world_borders ORDER BY name LIMIT 5")
    print(f"  Sample rows:")
    for row in c.fetchall():
        print(f"    {row[0]:30s} {row[1]:5s} {row[2] or 'N/A'}")

    # Show continents
    c.execute("""
        SELECT continent, COUNT(*) as n
        FROM world_borders
        GROUP BY continent
        ORDER BY n DESC
    """)
    print(f"\n  Countries by continent:")
    for row in c.fetchall():
        print(f"    {row[0] or 'Unknown':20s} {row[1]:3d}")

    # Show total geometry size
    c.execute("SELECT SUM(LENGTH(geometry_wkb)) FROM world_borders")
    total_bytes = c.fetchone()[0]
    print(f"\n  Total geometry size: {total_bytes / 1024 / 1024:.1f} MB WKB")

    conn.close()
    print("\n✓ Done! world_borders table ready in data/natural_earth/world_borders.db")
    print("  Attach from main DB with: ATTACH 'data/natural_earth/world_borders.db' AS geo")

finally:
    # Cleanup temp extraction dir
    shutil.rmtree(extract_dir, ignore_errors=True)
