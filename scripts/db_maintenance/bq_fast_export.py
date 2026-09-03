"""
Fast BQ Export: SQLite → CSV (Python csv.writer) → bq load
Much faster than JSON serialization — CSV writing is ~10x faster.
"""
import subprocess, os, sys, time, csv
from pathlib import Path
from google.cloud import bigquery

DB = r"E:\grid\churches.db"
PROJECT = "american-rel-infra"
DATASET = "American_Religious_Infrastructure"
CSV_PATH = r"E:\grid\data\churches_export.csv"

print("Step 1: Exporting churches.db → CSV...")
t0 = time.time()

import sqlite3
conn = sqlite3.connect(DB)
c = conn.cursor()

# Get column names
cols = [r[1] for r in c.execute("PRAGMA table_info(churches)").fetchall()]
row_count = c.execute("SELECT COUNT(*) FROM churches").fetchone()[0]
print(f"  {row_count:,} rows, {len(cols)} columns")

# Write CSV in streaming fashion
BATCH = 50000
written = 0
with open(CSV_PATH, "w", newline="", encoding="utf-8") as f:
    writer = csv.writer(f, quoting=csv.QUOTE_ALL)
    writer.writerow(cols)  # Header
    
    for offset in range(0, row_count, BATCH):
        rows = c.execute(f"SELECT * FROM churches LIMIT {BATCH} OFFSET {offset}").fetchall()
        for row in rows:
            # Convert None to empty string, everything else to string
            writer.writerow([str(v) if v is not None else "" for v in row])
        written += len(rows)
        pct = written / row_count * 100
        print(f"  {written:,}/{row_count:,} ({pct:.0f}%)", end="\r", flush=True)

conn.close()
print()

elapsed = time.time() - t0
size_mb = os.path.getsize(CSV_PATH) / (1024**1024)
print(f"  Done in {elapsed:.0f}s — {size_mb:.0f} MB ({row_count/elapsed:.0f} rows/s)")

# Step 2: Upload to BigQuery via bq load
print(f"\nStep 2: Loading CSV into BQ...")
table_ref = f"{PROJECT}.{DATASET}.churches"

# Drop existing table
print("  Dropping existing table...")
subprocess.run(["bq", "rm", "-f", "-t", table_ref], capture_output=True, timeout=30)

# Load CSV with autodetect schema
print(f"  Loading {size_mb:.0f} MB CSV (this may take 5-15 minutes)...")
t1 = time.time()
result = subprocess.run(
    ["bq", "load",
     "--source_format=CSV",
     "--autodetect",
     "--replace",
     "--max_bad_records=5000",
     "--quote", '"',
     table_ref,
     CSV_PATH],
    capture_output=True, text=True, timeout=3600
)

elapsed2 = time.time() - t1
print(f"  bq load done in {elapsed2:.0f}s")

if result.returncode != 0:
    print(f"  STDERR: {result.stderr[:1000]}")
else:
    print(f"  STDOUT: {result.stdout[:500]}")

# Cleanup
os.remove(CSV_PATH)
print(f"  Cleaned up CSV")

# Verify
c_bq = bigquery.Client(project=PROJECT)
t = c_bq.get_table(table_ref)
print(f"\n✅ BQ churches: {t.num_rows:,} rows, {t.num_bytes/(1024**3):.1f} GB")
print(f"   Expected: {row_count:,} rows")
if t.num_rows == row_count:
    print(f"   ✅ ROW COUNT MATCHES!")
else:
    print(f"   ⚠ Mismatch: diff={t.num_rows - row_count:,}")
