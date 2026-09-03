"""Use BQ REST API + gcloud auth to export Overture staging → holy_sites.
Avoids the broken google-cloud-bigquery Python library entirely."""
import json, sqlite3, time, subprocess, tempfile, os, csv
from datetime import datetime
import requests

DB = "E:/grid/churches.db"
PROJECT = 'american-rel-infra'
GCS_BUCKET = 'grantwizard-overture-export'
NOW = datetime.utcnow().isoformat()
t0 = time.time()

def log(msg):
    print(f"[{time.time()-t0:7.1f}s] {msg}", flush=True)

def get_token():
    result = subprocess.run(
        ['cmd', '/c', 'gcloud', 'auth', 'print-access-token'],
        capture_output=True, text=True, timeout=30
    )
    return result.stdout.strip()

def bq_api(path, method='GET', body=None):
    token = get_token()
    headers = {'Authorization': f'Bearer {token}', 'Content-Type': 'application/json'}
    url = f'https://bigquery.googleapis.com/bigquery/v2/{path}'
    if method == 'GET':
        return requests.get(url, headers=headers, timeout=300).json()
    else:
        return requests.post(url, headers=headers, json=body, timeout=300).json()

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

TAXONOMY_MAP = {
    "hindu_place_of_worship":    ("Hindu",     "temple"),
    "muslim_place_of_worship":   ("Islam",     "mosque"),
    "buddhist_place_of_worship": ("Buddhist",  "temple"),
    "jewish_place_of_worship":   ("Jewish",    "synagogue"),
    "sikh_place_of_worship":     ("Sikh",      "temple"),
    "christian_place_of_worship":("Christian", "church"),
    "catholic_place_of_worship": ("Christian", "church"),
    "anglican_place_of_worship": ("Christian", "church"),
    "shinto_place_of_worship":   ("Shinto",    "shrine"),
}

# ── Step 1: Create extract job to GCS ──
log("Creating extract job via REST API...")
ts = datetime.now().strftime("%Y%m%d_%H%M%S")
gcs_dest = f'gs://{GCS_BUCKET}/overture_holy_{ts}_*.csv'

body = {
    "jobReference": {
        "projectId": PROJECT,
        "jobId": f"overture_extract_{ts}"
    },
    "configuration": {
        "extract": {
            "sourceTable": {
                "projectId": PROJECT,
                "datasetId": "American_Religious_Infrastructure",
                "tableId": "overture_holy_staging"
            },
            "destinationUris": [gcs_dest],
            "destinationFormat": "CSV",
            "printHeader": True,
            "fieldDelimiter": ","
        }
    }
}

result = bq_api(f'projects/{PROJECT}/jobs', 'POST', body)
job_id = result['jobReference']['jobId']
log(f"  Job ID: {job_id}")

# ── Step 2: Poll for completion ──
log("Polling for extract completion...")
while True:
    status = bq_api(f'projects/{PROJECT}/jobs/{job_id}')
    state = status['status']['state']
    if state == 'DONE':
        log(f"  Extract complete!")
        break
    elif 'errorResult' in status.get('status', {}):
        log(f"  ERROR: {status['status']['errorResult']}")
        exit(1)
    log(f"  State: {state}...")
    time.sleep(5)

# Get output file(s)
files = status['statistics']['extract']['destinationUriFileCounts']
log(f"  Output files: {files}")

# ── Step 3: Download from GCS via REST API ──
log("Downloading via REST API...")

# List objects in the extract output
token = get_token()
list_url = f'https://storage.googleapis.com/storage/v1/b/{GCS_BUCKET}/o?prefix=overture_holy_{ts}_'
resp = requests.get(list_url, headers={'Authorization': f'Bearer {token}'}, timeout=60)
items = resp.json().get('items', [])

csv_files = []
for item in items:
    name = item['name']
    size = int(item['size'])
    local_path = os.path.join(tempfile.gettempdir(), name.split('/')[-1])
    
    # Download each file
    dl_url = f'https://storage.googleapis.com/storage/v1/b/{GCS_BUCKET}/o/{name}?alt=media'
    dl_resp = requests.get(dl_url, headers={'Authorization': f'Bearer {token}'}, timeout=300, stream=True)
    dl_resp.raise_for_status()
    
    with open(local_path, 'wb') as f:
        for chunk in dl_resp.iter_content(chunk_size=8192*1024):
            f.write(chunk)
    
    csv_files.append(local_path)
    log(f"  Downloaded {name} ({size/1024/1024:.1f} MB)")

