"""
==============================================================================
SQL MIGRATION — Compute estimated_attendance & attendance_confidence
==============================================================================

This script:
1. Adds estimated_attendance and attendance_confidence columns to churches
2. Creates a denom→ARDA lookup table from the existing keyword map
3. Creates a tmp_churches table with resolved ARDA codes
4. Computes attendance using the algorithm and writes results back

Algorithm (per denom_code + county_fips pair):
  C = arda_congregations  (from arda_counts)
  A = arda_adherents      (from arda_counts)
  N = count of our churches in that county/denom pair

  Rules:
    C==0 or A==0           → NULL, 0.0
    C==1 AND N==1           → A, 1.0
    C==N                    → A/N, 0.9
    C>N                     → A/C, 0.7
    C<N                     → A/N, 0.8

Usage:
    python scripts/enrichment/sql_compute_attendance.py
"""

import sqlite3
import csv
import os
import sys
from datetime import datetime

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.abspath(os.path.join(SCRIPT_DIR, '..', '..'))
DB = os.path.join(PROJECT_DIR, 'churches.db')
ARDA_CSV = os.path.join(PROJECT_DIR, 'data', 'arda', 'arda_per_denom_2020.csv')


# ── Keyword-based denomination mapping (same as arda_attendance.py) ──
DENOM_KEYWORDS = [
    ("COGIC", ["church of god in christ", "cogic"]),
    ("AMEZ", ["african methodist episcopal zion", "ame zion", "amez"]),
    ("AME", ["african methodist episcopal", "a.m.e.", "ame church"]),
    ("CME", ["christian methodist episcopal", "c.m.e.", "cme church"]),
    ("PC", ["presbyterian church (u.s.a.)", "presbyterian church (usa)", "presbyterian church u.s.a.", "presbyterian church usa", "pcusa", "presbyterian u.s.a."]),
    ("PCA", ["presbyterian church in america", "pca"]),
    ("EPC", ["evangelical presbyterian"]),
    ("OPC", ["orthodox presbyterian"]),
    ("RCA", ["reformed church in america"]),
    ("CRC", ["christian reformed"]),
    ("ELCA", ["evangelical lutheran", "elca"]),
    ("LCMS", ["lutheran church--missouri synod", "missouri synod", "lcms", "lutheran church mo synod"]),
    ("UMC", ["united methodist", "methodist church", "free methodist"]),
    ("WES", ["wesleyan"]),
    ("SBC", ["southern baptist", "sbc "]),
    ("NMBC", ["national baptist convention usa"]),
    ("ABC", ["american baptist"]),
    ("FWB", ["free will baptist"]),
    ("CCCC", ["christian church (disciples", "disciples of christ"]),
    ("COC", ["church of christ", "churches of christ"]),
    ("UCC", ["united church of christ", "congregational christian"]),
    ("NAZ", ["nazarene", "church of the nazarene"]),
    ("AGC", ["assemblies of god", "assembly of god"]),
    ("CGCT", ["church of god (cleveland", "church of god (cog"]),
    ("CGAI", ["church of god of prophecy"]),
    ("CHCH", ["church of god (anderson"]),
    ("CCNA", ["calvary chapel"]),
    ("EFCA", ["evangelical free church"]),
    ("ECC", ["evangelical covenant"]),
    ("CMA", ["christian and missionary alliance"]),
    ("VINE", ["vineyard"]),
    ("SDAC", ["seventh.day adventist", "sda ", "adventist"]),
    ("FOUR", ["foursquare"]),
    ("EC", ["episcopal church", "episcopal"]),
    ("CATH", ["roman catholic", "catholic"]),
    ("LDS", ["latter.day saint", "mormon", "lds", "community of christ"]),
    ("JW", ["jehovah", "jehovahs witnesses"]),
    ("UUA", ["unitarian universalist", "unitarian", "universalist"]),
    ("SALV", ["salvation army"]),
    ("ORTH", ["orthodox"]),
    ("GRK", ["greek orthodox"]),
    ("OCA", ["orthodox church in america"]),
    ("BRN", ["brethren"]),
    ("MENN", ["mennonite"]),
    ("FRND", ["friends (quaker", "quaker", "religious society of friends"]),
    ("NOND", ["non.denominational", "interdenominational", "non-denominational"]),
    ("BPRT", ["black protestant"]),
    ("BAPT", ["baptist", "missionary baptist", "independent baptist"]),
    ("MUS", ["muslim", "islam", "mosque"]),
    ("JEW", ["jewish", "judaism", "synagogue"]),
]


def find_arda_code(denomination, arda_codes):
    """Find the best ARDA code for a given denomination string."""
    if not denomination:
        return None
    d_lower = denomination.strip().lower()
    
    # 1. Direct match in arda_denom_map
    exact_match = {v: k for k, v in EXACT_DENOM_MAP.items()}
    if denomination in exact_match:
        code = exact_match[denomination]
        if code in arda_codes:
            return code
    
    # 2. Keyword matching
    for code, kws in DENOM_KEYWORDS:
        for kw in kws:
            if kw in d_lower:
                if code in arda_codes:
                    return code
    
    # 3. Partial containment in exact map
    for denom, code in EXACT_DENOM_MAP.items():
        dl = denom.lower()
        if len(dl) > 4 and len(d_lower) > 4:
            if dl in d_lower or d_lower in dl:
                if code in arda_codes:
                    return code
    
    return None


