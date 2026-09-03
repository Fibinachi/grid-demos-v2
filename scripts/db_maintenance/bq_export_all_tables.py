"""
Export ALL remaining tables (not churches) to BigQuery.
Uses the proven CSV → explicit schema → BQ load pipeline.
"""
import os, sys, time, csv, sqlite3, tempfile
from pathlib import Path
from google.cloud import bigquery

PROJECT = "american-rel-infra"
DATASET = "American_Religious_Infrastructure"
DB_PATH = r"E:\grid\churches.db"
CSV_DIR = Path(r"E:\grid\data\bq_exports")
CSV_DIR.mkdir(exist_ok=True)

# Tables to export
TABLES = [
    "churches",               # 3.28M rows, 92 cols — ~1.9 GB CSV
    "church_enrichment",      # 1.48M rows, 149 cols — large CSV!
    "church_external_ids",    # 4.94M rows, 6 cols
    "church_sources",         # 4.93M rows, 5 cols
    "church_metrics",         # 2M rows, 9 cols
    "church_contact_values",  # 463K rows
    "catholic_hierarchy",     # 337K rows
    "anglican_hierarchy",     # 69K
    "orthodox_hierarchy",     # 60K
    "lutheran_hierarchy",     # 57K
    "baptist_hierarchy",      # 36K
    "lds_hierarchy",          # 19K
    "jw_hierarchy",           # 11K
    "chabad_hierarchy",       # 2.9K
    "ahmadiyya_hierarchy",    # 140
    "bahai_hierarchy",        # 1.2K
    "sa_hierarchy",           # 2.9K
    "moravian_hierarchy",     # 608
    "mapping_saints",         # 3.8K
    "rucc_codes",             # 3.2K
    "arda_counts",            # 74K
    "arda_counts_2010",       # 77K
    "geonames_postal",        # 1.39M
    "emergency_stations",     # 49K
    "church_census_catalog",  # 163
    "provenance_log",         # 1.1K
    "enrichment_change_log",  # 2.2M
]

def log(msg):
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)

def progress_bar(current, total, width=30):
    if total == 0:
        return f"[{'█'*width}] {current}"
    pct = current / total
    filled = int(width * pct)
    return f"[{'█'*filled}{'░'*(width-filled)}] {current}/{total} ({pct*100:.0f}%)"

def export_table_to_csv(table_name):
    """Export SQLite table to CSV. Returns (csv_path, row_count)."""
    csv_path = CSV_DIR / f"{table_name}.csv"
    
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    # Check table exists
    c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table_name,))
    if not c.fetchone():
        conn.close()
        return None, 0
    
    cols = [r[1] for r in c.execute(f"PRAGMA table_info('{table_name}')").fetchall()]
    row_count = c.execute(f"SELECT COUNT(*) FROM '{table_name}'").fetchone()[0]
    
    if row_count == 0:
        conn.close()
        return None, 0
    
    # Write CSV
    BATCH = 50000
    written = 0
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f, quoting=csv.QUOTE_ALL)
        writer.writerow(cols)
        
        for offset in range(0, row_count, BATCH):
            rows = c.execute(f'SELECT * FROM "{table_name}" LIMIT {BATCH} OFFSET {offset}').fetchall()
            for row in rows:
                writer.writerow([str(v) if v is not None else "" for v in row])
            written += len(rows)
    
    conn.close()
    size_mb = os.path.getsize(csv_path) / (1024*1024)
    return csv_path, row_count

def load_csv_to_bq(table_name, csv_path, row_count):
    """Load CSV into BigQuery with explicit STRING schema."""
    table_ref = f"{PROJECT}.{DATASET}.{table_name}"
    
    # Build schema from CSV header
    with open(csv_path, encoding="utf-8") as f:
        reader = csv.reader(f)
        header = next(reader)
    
    schema = [bigquery.SchemaField(name, "STRING", mode="NULLABLE") for name in header]
    
    client = bigquery.Client(project=PROJECT)
    
    # Drop existing
    try:
        client.delete_table(table_ref, not_found_ok=True)
        time.sleep(1)
    except:
        pass
    
    # Create table
    table = bigquery.Table(table_ref, schema=schema)
    client.create_table(table)
    
    # Load CSV
    size_mb = os.path.getsize(csv_path) / (1024*1024)
    job_config = bigquery.LoadJobConfig(
        source_format=bigquery.SourceFormat.CSV,
        write_disposition=bigquery.WriteDisposition.WRITE_APPEND,
        max_bad_records=10000,
        quote_character='"',
        skip_leading_rows=1,
        allow_quoted_newlines=True,
    )
    
    t0 = time.time()
    with open(csv_path, "rb") as f:
        job = client.load_table_from_file(f, table_ref, job_config=job_config)
    
    try:
        result = job.result(timeout=600)
        elapsed = time.time() - t0
        ok = result.output_rows == row_count
        status = "✅" if ok else "⚠"
        log(f"  {status} {result.output_rows:,} rows in {elapsed:.0f}s ({size_mb:.0f} MB)")
        return ok
    except Exception as e:
        log(f"  ❌ Failed: {str(e)[:200]}")
        return False

# ── Main ──
log(f"Exporting {len(TABLES)} tables to BigQuery")
log(f"Project: {PROJECT}.{DATASET}")

total_ok = 0
total_fail = 0
start_all = time.time()

for i, table_name in enumerate(TABLES):
    log(f"\n[{i+1}/{len(TABLES)}] {table_name}")
    
    # Step 1: Export to CSV
    t0 = time.time()
    csv_path, row_count = export_table_to_csv(table_name)
    
    if csv_path is None:
        log(f"  ⚠ Skipping (empty or not found)")
        continue
    
    elapsed_csv = time.time() - t0
    size_mb = os.path.getsize(csv_path) / (1024*1024) if csv_path else 0
    log(f"  CSV: {row_count:,} rows, {size_mb:.0f} MB ({elapsed_csv:.0f}s)")
    
    # Step 2: Load to BQ
    ok = load_csv_to_bq(table_name, csv_path, row_count)
    
    if ok:
        total_ok += 1
    else:
        total_fail += 1
    
    # Clean up CSV
    os.remove(csv_path)

elapsed_all = time.time() - start_all
log(f"\n{'='*60}")
log(f"Done in {elapsed_all/60:.1f} min")
log(f"  ✅ {total_ok} tables")
if total_fail:
    log(f"  ❌ {total_fail} failed")
log(f"  Dataset: {PROJECT}.{DATASET}")
