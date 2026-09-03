"""
Download ARDA 2010 US Religion Census County File and import into GRID.

Source: OSF (DOI 10.17605/OSF.IO/QUN29) or ARDA data archive (FID RCMSCY10)
The 2010 file has same format as 2020: FIPS, COUNAM, STABBREV, STATNAM, POP2010,
then [DENOM]CNG_2010 and [DENOM]ADH_2010 columns for each denomination.

Usage:
  1. Download the XLSX from: https://thearda.com/data-archive?fid=RCMSCY10
     Click "Downloads" tab → download the .xlsx file
     Save as: data/arda/rcms_2010_county.xlsx
  
  2. OR download from OSF: https://osf.io/qun29/
     Save as: data/arda/rcms_2010_county.xlsx

  3. Run this script: python scripts/enrichment/import_arda_2010.py
"""
import sqlite3, csv, os, sys, re
from collections import defaultdict

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.abspath(os.path.join(SCRIPT_DIR, '..', '..'))
os.chdir(PROJECT_DIR)

DB = os.path.join(PROJECT_DIR, 'churches.db')
XLSX_PATH = os.path.join(PROJECT_DIR, 'data', 'arda', 'rcms_2010_county.xlsx')
CSV_PATH = os.path.join(PROJECT_DIR, 'data', 'arda', 'arda_per_denom_2010.csv')

# Summary column prefixes to exclude from denomination codes
SUMMARY_PREFIXES = {'TOT', 'EVAN', 'MPRT', 'BPRT', 'CPRT', 'ORTH', 'CATH', 'OTH', 
                     'NOND', 'BLACK', 'HISP', 'WHITE', 'JEW', 'MUS', 'BUD', 'HIN'}

# Step 1: Convert XLSX to CSV (2010 format: {CODE}CNG, {CODE}ADH without year suffix)
if not os.path.exists(CSV_PATH):
    if not os.path.exists(XLSX_PATH):
        print("ERROR: Need rcms_2010_county.xlsx in data/arda/")
        print("Download from: https://thearda.com/data-archive?fid=RCMSCY10")
        print("Click 'Downloads' tab → download .xlsx")
        sys.exit(1)
    
    print("Converting XLSX to CSV...")
    import pandas as pd
    df = pd.read_excel(XLSX_PATH, engine='calamine')
    df.to_csv(CSV_PATH, index=False)
    print(f"   Converted {len(df):,} rows x {len(df.columns):,} cols to {CSV_PATH}")

# Step 2: Parse CSV and build arda_counts_2010 table
print("Parsing 2010 CSV...")
with open(CSV_PATH, 'r', encoding='utf-8') as f:
    reader = csv.DictReader(f)
    headers = reader.fieldnames
    rows = list(reader)

print(f"   {len(rows):,} counties, {len(headers):,} columns")

# Find all denomination columns: [CODE]CNG (2010 format, no year suffix)
denom_codes = set()
for h in headers:
    m = re.match(r'^([A-Z0-9]+)CNG$', h)
    if m:
        code = m.group(1)
        if code not in SUMMARY_PREFIXES:
            denom_codes.add(code)

print(f"   Found {len(denom_codes):,} denomination codes")

# Step 3: Insert into arda_counts_2010 table
print("Importing into database...")
conn = sqlite3.connect(DB)
c = conn.cursor()

c.execute("DROP TABLE IF EXISTS arda_counts_2010")
c.execute("""
    CREATE TABLE arda_counts_2010 (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        denom_code TEXT,
        county_fips TEXT,
        arda_congregations INTEGER,
        arda_adherents INTEGER,
        created_at TEXT DEFAULT (datetime('now'))
    )
""")
c.execute("CREATE INDEX IF NOT EXISTS idx_ac10_denom ON arda_counts_2010(denom_code)")
c.execute("CREATE INDEX IF NOT EXISTS idx_ac10_fips ON arda_counts_2010(county_fips)")

# Also build denom lookup
c.execute("DROP TABLE IF EXISTS arda_denom_lookup_2010")
c.execute("CREATE TABLE arda_denom_lookup_2010 (code TEXT PRIMARY KEY, name TEXT)")

