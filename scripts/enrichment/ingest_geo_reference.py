"""
Geographic Reference Table Pipeline
====================================
Downloads and loads geographic enrichment datasets as standalone reference
tables. No church joins at import time — tables join on-demand via
church_districts, zip5, county_fips_5, etc.

Datasets: FEMA NRI, EPA EJScreen, CDC PLACES, Zillow ZHVI,
          Eviction Lab, Mapping Inequality, Opportunity Atlas, DOE LEAD

Usage:
  python scripts/enrichment/ingest_geo_reference.py          # all datasets
  python scripts/enrichment/ingest_geo_reference.py --dataset fema
"""
import csv, io, os, sqlite3, sys, time, urllib.request, zipfile, argparse
from datetime import datetime, timezone
from pathlib import Path

PROJECT = Path(__file__).resolve().parent.parent.parent
DATA_DIR = PROJECT / "data" / "geo_reference"
DATA_DIR.mkdir(parents=True, exist_ok=True)
DB_PATH = PROJECT / "churches.db"

# ═══════════════════════════════════════════════════════════════════════
DATASETS = {}

# ── FEMA National Risk Index ──────────────────────────────────────────
DATASETS["fema"] = {
    "name": "FEMA National Risk Index",
    "source": "fema_nri",
    "url": "https://nri-data-downloads.fema.gov/NationalRiskIndex/Tract/NRI_Table_Tracts.csv",
    "table": "fema_nri_tract",
    "key_col": "TRACTFIPS",
    "key_type": "tract_fips",
    "columns": {
        "TRACTFIPS": "tract_fips TEXT UNIQUE",
        "RISK_SCORE": "risk_score REAL",
        "RISK_RATNG": "risk_rating TEXT",
        "EAL_SCORE": "eal_score REAL",
        "SOVI_SCORE": "sovi_score REAL",
        "RESL_SCORE": "resl_score REAL",
        "POPULATION": "pop REAL",
        "BUILDVALUE": "building_value REAL",
        "AGRIVALUE": "agriculture_value REAL",
        # 18 hazard risk scores
        "AVLN_RISKS": "avalanche_score REAL", "CFLD_RISKS": "coastal_flood_score REAL",
        "CWAV_RISKS": "cold_wave_score REAL", "DRGT_RISKS": "drought_score REAL",
        "ERQK_RISKS": "earthquake_score REAL", "HAIL_RISKS": "hail_score REAL",
        "HWAV_RISKS": "heat_wave_score REAL", "HRCN_RISKS": "hurricane_score REAL",
        "ISTM_RISKS": "ice_storm_score REAL", "LNDS_RISKS": "landslide_score REAL",
        "LTNG_RISKS": "lightning_score REAL", "RFLD_RISKS": "river_flood_score REAL",
        "SWND_RISKS": "strong_wind_score REAL", "TRND_RISKS": "tornado_score REAL",
        "TSUN_RISKS": "tsunami_score REAL", "VLCN_RISKS": "volcano_score REAL",
        "WFIR_RISKS": "wildfire_score REAL", "WNTW_RISKS": "winter_weather_score REAL",
    },
}

# ── EPA EJScreen ──────────────────────────────────────────────────────
DATASETS["epa"] = {
    "name": "EPA EJScreen",
    "source": "epa_ejscreen",
    "url": "https://gaftp.epa.gov/EJSCREEN/2024/EJSCREEN_2024_StatePctile.csv.zip",
    "table": "epa_ejscreen",
    "key_col": "ID",
    "key_type": "bg_fips",
    "is_zip": True,
    "columns": {
        "ID": "bg_fips TEXT UNIQUE",
        "ACSTOTPOP": "total_pop REAL",
        "MINORPCT": "minority_pct REAL",
        "LOWINCPCT": "low_income_pct REAL",
        "LESSHSPCT": "less_hs_pct REAL",
        "LINGISOPCT": "linguistic_iso_pct REAL",
        "UNDER5PCT": "under_5_pct REAL",
        "OVER64PCT": "over_64_pct REAL",
        "PM25": "pm25_pctile REAL", "OZONE": "ozone_pctile REAL",
        "DSLPM": "diesel_pm_pctile REAL", "CANCER": "cancer_risk_pctile REAL",
        "RESP": "resp_hazard_pctile REAL", "PTRAF": "traffic_prox_pctile REAL",
        "PWDIS": "wastewater_pctile REAL", "PNPL": "superfund_pctile REAL",
        "PRMP": "rmp_facility_pctile REAL", "PTSDF": "tsdf_pctile REAL",
        "PRE1960PCT": "pre1960_housing_pct REAL", "LEADPAINT": "lead_paint_pctile REAL",
    },
}

