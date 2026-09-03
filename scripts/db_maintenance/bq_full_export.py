"""
Full churches.db → BigQuery Export (BQ Native Migration)
Drops and recreates ALL key tables in BigQuery, then uploads from SQLite.
Uses WRITE_TRUNCATE on first batch, WRITE_APPEND on subsequent batches.
Verifies row counts after upload.

Usage:
    python scripts/db_maintenance/bq_full_export.py
    python scripts/db_maintenance/bq_full_export.py --dry-run
    python scripts/db_maintenance/bq_full_export.py --tables churches,church_enrichment
"""
import os, sys, json, time, tempfile, argparse
from datetime import datetime, timezone
import sqlite3
import orjson
from google.cloud import bigquery

PROJECT = "american-rel-infra"
DATASET = "American_Religious_Infrastructure"
DB_PATH = r"E:\grid\churches.db"

# All tables to export, in dependency order (reference tables first)
ALL_TABLES = [
    # Core
    "churches",
    # Enrichment & contacts
    "church_enrichment",
    "church_contact_values",
    "church_external_ids",
    "church_sources",
    "church_metrics",
    # Hierarchy tables
    "catholic_hierarchy",
    "anglican_hierarchy",
    "orthodox_hierarchy",
    "lutheran_hierarchy",
    "baptist_hierarchy",
    "lds_hierarchy",
    "jw_hierarchy",
    "chabad_hierarchy",
    "ahmadiyya_hierarchy",
    "bahai_hierarchy",
    "sa_hierarchy",
    "moravian_hierarchy",
    # Reference tables
    "mapping_saints",
    "rucc_codes",
    "county_acs",
    "arda_counts",
    "arda_counts_2010",
    "geonames_postal",
    "emergency_stations",
    # Election/Census enrichment
    "church_census_catalog",
    # Provenance
    "provenance_log",
    "enrichment_change_log",
]

TYPE_MAP = {
    "INTEGER": "INTEGER", "INT": "INTEGER", "BIGINT": "INTEGER",
    "SMALLINT": "INTEGER", "TINYINT": "INTEGER",
    "REAL": "FLOAT", "FLOAT": "FLOAT", "DOUBLE": "FLOAT",
    "NUMERIC": "FLOAT", "DECIMAL": "FLOAT",
    "BOOLEAN": "BOOLEAN", "BOOL": "BOOLEAN",
    "TEXT": "STRING", "VARCHAR": "STRING", "CHAR": "STRING",
    "BLOB": "BYTES",
}

def log(msg):
    print(f"[{datetime.now(timezone.utc).strftime('%H:%M:%S')}] {msg}", flush=True)


def progress_bar(current, total, width=30):
    if total == 0:
        return f"[{'█'*width}] {current}"
    pct = current / total
    filled = int(width * pct)
    return f"[{'█'*filled}{'░'*(width-filled)}] {current}/{total} ({pct*100:.0f}%)"


