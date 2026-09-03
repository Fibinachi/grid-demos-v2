"""Export TN religious parcels to CSV and load into BigQuery."""
import sqlite3, csv, os, time, sys
from pathlib import Path
from google.cloud import bigquery

PROJECT = "american-rel-infra"
DATASET = "American_Religious_Infrastructure"
TABLE = "tn_religious_parcels"
STAGING_DB = Path("E:/grid/data/tn_parcels/tn_religious_parcels.db")
CSV_PATH = Path("E:/grid/data/tn_parcels/tn_religious_parcels.csv")
CHUNK_SIZE = 10000

table_ref = f"{PROJECT}.{DATASET}.{TABLE}"

# ── Step 1: Export to CSV ──
print("=" * 60)
print("STEP 1: Export to CSV")
print("=" * 60)

conn = sqlite3.connect(str(STAGING_DB))
conn.row_factory = sqlite3.Row

# Only export eligible parcels
where = "WHERE tn_filter IN ('church', 'parsonage', 'religious_cemetery')"
total = conn.execute(f"SELECT COUNT(*) FROM tn_religious_parcels {where}").fetchone()[0]
print(f"Exporting {total:,} eligible parcels...")

cols = [c[1] for c in conn.execute("PRAGMA table_info(tn_religious_parcels)").fetchall()]
# Remove SQLite internal columns
cols = [c for c in cols if c not in ('tn_filter', 'tn_filter_reason')]
# Add the filter columns at end
cols.append('tn_filter')
cols.append('tn_filter_reason')

with open(CSV_PATH, 'w', newline='', encoding='utf-8') as f:
    writer = csv.writer(f)
    writer.writerow(cols)
    
    offset = 0
    while True:
        rows = conn.execute(
            f"SELECT * FROM tn_religious_parcels {where} LIMIT {CHUNK_SIZE} OFFSET {offset}"
        ).fetchall()
        if not rows:
            break
        for row in rows:
            writer.writerow([row[c] for c in cols])
        offset += len(rows)
        pct = min(offset / total * 100, 100)
        print(f"\r  {offset:,} / {total:,} ({pct:.0f}%)", end="", flush=True)

conn.close()

size_mb = CSV_PATH.stat().st_size / (1024 * 1024)
print(f"\n  CSV saved: {size_mb:.1f} MB")

# ── Step 2: Load to BigQuery ──
print(f"\n{'=' * 60}")
print("STEP 2: Load to BigQuery")
print(f"{'=' * 60}")

client = bigquery.Client(project=PROJECT)

# Build schema: all STRING for safety
schema = [bigquery.SchemaField(c, "STRING", mode="NULLABLE") for c in cols]
print(f"  {len(schema)} columns (all STRING)")

# Drop existing
print(f"  Dropping existing {TABLE}...")
try:
    client.delete_table(table_ref, not_found_ok=True)
    time.sleep(2)
except Exception as e:
    print(f"  Warning: {e}")

# Create table
print("  Creating table...")
table = bigquery.Table(table_ref, schema=schema)
client.create_table(table)
print("  Done")

# Load CSV
print(f"  Loading CSV ({size_mb:.0f} MB)...")
job_config = bigquery.LoadJobConfig(
    source_format=bigquery.SourceFormat.CSV,
    skip_leading_rows=1,
    allow_quoted_newlines=True,
    max_bad_records=100,
    write_disposition=bigquery.WriteDisposition.WRITE_APPEND,
)

with open(CSV_PATH, "rb") as f:
    job = client.load_table_from_file(f, table_ref, job_config=job_config)

print(f"  Waiting for job {job.job_id}...")
result = job.result()
print(f"  ✅ Loaded {result.output_rows:,} rows")

# Verify
t = client.get_table(table_ref)
print(f"\n  Table: {t.table_id}")
print(f"  Rows:  {t.num_rows:,}")
print(f"  Size:  {t.num_bytes / (1024**3):.2f} GB")
print(f"  Modified: {t.modified}")

print(f"\n✅ Done — {TABLE} in BigQuery")
