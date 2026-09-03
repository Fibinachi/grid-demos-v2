"""
Download INEGI Marco Geoestadístico 2020, convert to WKT, upload to BigQuery.
This creates mx_ageb_boundaries table with AGEB polygons for spatial joins.
"""
import os, sys, json, tempfile, zipfile, urllib.request, time
import geopandas as gpd

os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = ''
from google.cloud import bigquery
from google.cloud.bigquery import LoadJobConfig, SchemaField

client = bigquery.Client(project='american-rel-infra')
PROJECT = 'american-rel-infra'
DATASET = 'American_Religious_Infrastructure'

INEGI_URL = 'https://www.inegi.org.mx/contenidos/productos/prod_serv/contenidos/espanol/bvinegi/productos/geografia/marcogeo/889463807469_s.zip'
ZIP_PATH = 'E:/grid/data/inegi_mg2020.zip'
EXTRACT_DIR = 'E:/grid/data/inegi_mg2020'

# ── Step 1: Download ──
print('=== Step 1: Download INEGI Marco Geoestadístico 2020 ===')
if not os.path.exists(ZIP_PATH):
    print(f'  Downloading from INEGI...', flush=True)
    def report(block_num, block_size, total_size):
        if block_num % 100 == 0:
            pct = block_num * block_size / total_size * 100
            print(f'    {pct:.0f}% ({block_num * block_size / 1024 / 1024:.0f} MB / {total_size / 1024 / 1024:.0f} MB)', flush=True)
    urllib.request.urlretrieve(INEGI_URL, ZIP_PATH, report)
else:
    size_mb = os.path.getsize(ZIP_PATH) / 1024 / 1024
    print(f'  Already downloaded: {size_mb:.0f} MB')

# ── Step 2: Extract ──
print('\n=== Step 2: Extract shapefile ===')
if not os.path.exists(EXTRACT_DIR):
    os.makedirs(EXTRACT_DIR)
    print(f'  Extracting...', flush=True)
    with zipfile.ZipFile(ZIP_PATH, 'r') as zf:
        zf.extractall(EXTRACT_DIR)
    print(f'  Extracted to {EXTRACT_DIR}')
else:
    print(f'  Already extracted: {EXTRACT_DIR}')

# Find the AGEB .shp file
shp_files = []
for root, dirs, files in os.walk(EXTRACT_DIR):
    for f in files:
        if f.endswith('.shp'):
            shp_files.append(os.path.join(root, f))

print(f'  Found {len(shp_files)} shapefiles:')
for sf in shp_files:
    size = os.path.getsize(sf) / 1024 / 1024
    print(f'    {sf} ({size:.0f} MB)')

# Pick the AGEB file (usually contains 'ageb' or 'AGEB' in name)
# Or just take the largest one (national coverage)
ageb_shp = max(shp_files, key=os.path.getsize) if shp_files else None
if not ageb_shp:
    print('  ERROR: No shapefile found!')
    sys.exit(1)
print(f'\n  Using: {os.path.basename(ageb_shp)}')

# ── Step 3: Convert to WKT ──
print('\n=== Step 3: Read shapefile and convert to WKT ===')
print(f'  Reading with geopandas...', flush=True)
gdf = gpd.read_file(ageb_shp)
print(f'  Loaded {len(gdf):,} rows, {len(gdf.columns)} columns')
print(f'  Columns: {list(gdf.columns)[:15]}')

# Convert CRS to WGS84 (EPSG:4326) if needed
if gdf.crs and gdf.crs.to_epsg() != 4326:
    print(f'  Converting from {gdf.crs} to EPSG:4326...', flush=True)
    gdf = gdf.to_crs(epsg=4326)

# Simplify geometry for upload (reduce polygon complexity)
print(f'  Simplifying geometries...', flush=True)
gdf['geometry'] = gdf['geometry'].simplify(tolerance=0.0001, preserve_topology=True)

# Convert to WKT
print(f'  Converting to WKT...', flush=True)
gdf['geom_wkt'] = gdf['geometry'].apply(lambda g: g.wkt if g else None)

# Select key columns
key_cols = [c for c in gdf.columns if c not in ('geometry',)]
if 'geom_wkt' not in key_cols:
    key_cols = [c for c in key_cols if c != 'geom_wkt']
key_cols = key_cols[:20]  # Max 20 columns to keep upload manageable
key_cols.append('geom_wkt')

gdf_export = gdf[key_cols]

# ── Step 4: Upload to BigQuery ──
print('\n=== Step 4: Upload to BigQuery ===')
table_ref = f'{PROJECT}.{DATASET}.mx_ageb_boundaries'

# Write to temp NDJSON
tmp = tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False, encoding='utf-8')
written = 0
for _, row in gdf_export.iterrows():
    rec = {c: str(row[c]) if row[c] is not None else None for c in key_cols if c != 'geom_wkt'}
    rec['geom_wkt'] = row['geom_wkt']
    tmp.write(json.dumps(rec, ensure_ascii=False) + '\n')
    written += 1
    if written % 50000 == 0:
        print(f'  Written {written:,} rows...', flush=True)
tmp.close()
print(f'  Wrote {written:,} rows to temp file')

# Build schema from the first row
sample = gdf_export.iloc[0]
schema = []
for c in key_cols:
    field_type = 'STRING'
    if c == 'geom_wkt':
        field_type = 'STRING'  # Store as STRING, use ST_GEOGFROMTEXT() in queries
    schema.append(SchemaField(c[:128], field_type))  # BQ limits to 128 chars

client.delete_table(table_ref, not_found_ok=True)

config = LoadJobConfig(
    schema=schema,
    source_format='NEWLINE_DELIMITED_JSON',
    write_disposition='WRITE_TRUNCATE',
    max_bad_records=1000,
)

print(f'  Uploading {written:,} rows to {table_ref}...', flush=True)
with open(tmp.name, 'rb') as f:
    job = client.load_table_from_file(f, table_ref, job_config=config)
job.result()
os.unlink(tmp.name)

# Verify
t = client.get_table(table_ref)
print(f'\n  Done! Table: {table_ref}')
print(f'  Rows: {t.num_rows:,}')
print(f'  Size: {t.num_bytes / 1024 / 1024:.0f} MB')

# Test query
print('\n=== Test: Spatial join with MX churches ===')
sql_test = f'''
SELECT COUNT(*) as cnt
FROM `{PROJECT}.{DATASET}._mx_admin_staging` s
JOIN `{table_ref}` a
  ON ST_WITHIN(ST_GEOGPOINT(s.longitude, s.latitude), ST_GEOGFROMTEXT(a.geom_wkt))
LIMIT 1
'''
try:
    for r in client.query(sql_test).result():
        print(f'  Test join matched: {r.cnt:,}')
except Exception as e:
    print(f'  Test join error: {str(e)[:150]}')

print('\nDone!')
