"""
Export ALL tables from churches.db to BigQuery.
Skips tables already in BQ with matching row counts.
ALL STRING schema — safe for SQLite dynamic typing (BLOB/TEXT in INTEGER cols).
Rowid-based pagination — O(1) per batch vs O(n²) for OFFSET.

Usage:
    python scripts/db_maintenance/bq_export_all.py
    python scripts/db_maintenance/bq_export_all.py --dry-run
    python scripts/db_maintenance/bq_export_all.py --force    # Re-export even if counts match
    python scripts/db_maintenance/bq_export_all.py --tables church_census_US,church_election_GB
"""
import os, sys, time, tempfile, argparse
from datetime import datetime, timezone
import sqlite3
import orjson
from google.cloud import bigquery

PROJECT = "american-rel-infra"
DATASET = "American_Religious_Infrastructure"
DB_PATH = r"E:\grid\churches.db"

# Tables to prioritize (exported first)
PRIORITY = [
    "churches", "church_enrichment", "church_contact_values",
    "church_external_ids", "church_sources", "church_metrics",
    "enrichment_change_log", "provenance_log",
]

def log(msg):
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)

def progress_bar(current, total, width=30):
    if total == 0:
        return f"[{'█'*width}] {current}"
    pct = current / total
    filled = int(width * pct)
    return f"[{'█'*filled}{'░'*(width-filled)}] {current}/{total} ({pct*100:.0f}%)"

def get_sqlite_tables():
    """Discover all user tables in SQLite with row counts."""
    conn = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)
    tables = []
    for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' "
        "AND name NOT LIKE 'sqlite_%' AND name NOT LIKE 'idx_%' "
        "AND name NOT LIKE '%_rtree%' ORDER BY name"
    ).fetchall():
        name = r[0]
        count = conn.execute(f"SELECT COUNT(*) FROM '{name}'").fetchone()[0]
        tables.append((name, count))
    conn.close()

    # Sort: priority first, then by row count desc (big tables first)
    result = []
    rest = []
    for name, count in tables:
        if name in PRIORITY:
            result.append((name, count))
        else:
            rest.append((name, count))
    rest.sort(key=lambda x: -x[1])  # biggest first
    result.extend(rest)
    return result

def get_bq_table_counts(client):
    """Get existing BQ table row counts."""
    counts = {}
    try:
        for t in client.list_tables(f"{PROJECT}.{DATASET}"):
            try:
                full = client.get_table(f"{PROJECT}.{DATASET}.{t.table_id}")
                counts[t.table_id] = full.num_rows
            except Exception:
                counts[t.table_id] = None
    except Exception as e:
        log(f"  ⚠ Could not list BQ tables: {e}")
    return counts

def export_table(client, table_name, row_count, dry_run=False):
    """Export one SQLite table to BQ with ALL STRING schema."""
    conn = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()

    cols = [r[1] for r in c.execute(f"PRAGMA table_info('{table_name}')").fetchall()]
    if not cols:
        conn.close()
        return "skip"

    log(f"  {row_count:,} rows, {len(cols)} cols")

    if row_count == 0:
        log(f"  ⚠ Empty, skipping")
        conn.close()
        return "skip"

    if dry_run:
        conn.close()
        return "ok"

    # ALL STRING schema — handles SQLite dynamic typing
    bq_schema = [bigquery.SchemaField(name, "STRING", mode="NULLABLE") for name in cols]
    table_ref = f"{PROJECT}.{DATASET}.{table_name}"

    # Drop and recreate
    try:
        client.delete_table(table_ref, not_found_ok=True)
        time.sleep(0.3)
    except Exception as e:
        log(f"  ⚠ Delete error: {e}")

    table = bigquery.Table(table_ref, schema=bq_schema)
    try:
        client.create_table(table)
    except Exception as e:
        log(f"  ❌ Create error: {e}")
        conn.close()
        return "fail"

    # Upload in batches with rowid pagination
    BATCH = 50000
    total_uploaded = 0
    last_rowid = 0
    t0 = time.time()

    while True:
        rows = c.execute(
            f'SELECT rowid, * FROM "{table_name}" WHERE rowid > ? ORDER BY rowid LIMIT {BATCH}',
            (last_rowid,)
        ).fetchall()
        if not rows:
            break

        last_rowid = rows[-1][0]  # First column is rowid (index 0, avoids duplicate key issue)

        # Write batch to temp NDJSON
        tmp = tempfile.NamedTemporaryFile(mode="wb", suffix=".json", delete=False)
        for row in rows:
            d = {}
            for cn in cols:
                v = row[cn]
                if v is None:
                    d[cn] = None
                elif isinstance(v, bytes):
                    d[cn] = v.hex()
                else:
                    d[cn] = str(v)
            tmp.write(orjson.dumps(d))
            tmp.write(b"\n")
        tmp.close()

        job_config = bigquery.LoadJobConfig(
            source_format=bigquery.SourceFormat.NEWLINE_DELIMITED_JSON,
            write_disposition=bigquery.WriteDisposition.WRITE_APPEND,
        )

        with open(tmp.name, "rb") as f:
            job = client.load_table_from_file(f, table_ref, job_config=job_config)

        os.unlink(tmp.name)

        try:
            job.result(timeout=180)
        except Exception as e:
            log(f"  ❌ Upload error @ rowid {last_rowid}: {str(e)[:300]}")
            conn.close()
            return "fail"

        total_uploaded += len(rows)
        print(f"    {progress_bar(total_uploaded, row_count)}", end="\r", flush=True)

    conn.close()
    elapsed = time.time() - t0
    rate = total_uploaded / elapsed if elapsed > 0 else 0
    print(f"    {progress_bar(total_uploaded, row_count)}  {elapsed:.0f}s ({rate:.0f} rec/s)")

    # Verify
    try:
        t = client.get_table(table_ref)
        bq_rows = t.num_rows
        if bq_rows == total_uploaded:
            log(f"  ✅ Verified: {bq_rows:,} rows")
        else:
            log(f"  ⚠ Mismatch: uploaded {total_uploaded:,}, BQ shows {bq_rows:,}")
    except Exception as e:
        log(f"  ⚠ Verify error: {e}")

    return "ok"

