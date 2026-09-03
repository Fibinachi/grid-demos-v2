"""
Push the 1865 Catholic Directory DB (catholic_directory.db) to BigQuery.
Uses the proven CSV + explicit STRING schema pipeline.
"""
import os, sys, time, csv, sqlite3
from pathlib import Path
from google.cloud import bigquery

PROJECT = "american-rel-infra"
DATASET = "American_Religious_Infrastructure"
DB_PATH = r"E:\grid\data\catholic_directory.db"
CSV_DIR = Path(r"E:\grid\data\bq_exports_1865")
CSV_DIR.mkdir(exist_ok=True)

# Prefix tables with "cd1865_" in BQ to avoid name collisions
BQ_PREFIX = "cd1865_"

def log(msg):
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)

client = bigquery.Client(project=PROJECT)

# Get all tables from the 1865 DB
src = sqlite3.connect(DB_PATH)
tables = [r[0] for r in src.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name").fetchall()]
src.close()

log(f"Found {len(tables)} tables in catholic_directory.db")

ok = 0
fail = 0
total_rows_all = 0

for i, table_name in enumerate(tables):
    src = sqlite3.connect(DB_PATH)
    
    # Check row count
    row_count = src.execute(f"SELECT COUNT(*) FROM \"{table_name}\"").fetchone()[0]
    cols = [r[1] for r in src.execute(f"PRAGMA table_info(\"{table_name}\")").fetchall()]
    
    if row_count == 0:
        log(f"[{i+1}/{len(tables)}] {table_name}: empty, skipping")
        src.close()
        continue
    
    # Export to CSV
    csv_path = CSV_DIR / f"{table_name}.csv"
    BATCH = 50000
    written = 0
    
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f, quoting=csv.QUOTE_ALL)
        writer.writerow(cols)
        for offset in range(0, row_count, BATCH):
            rows = src.execute(f'SELECT * FROM "{table_name}" LIMIT {BATCH} OFFSET {offset}').fetchall()
            for row in rows:
                writer.writerow([str(v) if v is not None else "" for v in row])
            written += len(rows)
    
    src.close()
    size_mb = os.path.getsize(csv_path) / (1024*1024)
    log(f"[{i+1}/{len(tables)}] {table_name}: {row_count:,} rows, {size_mb:.0f} MB CSV")
    
    # Upload to BQ
    bq_table = f"{BQ_PREFIX}{table_name}"
    table_ref = f"{PROJECT}.{DATASET}.{bq_table}"
    
    # Drop existing
    try:
        client.delete_table(table_ref, not_found_ok=True)
        time.sleep(1)
    except:
        pass
    
    # Create with explicit STRING schema
    schema = [bigquery.SchemaField(name, "STRING", mode="NULLABLE") for name in cols]
    table = bigquery.Table(table_ref, schema=schema)
    client.create_table(table)
    
    # Load CSV
    job_config = bigquery.LoadJobConfig(
        source_format=bigquery.SourceFormat.CSV,
        write_disposition=bigquery.WriteDisposition.WRITE_APPEND,
        max_bad_records=100,
        quote_character='"',
        skip_leading_rows=1,
        allow_quoted_newlines=True,
    )
    
    t0 = time.time()
    with open(csv_path, "rb") as f:
        job = client.load_table_from_file(f, table_ref, job_config=job_config)
    
    try:
        result = job.result(timeout=300)
        elapsed = time.time() - t0
        
        if result.output_rows == row_count:
            log(f"  ✅ {result.output_rows:,} rows in {elapsed:.0f}s")
            ok += 1
        else:
            log(f"  ⚠ {result.output_rows:,}/{row_count:,} rows in {elapsed:.0f}s")
            ok += 1
        total_rows_all += result.output_rows
    except Exception as e:
        log(f"  ❌ Failed: {str(e)[:200]}")
        fail += 1
    
    os.remove(csv_path)

# Cleanup
os.rmdir(CSV_DIR)

log(f"\n{'='*60}")
log(f"Done! {ok} tables, {fail} failed, {total_rows_all:,} total rows")
log(f"Dataset: {PROJECT}.{DATASET} (prefix: {BQ_PREFIX})")
