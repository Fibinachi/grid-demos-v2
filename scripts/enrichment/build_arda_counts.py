"""
Step 1: Build the arda_counts lookup table from the wide-format ARDA county CSV.

The ARDA CSV has one row per county with columns like:
  FIPS, CATHCNG_2020, CATHADH_2020, SBCCNG_2020, SBCADH_2020, ...

We melt this into a long-format table:
  arda_counts(denom_code, county_fips, arda_congregations, arda_adherents)

Also build arda_denom_map(code, denomination_name) for lookup.
"""

import csv
import sqlite3
import os
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.abspath(os.path.join(SCRIPT_DIR, '..', '..'))
DB = os.path.join(PROJECT_DIR, 'churches.db')
ARDA_CSV = os.path.join(PROJECT_DIR, 'data', 'arda', 'arda_per_denom_2020.csv')

# ── ARDA denomination code → our denomination text mapping ──
# Extracted from scripts/enrichment/arda_attendance.py
ARDA_DENOM_MAP = {
    "EVAN": "Evangelical",
    "MPRT": "Mainline Protestant",
    "BPRT": "Black Protestant",
    "CATH": "Roman Catholic Church",
    "ORTH": "Orthodox",
    "LDS": "Church of Jesus Christ of Latter-day Saints",
    "JEW": "Jewish",
    "MUS": "Muslim",
    "NOND": "Non-Denominational / Independent",
    "OTH": "Other",
    "AME": "African Methodist Episcopal Church",
    "AMEZ": "African Methodist Episcopal Zion Church",
    "CME": "Christian Methodist Episcopal Church",
    "UAMMEN": "African Methodist Episcopal Zion",
    "SBC": "Southern Baptist Convention",
    "ABC": "American Baptist Churches USA",
    "NMBC": "National Baptist Convention, USA",
    "NBCA": "National Baptist Convention of America",
    "PNBC": "Progressive National Baptist Convention",
    "FWB": "Free Will Baptist",
    "PFWB": "Original Free Will Baptist",
    "BMA": "Baptist Missionary Association of America",
    "GARB": "General Association of Regular Baptist Churches",
    "NACC": "North American Baptist Conference",
    "BFC": "Baptist Bible Fellowship International",
    "FGCAI": "Full Gospel Baptist Church Fellowship",
    "BGC": "Baptist General Conference",
    "CBC": "Conservative Baptist Association",
    "WBC": "World Baptist Fellowship",
    "IBAORB": "Independent Baptist",
    "UMC": "United Methodist Church",
    "FMC": "Free Methodist Church",
    "WES": "Wesleyan Church",
    "FUM": "Free Methodist Church",
    "BWC": "Bible Wesleyan Church",
    "NFMC": "National Association of Free Methodists",
    "UFM": "United Free Methodist",
    "ELCA": "Evangelical Lutheran Church in America",
    "LCMS": "Lutheran Church--Missouri Synod",
    "WELS": "Wisconsin Evangelical Lutheran Synod",
    "ELS": "Evangelical Lutheran Synod",
    "NALC": "North American Lutheran Church",
    "LCMC": "Lutheran Congregations in Mission for Christ",
    "AALC": "American Association of Lutheran Churches",
    "AFLC": "Association of Free Lutheran Congregations",
    "PCUSA": "Presbyterian Church (USA)",
    "PC": "Presbyterian Church (U.S.A.)",
    "PCA": "Presbyterian Church in America",
    "EPC": "Evangelical Presbyterian Church",
    "OPC": "Orthodox Presbyterian Church",
    "RPC": "Reformed Presbyterian Church",
    "APC": "Associate Reformed Presbyterian Church",
    "ARP": "Associate Reformed Presbyterian",
    "CRC": "Christian Reformed Church in North America",
    "RCA": "Reformed Church in America",
    "UCC": "United Church of Christ",
    "RCUS": "Reformed Church in the United States",
    "CREC": "Communion of Reformed Evangelical Churches",
    "FRC": "Free Reformed Church",
    "AGC": "Assemblies of God",
    "UPCI": "United Pentecostal Church International",
    "COGIC": "Church of God in Christ",
    "CGCT": "Church of God (Cleveland, TN)",
    "CGAI": "Church of God of Prophecy",
    "PAW": "Pentecostal Assemblies of the World",
    "IPCC": "International Pentecostal Church of Christ",
    "COLC": "Church of God (Mountain Assembly)",
    "INTF": "International Pentecostal Holiness Church",
    "PILM": "Pentecostal Church of God",
    "EC": "Episcopal Church",
    "ACNA": "Anglican Church in North America",
    "REC": "Reformed Episcopal Church",
    "ANCA": "Anglican Catholic Church",
    "NAZ": "Church of the Nazarene",
    "CGGC": "Church of God (Anderson, IN)",
    "FGC": "Fellowship of Grace Brethren Churches",
    "CMA": "Christian and Missionary Alliance",
    "MCF": "Missionary Church",
    "DOC": "Christian Church (Disciples of Christ)",
    "CCCC": "Christian Churches and Churches of Christ",
    "COC": "Church of Christ",
    "CCC": "Churches of Christ",
    "NCC": "Non-denominational Christian Church",
    "SDAC": "Seventh-day Adventist Church",
    "SDB": "Seventh Day Baptist",
    "CG7D": "Church of God (Seventh Day)",
    "COGA": "Church of God (Seventh Day)",
    "MENN": "Mennonite",
    "BRN": "Brethren",
    "BIC": "Brethren in Christ",
    "FRND": "Religious Society of Friends (Quakers)",
    "USMB": "United States Mennonite Brethren",
    "RFRM": "Reformed Mennonite",
    "EFCA": "Evangelical Free Church of America",
    "ECC": "Evangelical Covenant Church",
    "VINE": "Vineyard USA",
    "CCNA": "Calvary Chapel",
    "EMC": "Evangelical Mennonite Church",
    "CCON": "Conservative Congregational Christian Conference",
    "CTH": "Roman Catholic Church",
    "OCA": "Orthodox Church in America",
    "GRK": "Greek Orthodox",
    "ROC": "Russian Orthodox",
    "ANT": "Antiochian Orthodox",
    "ROAA": "Romanian Orthodox",
    "BULG": "Bulgarian Orthodox",
    "SERB": "Serbian Orthodox",
    "JW": "Jehovah's Witnesses",
    "UUA": "Unitarian Universalist",
    "SALV": "Salvation Army",
    "CHRD": "Christian Reformed Church",
    "MCC": "Metropolitan Community Churches",
    "JUD": "Jewish",
    "RJUD": "Jewish (Reform)",
    "CJUD": "Jewish (Conservative)",
    "OJUD": "Jewish (Orthodox)",
    "IJUD": "Jewish (Independent)",
    "MSLM": "Muslim",
    "THBUD": "Buddhist (Theravada)",
    "MAHBUD": "Buddhist (Mahayana)",
    "VAJBUD": "Buddhist (Vajrayana)",
    "HINT": "Hindu",
    "SIKH": "Sikh",
    "BAOC": "Baha'i",
    "CHCH": "Church of God (Anderson, IN)",
    "FOUR": "Foursquare Church",
    "BAPT": "Baptist (unspecified)",
}


