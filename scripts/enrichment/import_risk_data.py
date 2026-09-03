"""
IMPORT FEMA NRI — Lean version (~57 useful columns, not 469).

Usage: python scripts/enrichment/import_risk_data.py --fema
"""
import json, sqlite3, time, urllib.request, argparse
from pathlib import Path

PROJECT = Path(__file__).resolve().parent.parent.parent
DB_PATH = PROJECT / "churches.db"
FEMA_URL = "https://services.arcgis.com/XG15cJAlne2vxtgt/arcgis/rest/services/National_Risk_Index_Census_Tracts/FeatureServer/0"
TABLE = "fema_nri_tract"

# Only the columns we actually want — 57 lean columns
COLUMNS = [
    "TRACTFIPS","STCOFIPS","COUNTYFIPS","STATEFIPS","STATE","STATEABBRV",
    "COUNTY","COUNTYTYPE","TRACT","NRI_ID",
    "RISK_SCORE","RISK_RATNG","EAL_SCORE","EAL_RATNG",
    "SOVI_SCORE","SOVI_RATNG","RESL_SCORE","RESL_RATNG",
    "POPULATION","BUILDVALUE","AGRIVALUE",
    "AVLN_RISKS","CFLD_RISKS","CWAV_RISKS","DRGT_RISKS",
    "ERQK_RISKS","HAIL_RISKS","HWAV_RISKS","HRCN_RISKS",
    "ISTM_RISKS","LNDS_RISKS","LTNG_RISKS","IFLD_RISKS",
    "SWND_RISKS","TRND_RISKS","TSUN_RISKS","VLCN_RISKS",
    "WFIR_RISKS","WNTW_RISKS",
    "AVLN_RISKR","CFLD_RISKR","CWAV_RISKR","DRGT_RISKR",
    "ERQK_RISKR","HAIL_RISKR","HWAV_RISKR","HRCN_RISKR",
    "ISTM_RISKR","LNDS_RISKR","LTNG_RISKR","IFLD_RISKR",
    "SWND_RISKR","TRND_RISKR","TSUN_RISKR","VLCN_RISKR",
    "WFIR_RISKR","WNTW_RISKR",
]

def progress_bar(i, total, start, label=""):
    if total == 0: return
    elapsed = max(time.time() - start, 0.001)
    rate = (i + 1) / elapsed
    eta = (total - i - 1) / rate / 60 if rate > 0 else 0
    pct = (i + 1) / total * 100
    filled = int(30 * (i + 1) / total)
    bar = chr(0x2588) * filled + chr(0x2591) * (30 - filled)
    print(f"\r    {bar} {i+1:,}/{total:,} ({pct:.0f}%) {rate:.0f}/s ETA={eta:.0f}m {label}", end="", flush=True)

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--fema", action="store_true")
    p.add_argument("--all", action="store_true")
    args = p.parse_args()
    if not (args.fema or args.all): p.print_help(); return

    db = sqlite3.connect(str(DB_PATH), timeout=120)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA journal_mode=WAL")
    db.execute("PRAGMA synchronous=OFF")

    # Drop old fat table if it has 469 cols
    cur = db.execute(f"SELECT name FROM sqlite_master WHERE type='table' AND name='{TABLE}'")
    if cur.fetchone():
        cols = len(db.execute(f"PRAGMA table_info({TABLE})").fetchall())
        if cols > 400:
            print(f"Dropping old {TABLE} ({cols} cols) — re-importing lean ({len(COLUMNS)} cols)")
            db.execute(f"DROP TABLE {TABLE}"); db.commit()
        else:
            cnt = db.execute(f"SELECT COUNT(*) FROM {TABLE}").fetchone()[0]
            if cnt > 1000:
                print(f"{TABLE}: {cnt:,} rows × {cols} cols. Already lean. Done.")
                db.close(); return

    # Get count from ArcGIS
    print(f"Connecting to FEMA NRI v1.20...")
    url = f"{FEMA_URL}/query?where=1%3D1&returnCountOnly=true&f=json"
    req = urllib.request.Request(url, headers={"User-Agent": "GRID/1.0"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        total = json.loads(resp.read()).get("count", 0)
    print(f"{total:,} tracts — importing {len(COLUMNS)} columns")

    # Create lean table
    col_defs = []
    for c in COLUMNS:
        if c.endswith(("SCORE","VALUE","RATNG","RISKS","RISKR","POPULATION","BUILDVALUE","AGRIVALUE","AREA","_VALB","_VALP","_VALA","_VALT")):
            col_defs.append(f"{c} REAL")
        else:
            col_defs.append(f"{c} TEXT")
    db.execute(f"DROP TABLE IF EXISTS {TABLE}")
    db.execute(f"CREATE TABLE {TABLE} (id INTEGER PRIMARY KEY AUTOINCREMENT, {', '.join(col_defs)})")
    db.execute(f"CREATE INDEX IF NOT EXISTS idx_fema_tract ON {TABLE}(TRACTFIPS)")
    db.execute(f"CREATE INDEX IF NOT EXISTS idx_fema_county ON {TABLE}(COUNTYFIPS)")
    db.commit()

    # Paginate
    BATCH, inserted, failed, t0 = 1000, 0, 0, time.time()
    field_list = ",".join(COLUMNS)

    for offset in range(0, total, BATCH):
        url = (f"{FEMA_URL}/query?where=1%3D1&outFields={field_list}"
               f"&returnGeometry=false&resultOffset={offset}&resultRecordCount={BATCH}&f=json")

        data = None
        for attempt in range(5):
            try:
                req = urllib.request.Request(url, headers={"User-Agent": "GRID/1.0"})
                with urllib.request.urlopen(req, timeout=300) as resp:
                    data = json.loads(resp.read())
                break
            except Exception as e:
                if attempt == 4: failed += 1; data = {"features": []}
                else: time.sleep((attempt + 1) * 10)

        rows = [f["attributes"] for f in data.get("features", []) if f.get("attributes")]
        if rows:
            cols = ",".join(rows[0].keys())
            ph = ",".join([":" + c for c in rows[0].keys()])
            db.executemany(f"INSERT OR REPLACE INTO {TABLE} ({cols}) VALUES ({ph})", rows)
            db.commit(); inserted += len(rows)
        progress_bar(min(offset + BATCH, total), total, t0, f"{inserted:,}")

    print(f"\nDone: {inserted:,} rows × {len(COLUMNS)} cols ({failed} failed batches)")
    print(f"US churches joinable: {db.execute('SELECT COUNT(*) FROM churches WHERE country=\"US\" AND county_fips_5 IS NOT NULL').fetchone()[0]:,}")
    db.close()

if __name__ == "__main__":
    main()
