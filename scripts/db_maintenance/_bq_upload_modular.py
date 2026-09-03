"""Quick upload of modular schema tables to BigQuery."""
import sqlite3, json, tempfile, os, time, traceback
from datetime import datetime, timezone
from google.cloud import bigquery

DB = r"E:\grid\churches.db"
PROJECT = "american-rel-infra"
DATASET = "American_Religious_Infrastructure"

def log(msg):
    print(f"[{datetime.now(timezone.utc).strftime('%H:%M:%S')}] {msg}", flush=True)

client = bigquery.Client(project=PROJECT)
conn = sqlite3.connect(DB)
conn.row_factory = sqlite3.Row

TABLES = [
    "churches", "church_external_ids", "church_sources", "church_metrics",
    "church_enrichment",
]

for table_name in TABLES:
    log(f"\n--- {table_name} ---")
    
    # Get schema from SQLite
    cols = [(r[1], r[2]) for r in conn.execute(f"PRAGMA table_info('{table_name}')").fetchall()]
    row_count = conn.execute(f"SELECT COUNT(*) FROM \"{table_name}\"").fetchone()[0]
    log(f"  {row_count:,} rows, {len(cols)} cols")
    
    if row_count == 0:
        log("  Skipping (empty)")
        continue
    
    # Map types
    type_map = {"INTEGER": "INTEGER", "INT": "INTEGER", "REAL": "FLOAT", "FLOAT": "FLOAT",
                "TEXT": "STRING", "BOOLEAN": "BOOLEAN", "BLOB": "BYTES"}
    
    bq_schema = []
    for name, stype in cols:
        bt = type_map.get(stype.upper() if stype else "STRING", "STRING")
        bq_schema.append(bigquery.SchemaField(name, bt, mode="NULLABLE"))
    
    # Drop existing table
    table_ref = f"{PROJECT}.{DATASET}.{table_name}"
    try:
        client.delete_table(table_ref, not_found_ok=True)
    except:
        pass
    
    # Create table
    table = bigquery.Table(table_ref, schema=bq_schema)
    client.create_table(table)
    log("  Created BQ table")
    
    # Write batches to JSON, upload each
    BATCH = 50000
    offset = 0
    total_uploaded = 0
    col_names = [c[0] for c in cols]
    
    while offset < row_count:
        try:
            rows = conn.execute(f'SELECT * FROM "{table_name}" LIMIT {BATCH} OFFSET {offset}').fetchall()
            if not rows:
                break
            
            # Write batch to temp JSON
            tmp = tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False, encoding='utf-8')
            for row in rows:
                d = {cn: row[cn] if row[cn] is not None else None for cn in col_names}
                tmp.write(json.dumps(d, default=str) + '\n')
            tmp.close()
            
            # Upload
            job_config = bigquery.LoadJobConfig(
                source_format=bigquery.SourceFormat.NEWLINE_DELIMITED_JSON,
                write_disposition=bigquery.WriteDisposition.WRITE_APPEND,
            )
            with open(tmp.name, 'rb') as f:
                job = client.load_table_from_file(f, table_ref, job_config=job_config)
            job.result(timeout=600)
            
            os.unlink(tmp.name)
            total_uploaded += len(rows)
            offset += BATCH
            pct = min(100, round(total_uploaded / row_count * 100))
            log(f"    {total_uploaded:,}/{row_count:,} ({pct}%)")
        except Exception as e:
            log(f"  ERROR at offset {offset}: {e}")
            traceback.print_exc()
            break
    
    log(f"  [OK] {total_uploaded:,} rows uploaded")

conn.close()
log("\nDone!")