# ARDA code descriptions (from 2020 mapping, same codes for 2010)
ARDA_DENOM_MAP = {
    "SBC": "Southern Baptist Convention",
    "ABC": "American Baptist Churches USA",
    "BGC": "Baptist General Conference",
    "NBC": "National Baptist Convention",
    "PNBC": "Progressive National Baptist Convention",
    "CATH": "Roman Catholic Church",
    "UMC": "United Methodist Church",
    "ELCA": "Evangelical Lutheran Church in America",
    "LCMS": "Lutheran Church - Missouri Synod",
    "PC": "Presbyterian Church (U.S.A.)",
    "PCA": "Presbyterian Church in America",
    "EC": "Episcopal Church",
    "AGC": "Assemblies of God",
    "COGIC": "Church of God in Christ",
    "AME": "African Methodist Episcopal Church",
    "AMEZ": "African Methodist Episcopal Zion Church",
    "CME": "Christian Methodist Episcopal Church",
    "LDS": "Church of Jesus Christ of Latter-day Saints",
    "JW": "Jehovah's Witnesses",
    "SDAC": "Seventh-day Adventist Church",
    "NOND": "Non-Denominational",
    "EVAN": "Evangelical",
    "MPRT": "Mainline Protestant",
    "BPRT": "Black Protestant",
    "ORTH": "Orthodox",
    "JEW": "Jewish",
    "MUS": "Muslim",
    "OTH": "Other",
}

insert_count = 0
batch = []
CHUNK = 500

for row in rows:
    fips = row.get('FIPS', '').strip()
    if not fips: 
        continue
    fips = fips.zfill(5)  # pad to 5 digits
    
    for code in denom_codes:
        cng = row.get(f'{code}CNG', '').strip()
        adh = row.get(f'{code}ADH', '').strip()
        
        try:
            cng_val = int(float(cng)) if cng else None
        except ValueError:
            cng_val = None
        try:
            adh_val = int(float(adh)) if adh else None
        except ValueError:
            adh_val = None
        
        if cng_val is not None or adh_val is not None:
            batch.append((code, fips, cng_val, adh_val))
            insert_count += 1
        
        if len(batch) >= CHUNK:
            c.executemany("INSERT INTO arda_counts_2010 (denom_code, county_fips, arda_congregations, arda_adherents) VALUES (?, ?, ?, ?)", batch)
            batch = []

if batch:
    c.executemany("INSERT INTO arda_counts_2010 (denom_code, county_fips, arda_congregations, arda_adherents) VALUES (?, ?, ?, ?)", batch)

# Insert denom lookup
for code, name in ARDA_DENOM_MAP.items():
    if code in denom_codes:
        c.execute("INSERT OR IGNORE INTO arda_denom_lookup_2010 (code, name) VALUES (?, ?)", (code, name))

conn.commit()

# Stats
c.execute("SELECT COUNT(*) FROM arda_counts_2010")
total = c.fetchone()[0]
c.execute("SELECT COUNT(DISTINCT county_fips) FROM arda_counts_2010")
counties = c.fetchone()[0]
c.execute("SELECT COUNT(DISTINCT denom_code) FROM arda_counts_2010")
denoms = c.fetchone()[0]

# SBC specific
c.execute("SELECT COUNT(DISTINCT county_fips), SUM(arda_adherents), SUM(arda_congregations) FROM arda_counts_2010 WHERE denom_code='SBC' AND arda_adherents>0")
sbc = c.fetchone()
print(f"\n{'='*60}")
print("2010 ARDA Import Complete")
print(f"{'='*60}")
print(f"  Total rows:          {total:>10,}")
print(f"  Counties:            {counties:>10,}")
print(f"  Denominations:       {denoms:>10,}")
print(f"  SBC counties:        {sbc[0]:>10,}")
print(f"  SBC adherents:       {sbc[1]:>10,}")
print(f"  SBC congregations:   {sbc[2]:>10,}")

# Compare with 2020
c.execute("SELECT SUM(arda_adherents), SUM(arda_congregations) FROM arda_counts WHERE denom_code='SBC'")
sbc20 = c.fetchone()
print(f"\n  2020 SBC adherents:  {sbc20[0]:>10,}")
print(f"  2020 SBC congregations:{sbc20[1]:>10,}")
if sbc[1] and sbc20[0]:
    change = ((sbc20[0] - sbc[1]) / sbc[1]) * 100
    print(f"  Change 2010→2020:     {change:>+9.1f}%")

conn.close()
print("\nDone. Table: arda_counts_2010")
