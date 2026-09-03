"""
ACS Enrichment: fetch data, update local DB, re-upload churches to BQ.
"""
import sqlite3, os, sys, json, urllib.request, time, csv, tempfile
from datetime import datetime
from google.cloud import bigquery

PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DB_PATH = os.path.join(PROJECT_DIR, "churches.db")
KEY = "2159d6ade3d596371c9333d6118d1ef2f9342cf4"

S_VARS = "S1901_C01_012E,S1901_C01_013E,S1501_C01_006E,S1501_C01_007E,S1501_C01_005E,S0101_C01_001E,S0101_C02_001E,S0101_C01_022E,S0101_C01_006E,S0101_C01_014E,S1701_C01_001E,S1701_C02_001E,S2501_C01_001E,S2502_C01_001E,S2502_C01_002E,S2501_C01_008E,S2301_C01_001E,S2301_C02_001E,S2301_C03_001E,S2301_C04_001E,S1101_C02_001E,S1101_C03_001E,S1101_C04_001E,S1101_C05_001E,S0101_C01_002E,S0101_C01_003E,S2201_C01_001E,S2201_C02_001E,S2701_C01_001E,S2701_C02_001E"
D_VARS = "B02001_001E,B02001_002E,B02001_003E,B02001_004E,B02001_005E,B02001_006E,B02001_007E,B02001_008E,B03003_001E,B03003_003E"
S_NAMES = "median_hh_income,mean_hh_income,pct_bachelors,pct_graduate,pct_some_college,total_pop,median_age,pct_65plus,pct_18_34,pct_35_54,poverty_total,poverty_count,total_housing,owner_pct,renter_pct,vacancy_pct,emp_total_16plus,labor_force_pct,employed_pct,unemployed_pct,hh_total,avg_hh_size,married_pct,male_hh_pct,female_hh_pct,single_parent_pct,male_pop,female_pop,snap_total,snap_pct,ins_total,insured_pct"
D_NAMES = "race_total,white_pop,black_pop,native_pop,asian_pop,pac_islander_pop,other_race_pop,two_plus_race_pop,hisp_total,hisp_pop"
ALL_NAMES = S_NAMES + "," + D_NAMES + ",white_pct,black_pct,asian_pct,native_pct,pac_islander_pct,two_plus_race_pct,hisp_pct,poverty_rate"
names_list = ALL_NAMES.split(",")

def fetch_census():
    """Download all ACS ZCTA data. Returns {zip5: {col: val}}."""
    all_data = {}
    
    # Subject data
    url = f"https://api.census.gov/data/2022/acs/acs5/subject?get=NAME,{S_VARS}&for=zip+code+tabulation+area:*&key={KEY}"
    req = urllib.request.Request(url)
    with urllib.request.urlopen(req, timeout=120) as resp:
        raw = json.loads(resp.read().decode())
    hdr = raw[0]; zc = hdr.index("zip code tabulation area")
    s_vars_list = S_VARS.split(","); s_names_list = S_NAMES.split(",")
    for row in raw[1:]:
        z = row[zc]; all_data.setdefault(z, {})
        for v, n in zip(s_vars_list, s_names_list):
            idx = hdr.index(v)
            val = row[idx] if idx < len(row) else None
            if val and val not in ("null","*********"):
                try: all_data[z][n] = float(val.replace(",",""))
                except: pass
    print(f"  Subject: {len(raw)-1:,} ZIPS")
    
    # Detail data
    url = f"https://api.census.gov/data/2022/acs/acs5?get=NAME,{D_VARS}&for=zip+code+tabulation+area:*&key={KEY}"
    req = urllib.request.Request(url)
    with urllib.request.urlopen(req, timeout=120) as resp:
        raw = json.loads(resp.read().decode())
    hdr = raw[0]; zc = hdr.index("zip code tabulation area")
    d_vars_list = D_VARS.split(","); d_names_list = D_NAMES.split(",")
    for row in raw[1:]:
        z = row[zc]; all_data.setdefault(z, {})
        for v, n in zip(d_vars_list, d_names_list):
            idx = hdr.index(v)
            val = row[idx] if idx < len(row) else None
            if val and val not in ("null","*********"):
                try: all_data[z][n] = float(val.replace(",",""))
                except: pass
    
    # Derive percentages
    pop_cols = ["white_pop","black_pop","asian_pop","native_pop","pac_islander_pop","two_plus_race_pop"]
    for z, vals in all_data.items():
        pop = vals.get("total_pop", 0) or 0
        if pop > 0:
            for pc in pop_cols:
                v = vals.get(pc, 0) or 0
                vals[pc.replace("_pop","_pct")] = round(v / pop * 100, 1) if pop else 0
            vals["hisp_pct"] = round((vals.get("hisp_pop",0) or 0) / pop * 100, 1)
            vals["poverty_rate"] = round((vals.get("poverty_count",0) or 0) / pop * 100, 1)
    
    print(f"  Detail: {len(raw)-1:,} ZIPS")
    return all_data

