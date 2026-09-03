"""export_to_bigquery.py — Upload CSV chunks to BigQuery"""
import sys, os, csv, time, sqlite3, shutil, argparse, glob
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if PROJECT_ROOT not in sys.path: sys.path.insert(0, PROJECT_ROOT)
import google.auth
from google.cloud import bigquery
from tqdm import tqdm

CHURCHES_DB = r"E:\grid\churches.db"
PROJECT = "american-rel-infra"
DATASET = "American_Religious_Infrastructure"
LOCATION = "US"
CSV_DIR = r"E:\grid\data\bq_export"

def get_client():
    c, _ = google.auth.default()
    if hasattr(c,"with_quota_project"): c = c.with_quota_project(PROJECT)
    elif hasattr(c,"_quota_project_id"): c._quota_project_id = PROJECT
    return bigquery.Client(project=PROJECT, location=LOCATION, credentials=c)

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--tables", default="all")
    p.add_argument("--csv-dir", default=CSV_DIR)
    args = p.parse_args()

    bq = get_client()
    print(f"Connected: {PROJECT}.{DATASET} (location: {LOCATION})")

    # Find all chunk files grouped by table
    table_files = {}
    for fp in sorted(glob.glob(os.path.join(args.csv_dir, "*.csv"))):
        base = os.path.basename(fp)
        name = base.rsplit("_", 1)[0]
        table_files.setdefault(name, []).append(fp)

    names = list(table_files) if args.tables == "all" else [t.strip() for t in args.tables.split(",")]

    for name in names:
        files = table_files.get(name, [])
        if not files:
            print(f"  {name}: no files found, skip")
            continue

        tid = f"{PROJECT}.{DATASET}.{name}"
        print(f"\n  {name}: {len(files)} files")

        # Drop table if it already exists (partial from prior run)
        bq.delete_table(tid, not_found_ok=True)

        # First file: WRITE_TRUNCATE + autodetect (creates table schema)
        # Rest: WRITE_APPEND, NO autodetect (uses existing table schema)
        for i, fp in enumerate(tqdm(files, desc=f"    Upload {name}", unit="files")):
            cfg = bigquery.LoadJobConfig(
                source_format=bigquery.SourceFormat.CSV,
                skip_leading_rows=1, allow_quoted_newlines=True, max_bad_records=1000,
                write_disposition=(
                    bigquery.WriteDisposition.WRITE_TRUNCATE if i == 0
                    else bigquery.WriteDisposition.WRITE_APPEND
                ),
                autodetect=(i == 0),  # only autodetect for first file
            )
            with open(fp, "rb") as f:
                job = bq.load_table_from_file(f, tid, job_config=cfg)
                job.result(timeout=300)

        t = bq.get_table(tid)
        print(f"    ✓ {name}: {t.num_rows:,} rows ({len(t.schema)} cols)")

    print(f"\nDone.")

if __name__ == "__main__":
    main()
