"""
Fast BQ push using bq CLI (more reliable for large files).
Uses the already-exported CSV files and bq load.
"""
import subprocess, os, time, csv, sqlite3
from pathlib import Path

PROJECT = "american-rel-infra"
DATASET = "American_Religious_Infrastructure"
DB_PATH = r"E:\grid\churches.db"
CSV_DIR = Path(r"E:\grid\data\bq_exports")
CSV_DIR.mkdir(exist_ok=True)

# Tables to push (churches + enrichment first, then others)
TABLES = [
    "churches",               # ~3.28M rows, 1.9 GB
    "church_enrichment",      # 1.48M, 765 MB (already exported)
    "church_external_ids",
    "church_sources",
    "church_metrics",
    "church_contact_values",
    "catholic_hierarchy", "anglican_hierarchy", "orthodox_hierarchy",
    "lutheran_hierarchy", "baptist_hierarchy", "lds_hierarchy",
    "jw_hierarchy", "chabad_hierarchy", "ahmadiyya_hierarchy",
    "bahai_hierarchy", "sa_hierarchy", "moravian_hierarchy",
    "mapping_saints", "rucc_codes", "arda_counts", "arda_counts_2010",
    "geonames_postal", "emergency_stations", "church_census_catalog",
    "provenance_log", "enrichment_change_log",
]

def log(msg):
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)

# Step 1: Export all tables to CSV (skip if already exists)
log("Step 1: Exporting SQLite → CSV...")
conn = sqlite3.connect(DB_PATH)

for table_name in TABLES:
    csv_path = CSV_DIR / f"{table_name}.csv"
    
    # Skip if CSV already exists and is fresh
    if csv_path.exists():
        size_mb = os.path.getsize(csv_path) / (1024*1024)
        log(f"  {table_name}: CSV exists ({size_mb:.0f} MB), skipping export")
        continue
    
    # Check table
    c = conn.cursor()
    c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table_name,))
    if not c.fetchone():
        log(f"  {table_name}: not found, skipping")
        continue
    
    cols = [r[1] for r in c.execute(f"PRAGMA table_info('{table_name}')").fetchall()]
    row_count = c.execute(f"SELECT COUNT(*) FROM '{table_name}'").fetchone()[0]
    
    if row_count == 0:
        log(f"  {table_name}: empty, skipping")
        continue
    
    # Write CSV
    BATCH = 50000
    written = 0
    t0 = time.time()
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f, quoting=csv.QUOTE_ALL)
        writer.writerow(cols)
        for offset in range(0, row_count, BATCH):
            rows = c.execute(f'SELECT * FROM "{table_name}" LIMIT {BATCH} OFFSET {offset}').fetchall()
            for row in rows:
                writer.writerow([str(v) if v is not None else "" for v in row])
            written += len(rows)
    
    elapsed = time.time() - t0
    size_mb = os.path.getsize(csv_path) / (1024*1024)
    log(f"  {table_name}: {row_count:,} rows → {size_mb:.0f} MB ({elapsed:.0f}s)")

conn.close()

# Step 2: Load all CSVs into BQ using bq CLI
log("\nStep 2: Loading CSVs into BigQuery...")
ok = 0
fail = 0

for table_name in TABLES:
    csv_path = CSV_DIR / f"{table_name}.csv"
    if not csv_path.exists():
        continue
    
    size_mb = os.path.getsize(csv_path) / (1024*1024)
    table_ref = f"{PROJECT}:{DATASET}.{table_name}"
    
    log(f"  {table_name}: loading {size_mb:.0f} MB...")
    t0 = time.time()
    
    result = subprocess.run([
        "bq", "load",
        "--source_format=CSV",
        "--autodetect",
        "--replace",
        "--max_bad_records=50000",
        "--quote", '"',
        table_ref,
        str(csv_path),
    ], capture_output=True, text=True, timeout=1800)
    
    elapsed = time.time() - t0
    
    if result.returncode == 0:
        # Extract row count from output
        ok += 1
        log(f"    ✅ Done in {elapsed:.0f}s")
    else:
        fail += 1
        log(f"    ❌ Failed: {result.stderr[:300]}")
    
    # Delete CSV after successful load
    os.remove(csv_path)

log(f"\n{'='*60}")
log(f"Done! ✅ {ok} tables, ❌ {fail} failed")
log(f"Dataset: {PROJECT}.{DATASET}")

# Cleanup
try:
    os.rmdir(CSV_DIR)
except:
    pass