# ── CDC PLACES ─────────────────────────────────────────────────────────
DATASETS["cdc"] = {
    "name": "CDC PLACES Health Outcomes",
    "source": "cdc_places",
    "url": "https://data.cdc.gov/api/views/cwsq-ngmh/rows.csv?accessType=DOWNLOAD",
    "table": "cdc_places_tract",
    "key_col": "LocationID",
    "key_type": "tract_fips",
    "key_transform": "strip_1400000US",
    "columns": {
        "LocationID": "tract_fips TEXT",
        "TotalPopulation": "total_pop REAL",
        "OBESITY_CrudePrev": "obesity_pct REAL",
        "DIABETES_CrudePrev": "diabetes_pct REAL",
        "BPHIGH_CrudePrev": "high_bp_pct REAL",
        "CHD_CrudePrev": "heart_disease_pct REAL",
        "STROKE_CrudePrev": "stroke_pct REAL",
        "ASTHMA_CrudePrev": "asthma_pct REAL",
        "COPD_CrudePrev": "copd_pct REAL",
        "CANCER_CrudePrev": "cancer_pct REAL",
        "MHLTH_CrudePrev": "mental_health_poor_days REAL",
        "PHLTH_CrudePrev": "physical_health_poor_days REAL",
        "CSMOKING_CrudePrev": "smoking_pct REAL",
        "SLEEP_CrudePrev": "sleep_insufficient_pct REAL",
        "LPA_CrudePrev": "no_leisure_activity_pct REAL",
        "CHECKUP_CrudePrev": "no_checkup_pct REAL",
        "DENTAL_CrudePrev": "no_dental_pct REAL",
        "ACCESS2_CrudePrev": "no_insurance_pct REAL",
    },
    "filter": "MeasureId = 'HLTHOUT' AND Data_Value_Unit = '%'",
}

# ── Zillow ZHVI ────────────────────────────────────────────────────────
DATASETS["zillow"] = {
    "name": "Zillow Home Value Index",
    "source": "zillow_zhvi",
    "url": "https://files.zillowstatic.com/research/public_csvs/zhvi/Zip_zhvi_uc_sfrcondo_tier_0.33_0.67_sm_sa_month.csv",
    "table": "zillow_zhvi_zip",
    "key_col": "RegionName",
    "key_type": "zipcode",
    "columns": {
        "RegionName": "zipcode TEXT UNIQUE",
        "City": "city TEXT",
        "State": "state TEXT",
        "Metro": "metro TEXT",
        "CountyName": "county TEXT",
        "SizeRank": "size_rank INTEGER",
        # Most recent date column will be dynamically selected
    },
    "date_column": True,
}

# ═══════════════════════════════════════════════════════════════════════

def progress_bar(i, total, start, label=""):
    if total == 0: return
    elapsed = time.time() - start
    rate = (i + 1) / elapsed if elapsed > 0 else 0
    eta = (total - i - 1) / rate / 60 if rate > 0 else 0
    pct = (i + 1) / total * 100
    filled = int(30 * (i + 1) / total)
    bar = chr(0x2588) * filled + chr(0x2591) * (30 - filled)
    print(f"\r    {bar} {i+1:,}/{total:,} ({pct:.0f}%) rate={rate:.0f}/s ETA={eta:.0f}m {label}", end="", flush=True)

def download(url, fname, is_zip=False, retries=3):
    path = DATA_DIR / fname
    if path.exists():
        return path

    print(f"    Downloading {fname} ...", end="", flush=True)
    req = urllib.request.Request(url, headers={"User-Agent": "GRID/1.0 (research)"})
    for attempt in range(retries):
        try:
            with urllib.request.urlopen(req, timeout=600) as resp:
                path.write_bytes(resp.read())
            size = path.stat().st_size
            print(f" {size/1e6:.0f}MB")
            if is_zip and size > 0:
                print(f"    Extracting ...", end="", flush=True)
                with zipfile.ZipFile(path, "r") as zf:
                    zf.extractall(DATA_DIR)
                # Return the first CSV found
                csv_path = next((DATA_DIR / f for f in zf.namelist() if f.endswith(".csv")), None)
                if csv_path and csv_path.exists():
                    print(f" -> {csv_path.name} ({csv_path.stat().st_size/1e6:.0f}MB)")
                    return csv_path
            return path
        except Exception as e:
            if attempt == retries - 1: raise
            print(f" retry {attempt+1}...", end="", flush=True)
            time.sleep(10)

