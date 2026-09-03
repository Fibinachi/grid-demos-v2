"""
Deduplicate and upload GRID database to BigQuery.

Dedup strategy:
  1. For rows with non-NULL id: group by id, keep the row with most recent enrichment
  2. For rows with NULL id: group by (latitude, longitude), keep most enriched
  3. Enrichment recency = church_enrichment.last_updated > enrichment_change_log.changed_at
     > enrichment field count > church core field count

Usage:
    python _bq_upload_deduped.py
    python _bq_upload_deduped.py --dry-run
    python _bq_upload_deduped.py --batch-size 10000
    python _bq_upload_deduped.py --tables churches church_enrichment
"""

import os, sys, json, time, tempfile, argparse, textwrap
from datetime import datetime

# -- Configuration ----------------------------------------------------------
PROJECT_DIR = r"E:\grid"
MAIN_DB = os.path.join(PROJECT_DIR, "churches.db")
DATASET_ID = "American_Religious_Infrastructure"
PROJECT_ID = "american-rel-infra"
BATCH_SIZE = 5000

# Dedup ORDER BY clause — updated for modular schema (fewer columns in churches)
DEDUP_ORDER = """
    CASE WHEN e.last_updated IS NOT NULL THEN 1 ELSE 0 END DESC,
    e.last_updated DESC,
    CASE WHEN ecl.latest_change IS NOT NULL THEN 1 ELSE 0 END DESC,
    ecl.latest_change DESC,
    (CASE WHEN c.address IS NOT NULL AND c.address != '' THEN 1 ELSE 0 END +
     CASE WHEN c.city IS NOT NULL AND c.city != '' THEN 1 ELSE 0 END +
     CASE WHEN c.state IS NOT NULL AND c.state != '' THEN 1 ELSE 0 END +
     CASE WHEN c.name IS NOT NULL AND c.name != '' THEN 1 ELSE 0 END) DESC,
    c.source ASC
"""


def get_db():
    import sqlite3
    conn = sqlite3.connect(MAIN_DB)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=30000")
    # Use RAM aggressively — 32 GB machine
    conn.execute("PRAGMA cache_size = -8000000")   # 8 GB page cache
    conn.execute("PRAGMA mmap_size = 8589934592")   # 8 GB memory-mapped I/O
    conn.execute("PRAGMA temp_store = 2")            # MEMORY (use RAM for temp tables/sorting)
    conn.execute("PRAGMA synchronous = OFF")         # Speed over crash safety (upload is idempotent)
    return conn


def get_bq_client():
    from google.cloud import bigquery
    return bigquery.Client(project=PROJECT_ID)


def map_sqlite_type_to_bq(sqlite_type):
    t = sqlite_type.upper() if sqlite_type else "STRING"
    mapping = {
        "INTEGER": "INTEGER", "INT": "INTEGER", "BIGINT": "INTEGER",
        "SMALLINT": "INTEGER", "TINYINT": "INTEGER",
        "REAL": "FLOAT", "FLOAT": "FLOAT", "DOUBLE": "FLOAT",
        "NUMERIC": "FLOAT", "DECIMAL": "FLOAT",
        "BOOLEAN": "BOOLEAN", "BOOL": "BOOLEAN",
        "TEXT": "STRING", "VARCHAR": "STRING", "CHAR": "STRING",
        "BLOB": "BYTES", "DATE": "DATE", "DATETIME": "TIMESTAMP",
        "TIMESTAMP": "TIMESTAMP",
    }
    return mapping.get(t, "STRING")


def clean_name(name):
    return name.replace("-", "_").replace(".", "_").replace(" ", "_").lower()


def get_deduped_count(conn):
    """Count rows after dedup."""
    sql = f"""
    SELECT COUNT(*) as cnt FROM (
        SELECT c.id,
            ROW_NUMBER() OVER (
                PARTITION BY
                    CASE WHEN c.id IS NOT NULL THEN c.id ELSE NULL END,
                    CASE WHEN c.id IS NULL THEN c.latitude ELSE NULL END,
                    CASE WHEN c.id IS NULL THEN c.longitude ELSE NULL END
                ORDER BY {DEDUP_ORDER}
            ) as _rn
        FROM churches c
        LEFT JOIN church_enrichment e ON c.id = e.church_id
        LEFT JOIN (
            SELECT church_id, MAX(changed_at) as latest_change
            FROM enrichment_change_log GROUP BY church_id
        ) ecl ON c.id = ecl.church_id
    ) WHERE _rn = 1
    """
    return conn.execute(sql).fetchone()["cnt"]