def main():
    print(f'═' * 60)
    print(f'SQL ATTENDANCE COMPUTATION')
    print(f'Started: {datetime.now().isoformat()}')
    print(f'═' * 60)
    
    db = sqlite3.connect(DB)
    cur = db.cursor()
    
    # Step 1: Add columns if not exist
    cur.execute("PRAGMA table_info(churches)")
    cols = [c[1] for c in cur.fetchall()]
    
    new_cols = []
    if 'estimated_attendance' not in cols:
        cur.execute("ALTER TABLE churches ADD COLUMN estimated_attendance INTEGER")
        new_cols.append('estimated_attendance')
    if 'attendance_confidence' not in cols:
        cur.execute("ALTER TABLE churches ADD COLUMN attendance_confidence REAL DEFAULT 0.0")
        new_cols.append('attendance_confidence')
    if new_cols:
        print(f'Added columns: {", ".join(new_cols)}')
    else:
        print('Columns already exist')
    
    # Step 2: Load ARDA codes set
    cur.execute("SELECT DISTINCT denom_code FROM arda_counts")
    arda_codes = set(r[0] for r in cur.fetchall())
    print(f'ARDA codes with data: {len(arda_codes)}')
    
    # Step 3: Get all churches with county_fips and denomination
    cur.execute("""
        SELECT id, denomination, county_fips
        FROM churches
        WHERE county_fips IS NOT NULL AND county_fips != ''
          AND denomination IS NOT NULL AND denomination != ''
    """)
    churches = cur.fetchall()
    print(f'Churches with FIPS + denom: {len(churches):,}')
    
    # Step 4: Map each church to its ARDA code and group by (code, county)
    from collections import defaultdict, Counter
    
    code_map = {}  # church_id -> arda_code
    code_map_failed = Counter()
    
    for cid, denom, fips in churches:
        code = find_arda_code(denom, arda_codes)
        if code:
            code_map[cid] = code
        else:
            code_map_failed[denom] += 1
    
    print(f'  Mapped to ARDA: {len(code_map):,}')
    print(f'  Unmapped: {len(churches) - len(code_map):,}')
    if code_map_failed:
        print(f'  Top 10 unmapped denominations:')
        for denom, cnt in code_map_failed.most_common(10):
            print(f'    {denom[:50]:50s} {cnt:>6,}')
    
    # Step 5: Count N = our churches per (code, county)
    church_counts = Counter()
    for cid, code in code_map.items():
        # Need to get the county_fips for this church
        pass
    
    # Better approach: build a dict
    code_county_counts = Counter()
    church_code_county = {}  # cid -> (code, county_fips)
    
    for cid, denom, fips in churches:
        if cid in code_map:
            code = code_map[cid]
            key = (code, fips)
            code_county_counts[key] += 1
            church_code_county[cid] = (code, fips)
    
    print(f'  Unique (code, county) pairs: {len(code_county_counts):,}')
    
    # Step 6: For each (code, county), look up ARDA values and compute
    # Pre-load ARDA data
    arda_lookup = {}
    cur.execute("SELECT denom_code, county_fips, arda_congregations, arda_adherents FROM arda_counts")
    for row in cur.fetchall():
        arda_lookup[(row[0], row[1])] = (row[2], row[3])
    
    print(f'  ARDA lookup entries: {len(arda_lookup):,}')
    
    # Compute per-church values
    updates = []  # (estimated_attendance, attendance_confidence, church_id)
    stats = Counter()
    
    for cid, (code, fips) in church_code_county.items():
        key = (code, fips)
        arda = arda_lookup.get(key)
        if not arda:
            updates.append((None, 0.0, cid))
            stats['no_arda_data'] += 1
            continue
        
        C, A = arda
        N = code_county_counts[key]
        
        if C == 0 or A == 0:
            updates.append((None, 0.0, cid))
            stats['zero_C_or_A'] += 1
        elif C == 1 and N == 1:
            updates.append((int(A), 1.0, cid))
            stats['C1_N1_direct'] += 1
        elif C == N:
            est = max(1, round(A / N))
            updates.append((est, 0.9, cid))
            stats['C_equal_N'] += 1
        elif C > N:
            est = max(1, round(A / C))
            updates.append((est, 0.7, cid))
            stats['C_greater_N'] += 1
        else:  # C < N
            est = max(1, round(A / N))
            updates.append((est, 0.8, cid))
            stats['C_less_N'] += 1
    
    print(f'\nComputation stats:')
    for key, cnt in stats.most_common():
        print(f'  {key:20s}: {cnt:>8,}')
    
    # Step 7: Write back to DB
    BATCH = 1000
    total = len(updates)
    written = 0
    
    cur.execute("BEGIN TRANSACTION")
    for i in range(0, total, BATCH):
        batch = updates[i:i+BATCH]
        cur.executemany(
            "UPDATE churches SET estimated_attendance=?, attendance_confidence=? WHERE id=?",
            batch
        )
        written += len(batch)
        if (i // BATCH) % 10 == 0:
            db.commit()
            cur.execute("BEGIN TRANSACTION")
    
    db.commit()
    print(f'\nWritten {written:,} attendance estimates to churches table')
    
    # Summary
    cur.execute("SELECT COUNT(*) FROM churches WHERE estimated_attendance IS NOT NULL")
    has_att = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM churches")
    total_churches = cur.fetchone()[0]
    print(f'Churches with estimated_attendance: {has_att:,} / {total_churches:,}')
    
    # Distribution of confidence levels
    cur.execute("""
        SELECT attendance_confidence, COUNT(*), AVG(estimated_attendance)
        FROM churches
        WHERE estimated_attendance IS NOT NULL
        GROUP BY attendance_confidence
        ORDER BY attendance_confidence DESC
    """)
    print('\nConfidence distribution:')
    for row in cur.fetchall():
        print(f'  confidence={row[0]:.1f}: {row[1]:>8,} records, avg att={row[2]:.0f}')
    
    db.close()
    print('\nDone!')


# Exact denomination map (same as in build_arda_counts.py)
EXACT_DENOM_MAP = {
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


if __name__ == '__main__':
    main()
