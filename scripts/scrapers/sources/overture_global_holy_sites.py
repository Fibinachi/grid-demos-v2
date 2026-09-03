"""
Extract ALL religious places globally from Overture Maps → holy_sites table.

Uses CTAS (CREATE TABLE AS SELECT) in BigQuery to avoid materializing
2M+ rows through the Python client. Maps Overture categories to
holy_sites schema (tradition/subtradition/landmark_type).

Strategy:
  1. CTAS into BQ staging (dedup by overture_id using QUALIFY)
  2. Export BQ staging → GCS CSV
  3. Download CSV, process locally (map categories, final dedup)
  4. Import into holy_sites via SQLite
"""
import os, csv, json, tempfile, sqlite3, time
from datetime import datetime
os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = ''
from google.cloud import bigquery
from google.cloud.bigquery import QueryJobConfig

DB = "E:/grid/churches.db"
PROJECT = 'american-rel-infra'
DATASET = 'American_Religious_Infrastructure'
NOW = datetime.utcnow().isoformat()
t0 = time.time()

def log(msg):
    print(f"[{time.time()-t0:7.1f}s] {msg}", flush=True)

# ── Category → holy_sites mapping ──
CATEGORY_MAP = {
    "church_cathedral":       ("Christian", None,          "church"),
    "catholic_church":        ("Christian", "Catholic",    "church"),
    "baptist_church":         ("Christian", "Baptist",     "church"),
    "evangelical_church":     ("Christian", "Evangelical", "church"),
    "pentecostal_church":     ("Christian", "Pentecostal", "church"),
    "anglican_church":        ("Christian", "Anglican",    "church"),
    "episcopal_church":       ("Christian", "Episcopal",   "church"),
    "hindu_temple":           ("Hindu",     None,          "temple"),
    "mosque":                 ("Islam",     None,          "mosque"),
    "buddhist_temple":        ("Buddhist",  None,          "temple"),
    "synagogue":              ("Jewish",    None,          "synagogue"),
    "sikh_temple":            ("Sikh",      None,          "temple"),
    "shinto_shrines":         ("Shinto",    None,          "shrine"),
    "religious_destination":  ("Christian", None,          "shrine"),
}

# Taxonomy → (tradition, landmark_type) for resolving religious_organization and temple
TAXONOMY_MAP = {
    "hindu_place_of_worship":          ("Hindu",    "temple"),
    "muslim_place_of_worship":         ("Islam",    "mosque"),
    "buddhist_place_of_worship":       ("Buddhist", "temple"),
    "jewish_place_of_worship":         ("Jewish",   "synagogue"),
    "sikh_place_of_worship":           ("Sikh",     "temple"),
    "christian_place_of_worship":      ("Christian", "church"),
    "catholic_place_of_worship":       ("Christian", "church"),
    "anglican_place_of_worship":       ("Christian", "church"),
    "shinto_place_of_worship":         ("Shinto",   "shrine"),
}

QUERY_CATEGORIES = [
    "church_cathedral", "catholic_church", "baptist_church", "evangelical_church",
    "pentecostal_church", "anglican_church", "episcopal_church",
    "hindu_temple", "mosque", "buddhist_temple", "synagogue", "sikh_temple",
    "shinto_shrines", "religious_organization", "religious_destination", "temple",
]

client = bigquery.Client(project=PROJECT)
staging_ref = f'{PROJECT}.{DATASET}.overture_holy_staging'

# ── Step 1: CTAS into BQ staging ──
log("Creating staging table via CTAS (this runs entirely in BQ)...")
client.delete_table(staging_ref, not_found_ok=True)

cat_list = ", ".join(f"'{c}'" for c in QUERY_CATEGORIES)
sql_ctas = f"""
CREATE TABLE `{staging_ref}` AS
SELECT
    id AS overture_id,
    names.primary AS name,
    categories.primary AS category,
    taxonomy.primary AS taxonomy_primary,
    confidence,
    ROUND(ST_Y(geometry), 6) AS latitude,
    ROUND(ST_X(geometry), 6) AS longitude,
    addresses.list[SAFE_OFFSET(0)].element.country AS country,
    websites.list[SAFE_OFFSET(0)].element AS website
FROM `bigquery-public-data.overture_maps.place`
WHERE categories.primary IN ({cat_list})
  AND names.primary IS NOT NULL
  AND names.primary != ''
  AND geometry IS NOT NULL
QUALIFY ROW_NUMBER() OVER (PARTITION BY id ORDER BY 
    CASE categories.primary
        WHEN 'catholic_church' THEN 1 WHEN 'baptist_church' THEN 1
        WHEN 'evangelical_church' THEN 1 WHEN 'pentecostal_church' THEN 1
        WHEN 'anglican_church' THEN 1 WHEN 'episcopal_church' THEN 1
        WHEN 'hindu_temple' THEN 1 WHEN 'mosque' THEN 1
        WHEN 'buddhist_temple' THEN 1 WHEN 'synagogue' THEN 1
        WHEN 'sikh_temple' THEN 1
        ELSE 2
    END) = 1
"""

job = client.query(sql_ctas, job_config=QueryJobConfig(priority=bigquery.QueryPriority.INTERACTIVE))
log("CTAS submitted — running in BQ...")
job.result()

# Get count
count_job = client.query(f"SELECT COUNT(*) as cnt FROM `{staging_ref}`")
count = list(count_job.result())[0].cnt
log(f"Staging table created: {count:,} rows (deduped by overture_id)")

# ── Step 2: Export to GCS ──
log("Exporting to GCS...")
ts = datetime.now().strftime("%Y%m%d_%H%M%S")
gcs_uri = f'gs://grantwizard-data/overture_holy_{ts}.csv'
extract_job = client.extract_table(staging_ref, gcs_uri)
extract_job.result()
log(f"Exported to {gcs_uri}")