def build_arda_counts():
    """Read the wide-format ARDA CSV and build the arda_counts table."""
    print(f"Reading ARDA CSV: {ARDA_CSV}")
    
    with open(ARDA_CSV, encoding='utf-8') as f:
        reader = csv.DictReader(f)
        rows = list(reader)
    
    print(f"  Loaded {len(rows)} county rows")
    
    # Identify denomination codes from column names
    all_cols = reader.fieldnames
    cng_cols = sorted(set(c for c in all_cols if c.endswith('CNG_2020') and c != 'TOTCNG_2020'))
    adh_cols = set(c for c in all_cols if c.endswith('ADH_2020') and c != 'TOTADH_2020')
    
    # Extract denomination codes (everything before CNG_2020)
    codes = set()
    for c in cng_cols:
        code = c.replace('CNG_2020', '')
        codes.add(code)
    
    print(f"  Found {len(codes)} denomination codes with congregation data")
    
    # Build arda_counts data
    counts_data = []
    missing_cng = 0
    zero_cng = 0
    
    for row in rows:
        fips = row.get('FIPS', '').replace('.0', '')
        if not fips:
            continue
        
        for code in codes:
            cng_field = f'{code}CNG_2020'
            adh_field = f'{code}ADH_2020'
            
            cng_val = row.get(cng_field, '').strip()
            adh_val = row.get(adh_field, '').strip()
            
            if not cng_val or not adh_val:
                missing_cng += 1
                continue
            
            try:
                cng = float(cng_val)
                adh = float(adh_val)
            except (ValueError, TypeError):
                continue
            
            if cng <= 0 or adh <= 0:
                zero_cng += 1
                continue
            
            counts_data.append((code, fips, int(cng), int(adh)))
    
    print(f"  Skipped {missing_cng} missing entries, {zero_cng} zero entries")
    print(f"  Built {len(counts_data)} rows for arda_counts")
    
    # Connect to DB
    db = sqlite3.connect(DB)
    cur = db.cursor()
    
    # Create arda_counts table
    cur.execute("DROP TABLE IF EXISTS arda_counts")
    cur.execute("""
        CREATE TABLE arda_counts (
            denom_code TEXT NOT NULL,
            county_fips TEXT NOT NULL,
            arda_congregations INTEGER NOT NULL,
            arda_adherents INTEGER NOT NULL,
            PRIMARY KEY (denom_code, county_fips)
        )
    """)
    
    # Insert in batch
    BATCH = 500
    for i in range(0, len(counts_data), BATCH):
        batch = counts_data[i:i+BATCH]
        cur.executemany(
            "INSERT INTO arda_counts (denom_code, county_fips, arda_congregations, arda_adherents) VALUES (?, ?, ?, ?)",
            batch
        )
    
    db.commit()
    
    # Count
    cur.execute("SELECT COUNT(*) FROM arda_counts")
    print(f"  Inserted {cur.fetchone()[0]:,} rows into arda_counts")
    cur.execute("SELECT COUNT(DISTINCT county_fips) FROM arda_counts")
    print(f"  Covers {cur.fetchone()[0]:,} unique counties")
    cur.execute("SELECT COUNT(DISTINCT denom_code) FROM arda_counts")
    print(f"  Covers {cur.fetchone()[0]} unique denomination codes")
    
    # ── Build arda_denom_map table ──
    cur.execute("DROP TABLE IF EXISTS arda_denom_map")
    cur.execute("""
        CREATE TABLE arda_denom_map (
            code TEXT PRIMARY KEY,
            denomination_name TEXT NOT NULL
        )
    """)
    
    map_data = [(code, denom) for code, denom in ARDA_DENOM_MAP.items()]
    cur.executemany(
        "INSERT OR REPLACE INTO arda_denom_map (code, denomination_name) VALUES (?, ?)",
        map_data
    )
    db.commit()
    
    cur.execute("SELECT COUNT(*) FROM arda_denom_map")
    print(f"  Inserted {cur.fetchone()[0]} rows into arda_denom_map")
    
    db.close()
    print("Done!")


if __name__ == '__main__':
    build_arda_counts()
