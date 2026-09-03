"""
Import CRA charities into churches.db with full provenance.
Handles both 2018 and 2011 datasets for longitudinal comparison.

CRA 2018 Category codes (broad):
  30 = Advancement of Religion (Christian, 26K+)
  40 = Muslim / Islamic
  50 = Jewish / Synagogue
  60 = Buddhist / Sikh / Hindu / Other non-Christian
  90 = Religious education / broadcasting / endowments

CRA 2011 Category codes (granular):
  30-39 = Christian denominations (Anglican, Baptist, Lutheran, Evangelical, Presbyterian, Catholic, etc.)
  42 = Synagogues
  43, 35 = Buddhist
  44 = Pastoral charges (United Church, etc.)
  45 = Synagogues
  47 = Catholic orgs, Jehovah ministries
  48 = Hindu
  49 = Mixed religious (synagogue, Buddhist, camp)
  59-60 = Muslim
  61 = Jehovah's Witnesses
  62 = Sikh

CRA Designation: C=Charitable Org, F=Public Foundation, P=Private Foundation
"""
import pandas as pd, sqlite3, os, time

PROJECT_DIR = "E:/grid"
DATA_DIR = os.path.join(PROJECT_DIR, "data", "cra")
DB_PATH = os.path.join(PROJECT_DIR, "churches.db")

# 2018 scheme (broad)
RELIGIOUS_2018 = {30, 40, 50, 60, 90}
# 2011 scheme (granular) — Christian 30-39 + 44+47+61, Jewish 42, Buddhist 35+43, Muslim 60, Hindu 48, Sikh 62
# EXCLUDED: 49 (0% religious — mixed secular), 59 (0% religious — employment/community), 45 (48% religious — mixed endowments)
RELIGIOUS_2011 = set(range(30, 40)) | {35, 42, 43, 44, 47, 48, 60, 61, 62}

# Category → tradition mapping for 2011
CAT_TO_TRADITION_2011 = {
    **{c: "Christian" for c in [30,31,32,33,34,36,37,38,39,44,47,61,63]},
    **{c: "Muslim" for c in [60]},
    **{c: "Jewish" for c in [42]},
    **{c: "Buddhist" for c in [35,43]},
    **{c: "Hindu" for c in [48]},
    **{c: "Sikh" for c in [62]},
}

# CRA category → broad tradition
CAT_TO_TRADITION = {30: "Christian", 40: "Muslim", 50: "Jewish", 60: "Buddhist", 90: "Christian"}