def export_table(client, table_name, dry_run=False):
    """Export a single SQLite table to BigQuery."""
    conn = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()

    # Check table exists in SQLite
    c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table_name,))
    if not c.fetchone():
        log(f"  ⚠ {table_name}: not found in SQLite, skipping")
        conn.close()
        return

    # Get schema
    cols = [(r[1], r[2]) for r in c.execute(f"PRAGMA table_info('{table_name}')").fetchall()]
    row_count = c.execute(f"SELECT COUNT(*) FROM '{table_name}'").fetchone()[0]
    log(f"  {table_name}: {row_count:,} rows, {len(cols)} cols")

    if row_count == 0:
        log(f"  ⚠ {table_name}: empty, skipping")
        conn.close()
        return

    if dry_run:
        conn.close()
        return

    # Build BQ schema
    bq_schema = []
    for col_name, col_type in cols:
        bt = TYPE_MAP.get(col_type.upper() if col_type else "STRING", "STRING")
        bq_schema.append(bigquery.SchemaField(col_name, bt, mode="NULLABLE"))

    table_ref = f"{PROJECT}.{DATASET}.{table_name}"

    # Drop and recreate
    try:
        client.delete_table(table_ref, not_found_ok=True)
        time.sleep(1)  # Let BQ propagate the delete
    except Exception as e:
        log(f"  ⚠ Delete error (non-fatal): {e}")

    table = bigquery.Table(table_ref, schema=bq_schema)
    client.create_table(table)
    log(f"  Created BQ table")

    # Upload in batches
    BATCH = 50000
    offset = 0
    total_uploaded = 0
    first_batch = True
    col_names = [c[0] for c in cols]

    while offset < row_count:
        rows = c.execute(f'SELECT * FROM "{table_name}" LIMIT {BATCH} OFFSET {offset}').fetchall()
        if not rows:
            break

        # Write batch to temp JSON (using orjson for speed)
        tmp_path = tempfile.mktemp(suffix=".json")
        with open(tmp_path, "wb") as f:
            for row in rows:
                d = {cn: row[cn] if row[cn] is not None else None for cn in col_names}
                f.write(orjson.dumps(d, default=str))
                f.write(b"\n")

        # Upload
        job_config = bigquery.LoadJobConfig(
            source_format=bigquery.SourceFormat.NEWLINE_DELIMITED_JSON,
            write_disposition=bigquery.WriteDisposition.WRITE_TRUNCATE if first_batch else bigquery.WriteDisposition.WRITE_APPEND,
            schema=bq_schema if first_batch else None,
        )
        first_batch = False

        with open(tmp_path, "rb") as f:
            job = client.load_table_from_file(f, table_ref, job_config=job_config)
        try:
            job.result(timeout=120)
        except Exception as e:
            log(f"  ❌ Upload error: {e}")
            os.unlink(tmp_path)
            conn.close()
            return

        os.unlink(tmp_path)
        offset += len(rows)
        total_uploaded += len(rows)
        pct = progress_bar(total_uploaded, row_count)
        print(f"    {pct}", end="\r", flush=True)

    conn.close()
    print(f"    {progress_bar(total_uploaded, row_count)}  ✅")

    # Verify
    try:
        t = client.get_table(table_ref)
        bq_rows = t.num_rows
        if bq_rows == total_uploaded:
            log(f"  ✅ Verified: {bq_rows:,} rows in BQ")
        else:
            log(f"  ⚠ Mismatch: uploaded {total_uploaded:,}, BQ shows {bq_rows:,}")
    except Exception as e:
        log(f"  ⚠ Verify error: {e}")


def main():
    parser = argparse.ArgumentParser(description="Full churches.db → BigQuery export")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be done")
    parser.add_argument("--tables", type=str, help="Comma-separated list of tables to export")
    args = parser.parse_args()

    tables = ALL_TABLES
    if args.tables:
        tables = [t.strip() for t in args.tables.split(",")]

    log(f"BigQuery Full Export — {len(tables)} tables")
    log(f"Project: {PROJECT}.{DATASET}")
    log(f"Source: {DB_PATH}")
    if args.dry_run:
        log("DRY RUN — no changes will be made")

    client = bigquery.Client(project=PROJECT)

    # Ensure dataset exists
    try:
        client.get_dataset(f"{PROJECT}.{DATASET}")
    except Exception:
        ds = bigquery.Dataset(f"{PROJECT}.{DATASET}")
        ds.location = "US"
        client.create_dataset(ds)
        log(f"Created dataset {DATASET}")

    start = time.time()
    success = 0
    fail = 0

    for i, table_name in enumerate(tables):
        log(f"\n[{i+1}/{len(tables)}] {table_name}")
        try:
            export_table(client, table_name, dry_run=args.dry_run)
            success += 1
        except Exception as e:
            log(f"  ❌ FAILED: {e}")
            fail += 1

    elapsed = time.time() - start
    log(f"\n{'='*60}")
    log(f"Export complete in {elapsed/60:.1f} min")
    log(f"  ✅ {success} tables exported")
    if fail:
        log(f"  ❌ {fail} tables failed")
    log(f"  Dataset: {PROJECT}.{DATASET}")


if __name__ == "__main__":
    main()