def load_dataset(db, ds):
    """Download, create table, load data for one dataset."""
    name = ds["name"]
    url = ds["url"]
    table = ds["table"]
    key_col = ds["key_col"]
    is_zip = ds.get("is_zip", False)
    date_col = ds.get("date_column", False)

    print(f"\n  [{ds['source']}] {name}")

    # Check if already loaded
    cur = db.execute(f"SELECT name FROM sqlite_master WHERE type='table' AND name='{table}'")
    if cur.fetchone():
        cur = db.execute(f"SELECT COUNT(*) FROM {table}")
        existing = cur.fetchone()[0]
        if existing > 0:
            print(f"    Already loaded: {existing:,} rows. Skipping.")
            return existing

    # Download
    fname = url.split("/")[-1].split("?")[0]
    if is_zip:
        fname = fname
    path = download(url, fname, is_zip)

    # Parse CSV, inspect header
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        reader = csv.DictReader(f)
        header = reader.fieldnames
        sample = next(reader)

    # For date-column datasets (Zillow), find the most recent date column
    cols = dict(ds["columns"])
    date_cols = []
    if date_col:
        for h in header:
            if h.startswith("20") and len(h) >= 7:  # e.g., "2024-06-30"
                date_cols.append(h)
        if date_cols:
            latest = sorted(date_cols)[-1]
            cols[latest] = "zhvi REAL"

    # Build column mapping
    db_cols = []
    csv_cols_used = []
    has_unique = False
    for csv_name, db_def in cols.items():
        if csv_name in header:
            db_cols.append(db_def)
            csv_cols_used.append(csv_name)
            if "UNIQUE" in db_def.upper():
                has_unique = True

    # Create table
    db.execute(f"DROP TABLE IF EXISTS {table}")
    col_defs = ",\n            ".join(db_cols)
    col_defs += ",\n            loaded_at TEXT DEFAULT (datetime('now'))"
    db.execute(f"CREATE TABLE {table} ({col_defs})")
    if has_unique:
        pk_col = db_cols[0].split()[0]
        db.execute(f"CREATE INDEX IF NOT EXISTS idx_{table}_key ON {table}({pk_col})")
    db.commit()

    # Load data
    print(f"    Loading ...", end="", flush=True)
    # Re-read file
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        reader = csv.DictReader(f)
        batch = []
        total = 0
        start = time.time()

        placeholders = ",".join(["?"] * len(csv_cols_used))
        sql = f"INSERT OR IGNORE INTO {table} ({','.join(c.split()[0] for c in db_cols)}) VALUES ({placeholders})"

        for row in reader:
            vals = []
            for csv_name, db_def in zip(csv_cols_used, db_cols):
                val = row.get(csv_name, "")
                db_col_name = db_def.split()[0]
                # Numeric conversion
                if "REAL" in db_def.upper() or "INTEGER" in db_def.upper():
                    try:
                        val = float(val) if val and val.strip() else None
                    except:
                        val = None
                # Key transform
                if ds.get("key_transform") == "strip_1400000US" and csv_name == ds["key_col"]:
                    val = val.replace("1400000US", "") if val else val
                vals.append(val)

            if vals[0] and str(vals[0]).strip():
                batch.append(tuple(vals))
                total += 1

            if len(batch) >= 10000:
                db.executemany(sql, batch)
                db.commit()
                batch = []
                if total % 50000 == 0:
                    progress_bar(total - 1, total, start)

        if batch:
            db.executemany(sql, batch)
            db.commit()

    elapsed = time.time() - start
    cur = db.execute(f"SELECT COUNT(*) FROM {table}")
    final = cur.fetchone()[0]
    print(f"\r    Loaded: {final:,} rows ({elapsed:.0f}s)                     ")

    # Log provenance
    db.execute(
        "INSERT INTO provenance_log (source, script_name, started_at, completed_at, status, notes) VALUES (?,?,?,?,?,?)",
        (ds["source"], "ingest_geo_reference.py",
         datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
         datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
         "completed", f"Reference table. {final:,} rows, key={ds['key_type']}"))
    db.commit()
    return final

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", help="Single dataset to load (fema, epa, cdc, zillow)")
    args = parser.parse_args()

    if args.dataset:
        todo = {args.dataset: DATASETS[args.dataset]}
    else:
        todo = DATASETS

    print(f"\n{'='*60}")
    print(f"  Geographic Reference Table Pipeline — {len(todo)} datasets")
    print(f"{'='*60}")

    db = sqlite3.connect(str(DB_PATH))
    db.execute("PRAGMA journal_mode=WAL")
    db.execute("PRAGMA busy_timeout=30000")

    total_loaded = 0
    for key, ds in todo.items():
        try:
            n = load_dataset(db, ds)
            total_loaded += n
        except Exception as e:
            print(f"    FAILED: {type(e).__name__}: {e}")

    db.close()

    print(f"\n{'='*60}")
    print(f"  Pipeline complete. {total_loaded:,} total rows loaded.")
    print(f"  Join churches via church_districts or zip5/county_fips_5.")
    print(f"{'='*60}\n")

if __name__ == "__main__":
    main()