def import_cra_year(csv_path, year_label):
    print(f"\n{'='*60}")
    print(f"Importing CRA {year_label}: {os.path.basename(csv_path)}")
    print(f"{'='*60}")
    
    # Choose scheme
    is_2018 = year_label == "2018"
    religious_cats = RELIGIOUS_2018 if is_2018 else RELIGIOUS_2011
    
    # --- Read CSV ---
    print(f"Reading...")
    df = pd.read_csv(csv_path, encoding="utf-8", low_memory=False)
    print(f"  Total rows: {len(df):,}")
    
    # --- Filter to religious ---
    religious = df[df["Category"].isin(religious_cats)].copy()
    print(f"  Religious ({len(religious_cats)} categories): {len(religious):,}")
    
    # --- Clean ---
    # 2011 has no 'Sub Category' column
    if "Sub Category" not in religious.columns:
        religious["Sub Category"] = None
    
    religious.rename(columns={
        "Legal Name": "name", "Account Name": "account_name",
        "Address Line 1": "address", "Address Line 2": "address2",
        "City": "city", "Province": "state", "Postal Code": "postal_code",
        "Country": "country_code", "BN": "cra_bn",
        "Category": "cra_category", "Sub Category": "cra_sub_category",
        "Designation": "cra_designation",
    }, inplace=True)
    
    # Build full address (using original column name before rename)
    def build_addr(row):
        parts = [str(row["address"]) if pd.notna(row["address"]) else ""]
        if pd.notna(row["address2"]) and str(row["address2"]).strip():
            parts.append(str(row["address2"]))
        parts.append(f"{str(row['city'])}, {str(row['state'])} {str(row['postal_code'])}")
        return ", ".join(parts)
    
    religious["full_address"] = religious.apply(build_addr, axis=1)
    religious["country"] = "CA"
    religious["source"] = f"cra_{year_label}"
    
    if is_2018:
        religious["denomination"] = religious["cra_category"].map(CAT_TO_TRADITION).fillna("Other")
    else:
        religious["denomination"] = religious["cra_category"].map(CAT_TO_TRADITION_2011).fillna("Other")
    # Rename to match DB column
    religious.rename(columns={"postal_code": "zip"}, inplace=True)
    
    # --- Stats ---
    print(f"\nBy Province:")
    for prov, count in religious["state"].value_counts().items():
        print(f"  {prov}: {count:,}")
    
    print(f"\nBy Category:")
    trad_map = CAT_TO_TRADITION if is_2018 else CAT_TO_TRADITION_2011
    for cat, count in religious["cra_category"].value_counts().items():
        samples = religious[religious["cra_category"] == cat]["name"].head(3).tolist()
        print(f"  Cat {cat} ({trad_map.get(cat,'?')}): {count:,} — {samples[:2]}")
    
    # --- DB Import ---
    db = sqlite3.connect(DB_PATH)
    
    # Build insert dataframe
    cols = ["name", "address", "city", "state", "zip", "country",
            "source", "denomination", "cra_bn", "cra_category", 
            "cra_sub_category", "cra_designation", "full_address", "account_name"]
    insert_df = religious[cols].copy()
    
    # Temp table
    db.execute("DROP TABLE IF EXISTS _cra_import")
    insert_df.to_sql("_cra_import", db, index=False, if_exists="replace")
    db.execute("CREATE INDEX IF NOT EXISTS idx_cra_bn_imp ON _cra_import(cra_bn)")
    db.execute("CREATE INDEX IF NOT EXISTS idx_cra_name_imp ON _cra_import(name)")
    
    # Check BN overlap
    existing = db.execute("""
        SELECT COUNT(*) FROM _cra_import ci
        INNER JOIN churches c ON c.cra_bn = ci.cra_bn
    """).fetchone()[0]
    print(f"\n  Already in DB (by BN match): {existing:,}")
    
    # Insert new — by BN (unique CRA identifier)
    t0 = time.time()
    new_count = db.execute("""
        INSERT INTO churches (name, address, city, state, zip,
                             country, source, denomination, cra_bn,
                             cra_category, cra_sub_category, cra_designation)
        SELECT ci.name, ci.address, ci.city, ci.state, ci.zip,
               ci.country, ci.source, ci.denomination, ci.cra_bn,
               ci.cra_category, ci.cra_sub_category, ci.cra_designation
        FROM _cra_import ci
        WHERE ci.cra_bn NOT IN (SELECT cra_bn FROM churches WHERE cra_bn IS NOT NULL)
          AND ci.cra_bn IS NOT NULL
    """).rowcount
    print(f"  New churches inserted: {new_count:,} in {time.time()-t0:.1f}s")
    
    # Provenance — script-level log
    db.execute("""
        INSERT INTO provenance_log (source, script_name, started_at, completed_at, 
                                    churches_inserted, status, notes)
        VALUES (?, ?, datetime('now'), datetime('now'), ?, 'completed', ?)
    """, (f"cra_{year_label}", f"import_cra_{year_label}", new_count, 
          f"CRA {year_label} charities import — {len(religious):,} religious orgs"))
    
    db.execute("DROP TABLE IF EXISTS _cra_import")
    db.commit()
    db.close()
    return new_count

if __name__ == "__main__":
    # Import 2018
    csv_2018 = os.path.join(DATA_DIR, "cra_2018_identification.csv")
    if os.path.exists(csv_2018):
        n = import_cra_year(csv_2018, "2018")
        print(f"\n✅ CRA 2018: {n:,} new churches added")
    else:
        print(f"⚠ 2018 CSV not found at {csv_2018}")
    
    # Import 2011
    csv_2011 = os.path.join(DATA_DIR, "cra_2011_identification.csv")
    if os.path.exists(csv_2011):
        n = import_cra_year(csv_2011, "2011")
        print(f"\n✅ CRA 2011: {n:,} new churches added")
    else:
        print(f"\n⏳ 2011 CSV not yet downloaded — save to: {csv_2011}")