def main():
    parser = argparse.ArgumentParser(description="Export ALL churches.db tables to BigQuery")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be done")
    parser.add_argument("--force", action="store_true", help="Re-export even if BQ counts match")
    parser.add_argument("--tables", type=str, help="Comma-separated list of specific tables")
    args = parser.parse_args()

    log("BigQuery Full Export — ALL tables")
    log(f"Project: {PROJECT}.{DATASET}")
    log(f"Source: {DB_PATH}")

    # Discover tables
    sqlite_tables = get_sqlite_tables()
    log(f"SQLite tables: {len(sqlite_tables)}")

    # BQ client
    client = bigquery.Client(project=PROJECT)

    # Ensure dataset exists
    try:
        client.get_dataset(f"{PROJECT}.{DATASET}")
    except Exception:
        ds = bigquery.Dataset(f"{PROJECT}.{DATASET}")
        ds.location = "US"
        client.create_dataset(ds)
        log(f"Created dataset {DATASET}")

    # Get BQ table counts
    bq_counts = get_bq_table_counts(client)
    log(f"BQ tables: {len(bq_counts)}")

    # Filter to requested tables if specified
    if args.tables:
        requested = set(t.strip() for t in args.tables.split(","))
        sqlite_tables = [(n, c) for n, c in sqlite_tables if n in requested]
        log(f"Filtered to {len(sqlite_tables)} requested tables")

    # Determine which tables need export
    to_export = []
    skip_count = 0
    skip_rows = 0

    for name, sqlite_count in sqlite_tables:
        bq_count = bq_counts.get(name)
        if bq_count is not None and bq_count == sqlite_count and not args.force:
            skip_count += 1
            skip_rows += sqlite_count
        else:
            status = ""
            if bq_count is not None and bq_count != sqlite_count:
                status = f" [BQ has {bq_count:,}, re-exporting]"
            elif bq_count is None:
                status = " [new]"
            to_export.append((name, sqlite_count, status))

    log(f"\nTo export: {len(to_export)} tables")
    log(f"Already synced: {skip_count} tables ({skip_rows:,} rows)")
    if args.dry_run:
        log("DRY RUN — no changes will be made")
        for name, count, status in to_export[:30]:
            log(f"  {name}: {count:,}{status}")
        if len(to_export) > 30:
            log(f"  ... and {len(to_export)-30} more")
        return

    # Export
    start = time.time()
    ok, skip, fail = 0, 0, 0

    for i, (name, count, status) in enumerate(to_export):
        log(f"\n[{i+1}/{len(to_export)}] {name}{status}")
        try:
            result = export_table(client, name, count, dry_run=False)
            if result == "ok":
                ok += 1
            elif result == "skip":
                skip += 1
            else:
                fail += 1
        except Exception as e:
            log(f"  ❌ FAILED: {e}")
            import traceback; traceback.print_exc()
            fail += 1

    elapsed = time.time() - start
    log(f"\n{'='*60}")
    log(f"Export complete in {elapsed/60:.1f} min")
    log(f"  ✅ {ok} exported  ⏭ {skip} skipped  ❌ {fail} failed")
    log(f"  Already synced: {skip_count} tables ({skip_rows:,} rows)")
    log(f"  Dataset: {PROJECT}.{DATASET}")

if __name__ == "__main__":
    main()