def create_deduped_temp_table(conn):
    """Create an in-memory temp table with deduplicated rows (window fn runs ONCE)."""
    import time
    print("    Building deduped temp table (in-memory, 8 GB cache)...")
    t0 = time.time()

    conn.execute("DROP TABLE IF EXISTS temp._bq_deduped")
    
    sql = f"""
    CREATE TEMP TABLE _bq_deduped AS
    SELECT *
    FROM (
        SELECT c.*,
            ROW_NUMBER() OVER (
                PARTITION BY
                    CASE WHEN c.id IS NOT NULL THEN c.id ELSE NULL END,
                    CASE WHEN c.id IS NULL THEN c.latitude ELSE NULL END,
                    CASE WHEN c.id IS NULL THEN c.longitude ELSE NULL END
                ORDER BY {DEDUP_ORDER}
            ) as _rn
        FROM churches c
        LEFT JOIN church_enrichment e ON c.id = e.church_id
        LEFT JOIN (
            SELECT church_id, MAX(changed_at) as latest_change
            FROM enrichment_change_log GROUP BY church_id
        ) ecl ON c.id = ecl.church_id
    ) WHERE _rn = 1
    """
    conn.execute(sql)
    
    cnt = conn.execute("SELECT COUNT(*) FROM temp._bq_deduped").fetchone()[0]
    elapsed = time.time() - t0
    print(f"    Temp table ready: {cnt:,} rows in {elapsed:.0f}s")
    return cnt


def yield_deduped_batches(conn, columns, batch_size=BATCH_SIZE):
    """Yield batches from the pre-built temp._bq_deduped table (fast — no re-sort)."""
    col_names = [c[0] for c in columns]
    offset = 0
    while True:
        rows = conn.execute(
            f"SELECT * FROM temp._bq_deduped LIMIT {batch_size} OFFSET {offset}"
        ).fetchall()
        if not rows:
            break
        batch = []
        for row in rows:
            d = {}
            for cn in col_names:
                val = row[cn]
                d[cn] = val if val is not None else None
            batch.append(d)
        yield batch
        offset += batch_size


def yield_all_batches(conn, table_name, columns, batch_size=BATCH_SIZE):
    """Yield batches of ALL rows from a non-churches table."""
    col_names = [c[0] for c in columns]
    offset = 0
    while True:
        rows = conn.execute(
            f'SELECT * FROM "{table_name}" LIMIT {batch_size} OFFSET {offset}'
        ).fetchall()
        if not rows:
            break
        batch = []
        for row in rows:
            d = {}
            for cn in col_names:
                val = row[cn]
                d[cn] = val if val is not None else None
            batch.append(d)
        yield batch
        offset += batch_size


# -- BigQuery ---------------------------------------------------------------

def table_exists(client, table_ref):
    from google.api_core import exceptions as google_exceptions
    try:
        client.get_table(table_ref)
        return True
    except google_exceptions.NotFound:
        return False


def get_bq_row_count(client, table_name):
    try:
        r = client.query(
            f"SELECT COUNT(*) as cnt FROM `{PROJECT_ID}.{DATASET_ID}.{table_name}`"
        ).result()
        return list(r)[0].cnt
    except Exception:
        return None


def load_json_batch(client, bq_table_id, json_rows, first_batch=False):
    """Load batch of JSON rows into BigQuery via temp file."""
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".json", delete=False, encoding="utf-8"
    ) as f:
        for r in json_rows:
            f.write(json.dumps(r, default=str) + "\n")
        tmp_path = f.name
    try:
        from google.cloud import bigquery
        disposition = (bigquery.WriteDisposition.WRITE_TRUNCATE if first_batch
                       else bigquery.WriteDisposition.WRITE_APPEND)
        job_config = bigquery.LoadJobConfig(
            write_disposition=disposition,
            source_format=bigquery.SourceFormat.NEWLINE_DELIMITED_JSON,
        )
        with open(tmp_path, "rb") as f:
            job = client.load_table_from_file(f, bq_table_id, job_config=job_config)
        job.result(timeout=600)
        return True
    except Exception as e:
        print(f"\n    Load failed: {e}")
        return False
    finally:
        try:
            os.unlink(tmp_path)
        except Exception:
            pass