# ── Step 3: Download ──
log("Downloading CSV...")
from google.cloud import storage
gcs = storage.Client()
bucket = gcs.bucket('grantwizard-data')
blob = bucket.blob(f'overture_holy_{ts}.csv')
csv_path = os.path.join(tempfile.gettempdir(), f'overture_holy_{ts}.csv')
blob.download_to_filename(csv_path)
size_mb = os.path.getsize(csv_path) / 1024 / 1024
log(f"Downloaded: {size_mb:.1f} MB")

# ── Step 4: Process CSV — map categories, resolve ambiguous, final dedup ──
log("Processing CSV — mapping categories...")

db = sqlite3.connect(DB)

# Get existing coordinates grid for dedup
log("  Building existing coordinate grid...")
existing = db.execute("""
    SELECT ROUND(lat, 2), ROUND(lon, 2) FROM holy_sites WHERE lat IS NOT NULL
    UNION
    SELECT ROUND(latitude, 2), ROUND(longitude, 2) FROM churches 
    WHERE latitude IS NOT NULL AND latitude != 0
""").fetchall()
grid = set(existing)
log(f"  {len(grid):,} grid cells from existing data")

# Process CSV
stats_cat = {}
skipped_ambiguous = 0
skipped_dup = 0
rows_to_insert = []

with open(csv_path, 'r', encoding='utf-8') as f:
    reader = csv.DictReader(f)
    for row in reader:
        name = (row.get('name') or '').strip()
        if not name:
            continue
        
        category = row.get('category', '')
        taxonomy = row.get('taxonomy_primary', '') or ''
        
        # Map category
        mapping = CATEGORY_MAP.get(category)
        if mapping:
            tradition, subtradition, landmark_type = mapping
        elif category == 'religious_organization':
            # Try taxonomy
            tm = TAXONOMY_MAP.get(taxonomy)
            if tm:
                tradition, landmark_type = tm
                subtradition = None
            else:
                skipped_ambiguous += 1
                continue
        elif category == 'temple':
            tm = TAXONOMY_MAP.get(taxonomy)
            if tm:
                tradition, landmark_type = tm
                subtradition = None
            else:
                skipped_ambiguous += 1
                continue
        else:
            skipped_ambiguous += 1
            continue
        
        # Grid dedup
        try:
            lat = float(row.get('latitude', 0) or 0)
            lon = float(row.get('longitude', 0) or 0)
        except (ValueError, TypeError):
            continue
        
        if lat == 0 and lon == 0:
            continue
        
        glat, glon = round(lat, 2), round(lon, 2)
        if (glat, glon) in grid:
            skipped_dup += 1
            continue
        
        # Track
        key = f"{tradition}/{subtradition or '-'}"
        stats_cat[key] = stats_cat.get(key, 0) + 1
        
        conf = round(min(1.0, float(row.get('confidence', 0.5) or 0.5) + (0.1 if subtradition else 0)), 2)
        country = (row.get('country') or 'ZZ').strip()[:2]
        website = (row.get('website') or '').strip()[:500] or None
        
        rows_to_insert.append((
            name[:500], tradition, subtradition, country, lat, lon,
            "overture", category, 0, landmark_type,
            None, row.get('overture_id', ''), conf, website
        ))

log(f"  Mapped: {len(rows_to_insert):,} rows")
log(f"  Skipped ambiguous: {skipped_ambiguous:,}")
log(f"  Skipped duplicates (grid): {skipped_dup:,}")
log(f"  Tradition breakdown: {json.dumps(stats_cat, indent=2)}")

# ── Step 5: Import into holy_sites ──
log(f"Importing {len(rows_to_insert):,} records into holy_sites...")

db.execute("BEGIN")
batch_size = 10000
for start in range(0, len(rows_to_insert), batch_size):
    batch = rows_to_insert[start:start + batch_size]
    db.executemany("""
        INSERT OR IGNORE INTO holy_sites
        (name, tradition, subtradition, country, lat, lon,
         source_primary, source_secondary, is_landmark, landmark_type,
         wikidata_qid, osm_id, confidence_score, website)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, batch)
    if start % 100000 == 0:
        log(f"  {start:,} / {len(rows_to_insert):,}...")

db.commit()

# ── Step 6: Provenance log ──
db.execute("""
    INSERT INTO provenance_log
    (source, script_name, started_at, completed_at, churches_inserted,
     fields_populated, records_attempted, records_matched, status, notes)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'completed', ?)
""", (
    "overture_global", "overture_global_holy_sites.py", NOW,
    datetime.utcnow().isoformat(), len(rows_to_insert),
    "name,tradition,subtradition,country,lat,lon,landmark_type,website",
    count, len(rows_to_insert),
    f"Global Overture import: {count:,} from BQ, {len(rows_to_insert):,} inserted. "
    f"Categories: {json.dumps(stats_cat)}. "
    f"Skipped: {skipped_ambiguous:,} ambiguous, {skipped_dup:,} grid dups."
))
db.commit()

total_hs = db.execute("SELECT COUNT(*) FROM holy_sites").fetchone()[0]
db.close()

log(f"\n{'='*60}")
log(f"DONE: {len(rows_to_insert):,} records imported into holy_sites")
log(f"holy_sites total: {total_hs:,}")
log(f"Runtime: {time.time()-t0:.0f}s")

# Cleanup
blob.delete()
client.delete_table(staging_ref, not_found_ok=True)
try:
    os.unlink(csv_path)
except:
    pass
log("Cleaned up GCS + BQ staging")