total_size = sum(os.path.getsize(f) for f in csv_files)
log(f"  Total: {len(csv_files)} file(s), {total_size/1024/1024:.1f} MB")

# ── Step 4: Build grid ──
log("Building coordinate grid...")
db = sqlite3.connect(DB)
existing = db.execute("""
    SELECT ROUND(lat,2), ROUND(lon,2) FROM holy_sites WHERE lat IS NOT NULL
    UNION
    SELECT ROUND(latitude,2), ROUND(longitude,2) FROM churches WHERE latitude IS NOT NULL AND latitude!=0
""").fetchall()
grid = set(existing)
log(f"  {len(grid):,} grid cells")

# ── Step 5: Process CSV(s) ──
stats_cat = {}
skipped_amb, skipped_dup, total_ins = 0, 0, 0

for csv_file in csv_files:
    log(f"  Processing {os.path.basename(csv_file)}...")
    rows_buf = []
    
    with open(csv_file, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            name = (row.get('name') or '').strip()
            if not name: continue
            
            cat = (row.get('category') or '')
            tax = (row.get('taxonomy_primary') or '').lower()
            
            m = CATEGORY_MAP.get(cat)
            if m:
                trad, sub, lm = m
            elif cat in ('religious_organization','temple'):
                tm = TAXONOMY_MAP.get(tax)
                if tm: trad, lm = tm; sub = None
                else: skipped_amb += 1; continue
            else:
                skipped_amb += 1; continue
            
            try: lat=float(row.get('latitude',0) or 0); lon=float(row.get('longitude',0) or 0)
            except: continue
            if lat==0 and lon==0: continue
            
            gl, gn = round(lat,2), round(lon,2)
            if (gl, gn) in grid: skipped_dup += 1; continue
            
            k = f"{trad}/{sub or '-'}"
            stats_cat[k] = stats_cat.get(k,0)+1
            
            conf = round(min(1.0, float(row.get('confidence',0.5) or 0.5)+(0.1 if sub else 0)), 2)
            cntry = (row.get('country') or 'ZZ').strip()[:2]
            web = (row.get('website') or '').strip()[:500] or None
            
            rows_buf.append((name[:500], trad, sub, cntry, lat, lon,
                "overture", cat, 0, lm, None, row.get('overture_id',''), conf, web))
            
            if len(rows_buf) >= 50000:
                db.execute("BEGIN")
                db.executemany("""INSERT OR IGNORE INTO holy_sites
                    (name,tradition,subtradition,country,lat,lon,
                     source_primary,source_secondary,is_landmark,landmark_type,
                     wikidata_qid,osm_id,confidence_score,website)
                    VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)""", rows_buf)
                db.commit()
                total_ins += len(rows_buf)
                log(f"    Flushed {len(rows_buf):,} (total: {total_ins:,})")
                rows_buf = []
    
    # Final flush for this file
    if rows_buf:
        db.execute("BEGIN")
        db.executemany("""INSERT OR IGNORE INTO holy_sites
            (name,tradition,subtradition,country,lat,lon,
             source_primary,source_secondary,is_landmark,landmark_type,
             wikidata_qid,osm_id,confidence_score,website)
            VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)""", rows_buf)
        db.commit()
        total_ins += len(rows_buf)

# ── Provenance ──
db.execute("""INSERT INTO provenance_log
    (source,script_name,started_at,completed_at,churches_inserted,
     fields_populated,records_attempted,records_matched,status,notes)
    VALUES(?,?,?,?,?,?,?,?,'completed',?)""", (
    "overture_global","overture_rest_import.py",NOW,datetime.utcnow().isoformat(),
    total_ins,"name,faith,tradition,country,lat,lon,landmark_type,website",
    0,total_ins,
    f"Global Overture via REST API+gsutil. {total_ins:,} inserted. {json.dumps(stats_cat)}"
))
db.commit()

total_hs = db.execute("SELECT COUNT(*) FROM holy_sites").fetchone()[0]
db.close()

log(f"\n{'='*60}")
log(f"DONE: {total_ins:,} imported | holy_sites: {total_hs:,}")
log(f"Skipped: {skipped_amb:,} ambiguous | {skipped_dup:,} grid dups")
for k, v in sorted(stats_cat.items(), key=lambda x:-x[1]):
    log(f"  {k:30s} {v:>10,}")
log(f"Runtime: {time.time()-t0:.0f}s")

# Cleanup downloaded files
for f in csv_files:
    try: os.unlink(f)
    except: pass
log("Cleaned up temp files")