def create_dataset(client):
    from google.cloud import bigquery
    dataset_ref = bigquery.DatasetReference(PROJECT_ID, DATASET_ID)
    try:
        client.get_dataset(dataset_ref)
        print(f"  Dataset '{DATASET_ID}' already exists")
    except Exception:
        dataset = bigquery.Dataset(dataset_ref)
        dataset.location = "US"
        dataset.description = "GRID - Global Religious Infrastructure Database"
        client.create_dataset(dataset)
        print(f"  Created dataset '{DATASET_ID}'")


def upload_table(client, conn, table_name, dry_run=False):
    """Upload a table. For 'churches', applies enrichment-based dedup via temp table."""
    from google.cloud import bigquery

    row_count = conn.execute(
        f"SELECT COUNT(*) as cnt FROM \"{table_name}\""
    ).fetchone()["cnt"]
    columns = [(r[1], r[2]) for r in conn.execute(
        f"PRAGMA table_info(\"{table_name}\")"
    ).fetchall()]

    if table_name == "churches":
        # Build temp table once (window function runs ONCE, not re-executed per batch)
        deduped_count = create_deduped_temp_table(conn)
        removed = row_count - deduped_count
        print(f"    Dedup: {row_count:,} raw -> {deduped_count:,} ({removed:,} removed, {removed/row_count*100:.1f}%)")
        upload_count = deduped_count
    else:
        print(f"\n  {table_name}: {row_count:,} rows, {len(columns)} cols")
        upload_count = row_count

    if dry_run:
        if table_name == "churches":
            conn.execute("DROP TABLE IF EXISTS temp._bq_deduped")
        return upload_count

    bq_table_id = f"{PROJECT_ID}.{DATASET_ID}.{table_name}"

    schema = [
        bigquery.SchemaField(clean_name(cn), map_sqlite_type_to_bq(ct), mode="NULLABLE")
        for cn, ct in columns
    ]
    table_ref = bigquery.Table(bq_table_id, schema=schema)

    if not table_exists(client, table_ref):
        client.create_table(table_ref)
        print(f"    Created BigQuery table")
    else:
        print(f"    Overwriting existing table")

    batches = (yield_deduped_batches(conn, columns, BATCH_SIZE) if table_name == "churches"
               else yield_all_batches(conn, table_name, columns, BATCH_SIZE))

    # Write all rows to a single temp JSON file, then upload once
    tmp_path = os.path.join(tempfile.gettempdir(), f"bq_upload_{table_name}_{int(time.time())}.json")
    print(f"    Writing JSON to {tmp_path}...")
    total_written = 0
    with open(tmp_path, "w", encoding="utf-8") as f:
        for batch in batches:
            for row in batch:
                cleaned = {clean_name(k): v for k, v in row.items()}
                f.write(json.dumps(cleaned, default=str) + "\n")
                total_written += 1
            pct = min(100, round(total_written / upload_count * 100))
            print(f"    Writing: {total_written:,}/{upload_count:,} ({pct}%)", end="\r")
    print(f"\n    Wrote {total_written:,} rows ({os.path.getsize(tmp_path)/1024/1024:.0f} MB)")

    # Upload single file
    print(f"    Uploading to BigQuery...")
    job_config = bigquery.LoadJobConfig(
        write_disposition=bigquery.WriteDisposition.WRITE_TRUNCATE,
        source_format=bigquery.SourceFormat.NEWLINE_DELIMITED_JSON,
    )
    with open(tmp_path, "rb") as f:
        job = client.load_table_from_file(f, bq_table_id, job_config=job_config)
    try:
        job.result(timeout=900)
        print(f"    Uploaded {total_written:,} rows to {table_name}")
    except Exception as e:
        print(f"\n    Upload failed: {e}")
        total_written = 0
    finally:
        try:
            os.unlink(tmp_path)
        except Exception:
            pass

    # Clean up temp table
    if table_name == "churches":
        conn.execute("DROP TABLE IF EXISTS temp._bq_deduped")

    return total_written