def update_local_db(zip_data):
    """Write ACS data to local SQLite churches table."""
    print("Updating local DB...", end=" ", flush=True)
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    
    # Add columns
    for col in names_list:
        try: cur.execute(f"ALTER TABLE churches ADD COLUMN census_{col} TEXT DEFAULT ''")
        except: pass
    conn.commit()
    
    # Create temp table with CSV
    csv_path = os.path.join(PROJECT_DIR, "data", "_acs_import.csv")
    with open(csv_path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["zip5"] + names_list)
        for z in sorted(zip_data.keys()):
            vals = zip_data[z]
            row = [z] + [str(vals.get(n, "")) for n in names_list]
            w.writerow(row)
    
    cur.execute("DROP TABLE IF EXISTS _acs_temp")
    cols_def = ",".join([f"census_{c} TEXT" for c in names_list])
    cur.execute(f"CREATE TABLE _acs_temp (zip5 TEXT, {cols_def})")
    
    # Import CSV
    with open(csv_path, "r") as f:
        reader = csv.reader(f)
        next(reader)
        rows = list(reader)
    cur.execute("BEGIN")
    placeholders = ",".join(["?"] * (len(names_list) + 1))
    cur.executemany(f"INSERT INTO _acs_temp VALUES ({placeholders})", rows)
    cur.execute("CREATE INDEX idx_acs_z ON _acs_temp(zip5)")
    conn.commit()
    
    # Mass UPDATE - one column at a time
    for col in names_list:
        cur.execute(f"""
            UPDATE churches SET census_{col} = (
                SELECT census_{col} FROM _acs_temp WHERE _acs_temp.zip5 = substr(churches.zip, 1, 5)
            )
            WHERE EXISTS (
                SELECT 1 FROM _acs_temp WHERE _acs_temp.zip5 = substr(churches.zip, 1, 5)
            )
        """)
    conn.commit()
    
    cur.execute("DROP TABLE _acs_temp")
    conn.commit()
    os.unlink(csv_path)
    
    # Verify
    cur.execute("SELECT COUNT(*) FROM churches WHERE census_median_hh_income IS NOT NULL AND census_median_hh_income != ''")
    cnt = cur.fetchone()[0]
    print(f"{cnt:,} rows")
    conn.close()
    return cnt

def push_to_bq():
    """Push census data to BQ via temp table + MERGE (safe, no replace)."""
    print("Pushing to BigQuery...")
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    
    # Export only census columns to JSONL
    census_cols = [f"census_{c}" for c in names_list]
    all_cols = ["id"] + census_cols
    
    cur.execute(f"SELECT {','.join(all_cols)} FROM churches ORDER BY id")
    rows = cur.fetchall()
    conn.close()
    
    with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False, encoding="utf-8") as f:
        for row in rows:
            jr = {"id": row[0]}
            for i, c in enumerate(census_cols):
                v = row[i+1]
                if v is not None and v != "":
                    jr[c] = str(v)
            f.write(json.dumps(jr, default=str) + "\n")
        tmp = f.name
    
    client = bigquery.Client(project="american-rel-infra")
    tmp_table = "_census_update"
    client.delete_table(f"american-rel-infra.American_Religious_Infrastructure.{tmp_table}", not_found_ok=True)
    
    schema = [bigquery.SchemaField("id", "INTEGER")]
    for c in census_cols:
        schema.append(bigquery.SchemaField(c, "STRING"))
    client.create_table(bigquery.Table(f"american-rel-infra.American_Religious_Infrastructure.{tmp_table}", schema=schema))
    
    print(f"  Loading {len(rows):,} rows to temp table...", end=" ", flush=True)
    with open(tmp, "rb") as f:
        client.load_table_from_file(f, f"american-rel-infra.American_Religious_Infrastructure.{tmp_table}",
            job_config=bigquery.LoadJobConfig(
                write_disposition=bigquery.WriteDisposition.WRITE_APPEND,
                source_format=bigquery.SourceFormat.NEWLINE_DELIMITED_JSON,
                max_bad_records=100000)).result()
    print("done")
    
    # MERGE - do one column at a time with SAFE_CAST to handle type mismatches
    print("  Running MERGE per column...")
    for c in census_cols:
        sql = f"""
            UPDATE `american-rel-infra.American_Religious_Infrastructure.churches` t
            SET t.{c} = s.{c}
            FROM `american-rel-infra.American_Religious_Infrastructure.{tmp_table}` s
            WHERE t.id = s.id AND s.{c} IS NOT NULL
        """
        try:
            client.query(sql).result()
        except Exception:
            # Try STRING -> INT64 -> FLOAT64 conversion chain
            sql = f"""
                UPDATE `american-rel-infra.American_Religious_Infrastructure.churches` t
                SET t.{c} = CAST(SAFE_CAST(s.{c} AS FLOAT64) AS INT64)
                FROM `american-rel-infra.American_Religious_Infrastructure.{tmp_table}` s
                WHERE t.id = s.id AND s.{c} IS NOT NULL
            """
            try:
                client.query(sql).result()
            except Exception:
                sql = f"""
                    UPDATE `american-rel-infra.American_Religious_Infrastructure.churches` t
                    SET t.{c} = SAFE_CAST(s.{c} AS FLOAT64)
                    FROM `american-rel-infra.American_Religious_Infrastructure.{tmp_table}` s
                    WHERE t.id = s.id AND s.{c} IS NOT NULL
                """
                client.query(sql).result()
    
    client.delete_table(f"american-rel-infra.American_Religious_Infrastructure.{tmp_table}")
    os.unlink(tmp)
    
    r = client.query("SELECT COUNT(*) as c FROM `american-rel-infra.American_Religious_Infrastructure.churches` WHERE census_median_hh_income IS NOT NULL").result()
    cnt = list(r)[0].c
    print(f"  Census data updated: {cnt:,} rows")

def main():
    t0 = time.time()
    
    print(f"[{datetime.now().strftime('%H:%M:%S')}] Fetching ACS data...")
    zip_data = fetch_census()
    
    print(f"[{datetime.now().strftime('%H:%M:%S')}] Updating local DB...")
    cnt = update_local_db(zip_data)
    
    print(f"[{datetime.now().strftime('%H:%M:%S')}] Pushing to BigQuery...")
    push_to_bq()
    
    print(f"\n✅ Complete in {time.time()-t0:.0f}s")

if __name__ == "__main__":
    main()
