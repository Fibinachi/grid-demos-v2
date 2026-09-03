"""Load the pre-exported CSV into BigQuery using Python SDK with explicit schema."""
import os, time, sqlite3
from google.cloud import bigquery

PROJECT = "american-rel-infra"
DATASET = "American_Religious_Infrastructure"
CSV_PATH = r"E:\grid\data\churches_export.csv"
DB_PATH = r"E:\grid\churches.db"
TABLE = "churches"
table_ref = f"{PROJECT}.{DATASET}.{TABLE}"

size_gb = os.path.getsize(CSV_PATH) / (1024**3)
print(f"CSV: {size_gb:.2f} GB")

# Build explicit schema from SQLite to avoid autodetect type mismatches
print("Building schema from SQLite...")
conn = sqlite3.connect(DB_PATH)
cols = conn.execute("PRAGMA table_info(churches)").fetchall()
conn.close()

# All columns as STRING to avoid type coercion issues
# (SQLite is dynamically typed; some "zip5" values are state names, etc.)
schema = []
for col in cols:
    col_name = col[1]
    # Use STRING for everything — safest for messy data
    schema.append(bigquery.SchemaField(col_name, "STRING", mode="NULLABLE"))

print(f"  {len(schema)} columns (all STRING)")

client = bigquery.Client(project=PROJECT)

# Drop existing table
print("Dropping existing table...")
try:
    client.delete_table(table_ref, not_found_ok=True)
    time.sleep(2)
    print("  Done")
except Exception as e:
    print(f"  Warning: {e}")

# Create empty table with schema first
print("Creating table with explicit schema...")
table = bigquery.Table(table_ref, schema=schema)
client.create_table(table)
print("  Done")

# Load CSV data
print(f"Loading CSV (this may take 5-15 minutes for {size_gb:.1f} GB)...")
job_config = bigquery.LoadJobConfig(
    source_format=bigquery.SourceFormat.CSV,
    write_disposition=bigquery.WriteDisposition.WRITE_APPEND,  # Append to empty table
    max_bad_records=50000,
    quote_character='"',
    skip_leading_rows=1,  # Skip header
    allow_quoted_newlines=True,
    ignore_unknown_values=False,
)

t0 = time.time()
with open(CSV_PATH, "rb") as f:
    job = client.load_table_from_file(f, table_ref, job_config=job_config)

try:
    result = job.result(timeout=1800)  # 30 min timeout
    elapsed = time.time() - t0
    print(f"  ✅ Loaded {result.output_rows:,} rows in {elapsed:.0f}s")
except Exception as e:
    elapsed = time.time() - t0
    print(f"  ❌ Job failed after {elapsed:.0f}s: {e}")
    if hasattr(job, 'errors') and job.errors:
        for err in job.errors[:3]:
            print(f"    {err}")

# Verify
t = client.get_table(table_ref)
print(f"\nBQ table: {t.num_rows:,} rows, {t.num_bytes/(1024**3):.1f} GB")

# Clean up CSV
os.remove(CSV_PATH)
print(f"Cleaned up CSV")