def create_views(client):
    """Create BigQuery analytics views."""
    print(f"\n{'='*60}")
    print("  Creating analytics views")
    print(f"{'='*60}")

    views = {
        "church_deduped": f"""
            CREATE OR REPLACE VIEW `{PROJECT_ID}.{DATASET_ID}.church_deduped` AS
            SELECT id, name, denomination, family, faith_tradition,
                address, city, state, zip, country,
                latitude, longitude, fips AS county_fips,
                source,
                ein, ntee_code,
                mosque_type, canonical_status,
                is_landmark, heritage_status, landmark_type,
                building_year, capacity,
                osm_id, osm_type, wikidata_qid, overture_id
            FROM `{PROJECT_ID}.{DATASET_ID}.churches`
        """,
        "denomination_summary": f"""
            CREATE OR REPLACE VIEW `{PROJECT_ID}.{DATASET_ID}.denomination_summary` AS
            SELECT
                COALESCE(faith_tradition, denomination, 'Unknown') AS tradition,
                denomination,
                COUNT(*) AS church_count,
                COUNT(DISTINCT country) AS countries_present,
                COUNT(DISTINCT state) AS states_present,
                COUNTIF(is_landmark = 1) AS landmark_count
            FROM `{PROJECT_ID}.{DATASET_ID}.churches`
            GROUP BY 1, 2 ORDER BY 3 DESC
        """,
        "country_summary": f"""
            CREATE OR REPLACE VIEW `{PROJECT_ID}.{DATASET_ID}.country_summary` AS
            SELECT country, COUNT(*) AS church_count,
                COUNT(DISTINCT denomination) AS denominations,
                COUNT(DISTINCT faith_tradition) AS traditions
            FROM `{PROJECT_ID}.{DATASET_ID}.churches`
            GROUP BY country ORDER BY 2 DESC
        """,
    }

    for view_name, view_sql in views.items():
        try:
            client.query(view_sql).result()
            print(f"  Created view: {view_name}")
        except Exception as e:
            print(f"  Failed {view_name}: {e}")


# -- Main -------------------------------------------------------------------

def main():
    global BATCH_SIZE
    
    parser = argparse.ArgumentParser(description="Dedup + Upload GRID to BigQuery")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--batch-size", type=int, default=BATCH_SIZE)
    parser.add_argument("--tables", nargs="*",
                        help="Tables to upload (default: churches)")
    parser.add_argument("--no-views", action="store_true")
    args = parser.parse_args()

    BATCH_SIZE = args.batch_size

    start_time = time.time()
    print(f"{'='*60}")
    print(f"  GRID -> BigQuery: Enrichment-based Dedup + Upload")
    print(f"  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"  Batch size: {BATCH_SIZE:,}")
    print(f"{'='*60}")

    conn = get_db()
    tables_to_upload = args.tables if args.tables else ["churches"]

    # Show raw count
    if "churches" in tables_to_upload:
        raw = conn.execute("SELECT COUNT(*) as cnt FROM churches").fetchone()["cnt"]
        print(f"\n  Raw churches: {raw:,} rows (dedup happens during upload)")

    if args.dry_run:
        print("\n  [DRY RUN] No data uploaded. Run without --dry-run to upload.")
        conn.close()
        return

    # Upload
    client = get_bq_client()
    create_dataset(client)

    total_uploaded = 0
    for table_name in tables_to_upload:
        uploaded = upload_table(client, conn, table_name, dry_run=False)
        total_uploaded += uploaded

    conn.close()

    if not args.no_views:
        create_views(client)

    elapsed = time.time() - start_time
    print(f"\n{'='*60}")
    print(f"  UPLOAD COMPLETE in {elapsed/60:.1f} min")
    print(f"  Project: {PROJECT_ID} / Dataset: {DATASET_ID}")
    print(f"  Total: {total_uploaded:,} rows")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
