"""export_to_bigquery.py - Export churches.db to BigQuery"""
import sys, os, csv, time, sqlite3, shutil, argparse
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
ROWS_PER_FILE = 50000
TABLES = {
    # Core data
    "churches":{}, "provenance_log":{}, "church_sources":{},
    "sources":{}, "church_enrichment":{}, "church_contact_values":{},
    # Hierarchy tables
    "lds_hierarchy":{}, "lutheran_hierarchy":{}, "jw_hierarchy":{},
    "sa_hierarchy":{}, "chabad_hierarchy":{}, "moravian_hierarchy":{},
    "baptist_hierarchy":{}, "catholic_hierarchy":{}, "ahmadiyya_hierarchy":{},
    # Reference tables
    "rucc_codes":{}, "county_census_us":{}, "fcc_facilities":{},
    "taxonomy":{}, "county_fips_lookup":{},
}
BQ_TYPE_MAP = {"TEXT":"STRING","INT":"INT64","INTEGER":"INT64",
               "REAL":"FLOAT64","FLOAT":"FLOAT64","BLOB":"BYTES"}

def get_client():
    c, _ = google.auth.default()
    if hasattr(c,"with_quota_project"): c = c.with_quota_project(PROJECT)
    elif hasattr(c,"_quota_project_id"): c._quota_project_id = PROJECT
    return bigquery.Client(project=PROJECT, location=LOCATION, credentials=c)

def build_schema(conn, table_name):
    c = conn.cursor(); c.execute(f"PRAGMA table_info({table_name})")
    schema = []
    for col in c.fetchall():
        name, ctype = col[1], col[2]; bq_type = "STRING"
        for k, v in BQ_TYPE_MAP.items():
            if ctype.upper().startswith(k): bq_type = v; break
        schema.append(bigquery.SchemaField(name, bq_type, "NULLABLE"))
    return schema

def export_table(conn, name, export_dir):
    c = conn.cursor()
    c.execute(f"PRAGMA table_info({name})"); cols = [r[1] for r in c.fetchall()]
    c.execute(f"SELECT COUNT(*) FROM {name}"); total = c.fetchone()[0]
    if total == 0: print(f"  {name}: 0 rows"); return []
    c.execute(f"SELECT MIN(rowid), MAX(rowid) FROM {name}")
    min_r, max_r = c.fetchone(); rng = max_r - min_r + 1
    n_files = max(1, total // ROWS_PER_FILE); chunk = max(1, rng // n_files)
    print(f"  {name}: {total:,} rows, {len(cols)} cols ({n_files} files)")
    files = []; lo = min_r
    with tqdm(total=total, desc=f"    Export {name}", unit="rows") as pbar:
        while lo <= max_r:
            hi = lo + chunk
            c.execute(f"SELECT * FROM {name} WHERE rowid BETWEEN ? AND ? ORDER BY rowid", (lo, hi))
            rows = c.fetchall()
            if rows:
                fn = os.path.join(export_dir, f"{name}_{len(files):04d}.csv")
                with open(fn,"w",encoding="utf-8",newline="") as f:
                    w = csv.writer(f, quoting=csv.QUOTE_ALL); w.writerow(cols); w.writerows(rows)
                files.append(fn); pbar.update(len(rows))
            lo = hi + 1
    return files

def upload_table(bq, name, files, schema=None):
    tid = f"{PROJECT}.{DATASET}.{name}"
    print(f"    Upload {len(files)} files...")
    cfg = bigquery.LoadJobConfig(
        source_format=bigquery.SourceFormat.CSV,
        write_disposition=bigquery.WriteDisposition.WRITE_TRUNCATE,
        skip_leading_rows=1, allow_quoted_newlines=True, max_bad_records=1000)
    if schema: cfg.schema = schema; cfg.autodetect = False
    else: cfg.autodetect = True
    total = 0
    for i, fp in enumerate(tqdm(files, desc="    Upload", unit="files")):
        is_first = (i == 0)
        with open(fp,"rb") as f:
            cfg.write_disposition = bigquery.WriteDisposition.WRITE_TRUNCATE if is_first else bigquery.WriteDisposition.WRITE_APPEND
            job = bq.load_table_from_file(f, tid, job_config=cfg); job.result(timeout=300)
            total += job.output_rows or 0
    t = bq.get_table(tid)
    print(f"    ✓ {name}: {t.num_rows:,} rows ({len(t.schema)} cols)")

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--tables",default="all"); p.add_argument("--keep-csv",action="store_true")
    args = p.parse_args(); t0 = time.time()
    names = list(TABLES) if args.tables=="all" else [t.strip() for t in args.tables.split(",")]
    if os.path.exists(CSV_DIR): shutil.rmtree(CSV_DIR)
    os.makedirs(CSV_DIR)
    conn = sqlite3.connect(CHURCHES_DB); conn.execute("PRAGMA journal_mode=WAL")
    bq = get_client()
    print(f"Connected: {PROJECT}.{DATASET} (location: {LOCATION})")
    for n in names:
        if n not in TABLES: print(f"  Unknown: {n}"); continue
        f = export_table(conn, n, CSV_DIR)
        if f:
            schema = build_schema(conn, n)  # explicit schema for all tables
            upload_table(bq, n, f, schema)
    conn.close()
    if not args.keep_csv: shutil.rmtree(CSV_DIR)
    print(f"Done in {time.time()-t0:.0f}s")

if __name__=="__main__": main()
