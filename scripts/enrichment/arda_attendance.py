#!/usr/bin/env python3
"""
Extract ARDA per-denomination county data from .sav file and
compute attendance estimates for churches.

Phase 1: Extract per-denom congregation+adherent counts to CSV
Phase 2: Map ARDA denomination codes to our denomination names
Phase 3: Compute attendance per church (direct attribution or average)
Phase 4: Store in DB with source tracking

Usage:
    python scripts/enrichment/arda_attendance.py --extract    # Phase 1
    python scripts/enrichment/arda_attendance.py --compute    # Phases 2-4
    python scripts/enrichment/arda_attendance.py --all        # Everything
"""
import csv, json, os, re, sqlite3, sys
from datetime import datetime
from collections import defaultdict

PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
for _ in range(5):
    if os.path.exists(os.path.join(PROJECT_DIR, "churches.db")):
        break
    parent = os.path.dirname(PROJECT_DIR)
    if parent == PROJECT_DIR:
        break
    PROJECT_DIR = parent

DB_PATH = os.path.join(PROJECT_DIR, "churches.db")
ARDA_DIR = os.path.join(PROJECT_DIR, "data", "arda")
SAV_PATH = os.path.join(ARDA_DIR, "U.S. Religion Census - Religious Congregations and Membership Study, 2020 (County File).sav")
PER_DENOM_CSV = os.path.join(ARDA_DIR, "arda_per_denom_2020.csv")

# ═══════════════════════════════════════════════════════════════
# ARDA Denomination Code → Our Denomination Name Mapping
# ═══════════════════════════════════════════════════════════════
# Maps the ARDA 3-4 letter codes to the denomination strings in our DB

ARDA_DENOM_MAP = {
    # Broad traditions
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
    
    # Specific denominations
    "AME": "African Methodist Episcopal Church",
    "AMEZ": "African Methodist Episcopal Zion Church",
    "CME": "Christian Methodist Episcopal Church",
    "AMEZ": "African Methodist Episcopal Zion",
    "CME": "Christian Methodist Episcopal",
    "UAMMEN": "African Methodist Episcopal Zion",
    
    # Baptist
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
    
    # Methodist / Wesleyan
    "UMC": "United Methodist Church",
    "FMC": "Free Methodist Church",
    "WES": "Wesleyan Church",
    "FUM": "Free Methodist Church",
    "BWC": "Bible Wesleyan Church",
    "NFMC": "National Association of Free Methodists",
    "UFM": "United Free Methodist",
    
    # Lutheran
    "ELCA": "Evangelical Lutheran Church in America",
    "LCMS": "Lutheran Church--Missouri Synod",
    "WELS": "Wisconsin Evangelical Lutheran Synod",
    "ELS": "Evangelical Lutheran Synod",
    "NALC": "North American Lutheran Church",
    "LCMC": "Lutheran Congregations in Mission for Christ",
    "AALC": "American Association of Lutheran Churches",
    "AFLC": "Association of Free Lutheran Congregations",
    
    # Presbyterian / Reformed
    "PCUSA": "Presbyterian Church (USA)",
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
    
    # Pentecostal
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
    
    # Anglican / Episcopal
    "EC": "Episcopal Church",
    "ACNA": "Anglican Church in North America",
    "REC": "Reformed Episcopal Church",
    "ANCA": "Anglican Catholic Church",
    
    # Holiness
    "NAZ": "Church of the Nazarene",
    "CGGC": "Church of God (Anderson, IN)",
    "FGC": "Fellowship of Grace Brethren Churches",
    "CMA": "Christian and Missionary Alliance",
    "WES": "Wesleyan Church",
    "MCF": "Missionary Church",
    
    # Restoration Movement
    "DOC": "Christian Church (Disciples of Christ)",
    "CCCC": "Christian Churches and Churches of Christ",
    "COC": "Church of Christ",
    "CCC": "Churches of Christ",
    "NCC": "Non-denominational Christian Church",
    "NACC": "North American Christian Convention",
    
    # Adventist
    "SDAC": "Seventh-day Adventist Church",
    "SDB": "Seventh Day Baptist",
    "CG7D": "Church of God (Seventh Day)",
    "COGA": "Church of God (Seventh Day)",
    
    # Anabaptist / Mennonite / Brethren
    "MENN": "Mennonite",
    "BRN": "Brethren",
    "BIC": "Brethren in Christ",
    "FRND": "Religious Society of Friends (Quakers)",
    "USMB": "United States Mennonite Brethren",
    "RFRM": "Reformed Mennonite",
    
    # Evangelical / Independent
    "EFCA": "Evangelical Free Church of America",
    "ECC": "Evangelical Covenant Church",
    "CMA": "Christian and Missionary Alliance",
    "VINE": "Vineyard USA",
    "CCNA": "Calvary Chapel",
    "BIC": "Bible Church",
    "EMC": "Evangelical Mennonite Church",
    "CCON": "Conservative Congregational Christian Conference",
    
    # Catholic / Orthodox
    "CATH": "Roman Catholic Church",
    "CTH": "Roman Catholic Church",
    "ORTH": "Orthodox",
    "OCA": "Orthodox Church in America",
    "GRK": "Greek Orthodox",
    "ROC": "Russian Orthodox",
    "ANT": "Antiochian Orthodox",
    "ROAA": "Romanian Orthodox",
    "BULG": "Bulgarian Orthodox",
    "SERB": "Serbian Orthodox",
    
    # Others
    "LDS": "Church of Jesus Christ of Latter-day Saints",
    "JW": "Jehovah's Witnesses",
    "UUA": "Unitarian Universalist",
    "SALV": "Salvation Army",
    "CHRD": "Christian Reformed Church",
    "MCC": "Metropolitan Community Churches",
    "NAZ": "Church of the Nazarene",
    
    # Jewish
    "JUD": "Jewish",
    "RJUD": "Jewish (Reform)",
    "CJUD": "Jewish (Conservative)",
    "OJUD": "Jewish (Orthodox)",
    "IJUD": "Jewish (Independent)",
    
    # Muslim
    "MSLM": "Muslim",
    
    # Buddhist
    "THBUD": "Buddhist (Theravada)",
    "MAHBUD": "Buddhist (Mahayana)",
    "VAJBUD": "Buddhist (Vajrayana)",
    
    # Hindu
    "HINT": "Hindu",
    
    # Sikh
    "SIKH": "Sikh",
    
    # Baha'i
    "BAOC": "Baha'i",
}

# Reverse: partial denomination string → ARDA code
# Used to find which ARDA code matches a given church's denomination
DENOM_TO_ARDA = {}
for code, denom in ARDA_DENOM_MAP.items():
    key = denom.lower().replace(" ", "_").replace("(", "").replace(")", "").replace("-", "_")
    DENOM_TO_ARDA[denom] = code

# Load ARDA field names for field verification in find_arda_code
ARDA_FIELDS = set()
_ARDA_CSV = os.path.join(PROJECT_DIR, "data", "arda", "arda_per_denom_2020.csv")
if os.path.exists(_ARDA_CSV):
    import csv as _csv
    with open(_ARDA_CSV, encoding="utf-8") as _f:
        ARDA_FIELDS = set(_f.readline().strip().split(","))

def log(msg):
    print("[%s] %s" % (datetime.now().strftime("%H:%M:%S"), msg))

# ═══════════════════════════════════════════════════════════════
# PHASE 1: Extract per-denomination data from .sav
# ═══════════════════════════════════════════════════════════════

def phase1_extract():
    """Extract per-denomination congregation + adherent counts from .sav."""
    log("Phase 1: Extracting per-denomination data from .sav...")
    
    try:
        import pyreadstat
    except ImportError:
        log("  ERROR: pyreadstat not installed. Run: pip install pyreadstat")
        return
    
    df, meta = pyreadstat.read_sav(SAV_PATH)
    headers = list(df.columns)
    log(f"  File has {len(headers)} variables, {len(df)} rows")
    
    # Identify congregation count and adherent count fields
    cng_fields = sorted([h for h in headers if h.endswith("CNG_2020")])
    adh_fields = sorted([h for h in headers if h.endswith("ADH_2020")])
    
    log(f"  Found {len(cng_fields)} congregation fields, {len(adh_fields)} adherent fields")
    
    # Core columns to include
    core_cols = ["FIPS", "COUNAM", "STABBREV", "STATNAM", "POP2020", "TOTCNG_2020", "TOTADH_2020"]
    output_cols = core_cols + cng_fields + adh_fields
    output_cols = [c for c in output_cols if c in df.columns]
    
    # Write CSV
    df_out = df[output_cols].copy()
    # Fill NaN with empty string
    df_out = df_out.fillna("")
    # Clean FIPS - remove .0
    if "FIPS" in df_out.columns:
        df_out["FIPS"] = df_out["FIPS"].apply(lambda x: str(x).replace(".0", "") if x != "" else "")
    
    df_out.to_csv(PER_DENOM_CSV, index=False, encoding="utf-8")
    log(f"  Written {len(df_out)} counties to {PER_DENOM_CSV}")
    
    # Quick summary of non-empty congregation fields
    non_zero_counts = {}
    for f in cng_fields:
        if f in df.columns:
            cnt = (df[f].notna() & (df[f] > 0)).sum()
            if cnt > 0:
                non_zero_counts[f] = cnt
    
    log(f"\n  Denominations with congregation data (top 30):")
    for f, cnt in sorted(non_zero_counts.items(), key=lambda x: -x[1])[:30]:
        code = f.replace("CNG_2020", "")
        log(f"    {code:8s}: {cnt:5d} counties have congregations")

# ═══════════════════════════════════════════════════════════════
# PHASE 2-4: Compute attendance from ARDA data
# ═══════════════════════════════════════════════════════════════

def find_arda_code(denomination):
    """Find the best ARDA code for a given denomination string."""
    if not denomination:
        return None
    d = denomination.strip()
    d_lower = d.lower()
    
    # 1. Direct match
    if d in DENOM_TO_ARDA:
        return DENOM_TO_ARDA[d]
    
    # 2. Keyword matching - ordered list, most specific first
    keywords = [
        ("COGIC", ["church of god in christ", "cogic"]),
        ("AMEZ", ["african methodist episcopal zion", "ame zion", "amez"]),
        ("AME", ["african methodist episcopal", "a.m.e.", "ame church"]),
        ("CME", ["christian methodist episcopal", "c.m.e.", "cme church"]),
        ("PCUSA", ["presbyterian church (usa)", "presbyterian church u.s.a.", "presbyterian church usa", "pcusa", "presbyterian u.s.a."]),
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
        ("BAPT", ["baptist", "missionary baptist"]),
        ("MUS", ["muslim", "islam", "mosque"]),
        ("JEW", ["jewish", "judaism", "synagogue"]),
    ]
    
    for code, kws in keywords:
        for kw in kws:
            if kw in d_lower:
                # Verify the ARDA field exists
                cng_field = f"{code}CNG_2020"
                adh_field = f"{code}ADH_2020"
                if cng_field in ARDA_FIELDS and adh_field in ARDA_FIELDS:
                    return code
                elif cng_field in ARDA_FIELDS:
                    return code  # CNG exists, ADH might too
                return None
    
    # 3. Partial match on full denomination name (only exact containment)
    for denom, code in DENOM_TO_ARDA.items():
        dl = denom.lower()
        if dl == d_lower:
            return code
        # Only match if one fully contains the other (not partial word match)
        if len(dl) > 4 and len(d_lower) > 4:
            if dl in d_lower or d_lower in dl:
                return code
    
    return None

def phase2_compute():
    """Compute attendance for churches using ARDA county data."""
    log("Phase 2: Computing ARDA-based attendance...")
    
    # Load per-denomination ARDA data
    if not os.path.exists(PER_DENOM_CSV):
        log(f"  ERROR: {PER_DENOM_CSV} not found. Run --extract first.")
        return
    
    arda_data = {}
    with open(PER_DENOM_CSV, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            fips = row.get("FIPS", "").replace(".0", "")
            if fips:
                arda_data[fips] = row
    
    log(f"  Loaded ARDA data for {len(arda_data)} counties")
    
    db = sqlite3.connect(DB_PATH)
    cur = db.cursor()
    
    # Add attendance/membership columns if not exist
    cur.execute("PRAGMA table_info(churches)")
    cols = [col[1] for col in cur.fetchall()]
    
    new_cols = []
    if "attendance_arda" not in cols:
        cur.execute("ALTER TABLE churches ADD COLUMN attendance_arda INTEGER DEFAULT 0")
        new_cols.append("attendance_arda")
    if "attendance_source" not in cols:
        cur.execute("ALTER TABLE churches ADD COLUMN attendance_source TEXT DEFAULT ''")
        new_cols.append("attendance_source")
    if "attendance_computed" not in cols:
        cur.execute("ALTER TABLE churches ADD COLUMN attendance_computed INTEGER DEFAULT 0")
        new_cols.append("attendance_computed")
    if "members_arda" not in cols:
        cur.execute("ALTER TABLE churches ADD COLUMN members_arda INTEGER DEFAULT 0")
        new_cols.append("members_arda")
    if "members_source" not in cols:
        cur.execute("ALTER TABLE churches ADD COLUMN members_source TEXT DEFAULT ''")
        new_cols.append("members_source")
    if "attendance_est" not in cols:
        # Already exists but check
        pass
    
    if new_cols:
        log(f"  Added columns: {', '.join(new_cols)}")
    
    # Get all churches with county FIPS and denomination
    cur.execute("""
        SELECT id, denomination, county_fips_5, attendance_est 
        FROM churches 
        WHERE county_fips_5 != '' AND county_fips_5 IS NOT NULL
          AND denomination != '' AND denomination IS NOT NULL
    """)
    churches = cur.fetchall()
    log(f"  Processing {len(churches)} churches with FIPS + denomination")
    
    # Track stats
    stats = defaultdict(int)
    arda_codes_used = defaultdict(int)
    
    batch_updates = []
    BATCH_SIZE = 500
    
    for cid, denom, fips, current_att in churches:
        # Clean FIPS
        fips_clean = fips.replace(".0", "").strip()
        if fips_clean not in arda_data:
            continue
        
        county = arda_data[fips_clean]
        
        # Find matching ARDA denomination code
        arda_code = find_arda_code(denom)
        if not arda_code:
            continue
        
        # Get congregation and adherent counts
        cng_field = f"{arda_code}CNG_2020"
        adh_field = f"{arda_code}ADH_2020"
        
        try:
            cng = float(county.get(cng_field, 0) or 0)
            adh = float(county.get(adh_field, 0) or 0)
        except (ValueError, TypeError):
            continue
        
        if cng <= 0 or adh <= 0:
            continue
        
        arda_codes_used[arda_code] += 1
        
        if cng == 1:
            # Only one congregation of this type in the county
            # Attribute ALL adherents to this church
            attendance = int(adh)
            source = "arda_direct"
        else:
            # Multiple congregations - compute average
            attendance = max(1, int(adh / cng))
            source = "arda_computed"
        
        # Only update if we don't already have attendance data or it's from a lower-confidence source
        if current_att and current_att > 0:
            # Keep existing if it's already set
            continue
        
        batch_updates.append((attendance, source, cid))
        stats[source] += 1
        
        if len(batch_updates) >= BATCH_SIZE:
            cur.executemany(
                "UPDATE churches SET attendance_est=?, attendance_arda=?, attendance_source=? WHERE id=?",
                [(a, a, s, i) for a, s, i in batch_updates]
            )
            db.commit()
            batch_updates = []
    
    # Final batch
    if batch_updates:
        cur.executemany(
            "UPDATE churches SET attendance_est=?, attendance_arda=?, attendance_source=? WHERE id=?",
            [(a, a, s, i) for a, s, i in batch_updates]
        )
        db.commit()
    
    log(f"\n  Results:")
    log(f"    arda_direct (unique county match):   {stats['arda_direct']}")
    log(f"    arda_computed (averaged across county): {stats['arda_computed']}")
    log(f"  Total churches with ARDA attendance: {sum(stats.values())}")
    
    log(f"\n  ARDA denom codes used:")
    for code, cnt in sorted(arda_codes_used.items(), key=lambda x: -x[1])[:15]:
        log(f"    {code:6s}: {cnt:5d} churches")
    
    db.close()

def phase3_report():
    """Generate a report of what we computed."""
    log("Phase 3: Report...")
    db = sqlite3.connect(DB_PATH)
    cur = db.cursor()
    
    cur.execute("SELECT attendance_source, COUNT(*), SUM(attendance_est) FROM churches WHERE attendance_source != '' GROUP BY attendance_source")
    print("\n=== ATTENDANCE SOURCE BREAKDOWN ===")
    for src, cnt, total in cur.fetchall():
        avg = total / cnt if cnt else 0
        print(f"  {src:20s}: {cnt:6d} churches, {total:10d} total attendance, avg={avg:.0f}")
    
    cur.execute("SELECT COUNT(*), SUM(attendance_est) FROM churches WHERE attendance_source != ''")
    total_cnt, total_att = cur.fetchone()
    cur.execute("SELECT COUNT(*) FROM churches")
    all_churches = cur.fetchone()[0]
    print(f"\n  TOTAL with ARDA attendance: {total_cnt} / {all_churches} ({100*total_cnt/all_churches:.1f}%)")
    print(f"  TOTAL ARDA attendance sum: {int(total_att):,}")
    
    # Top denominations by ARDA coverage
    print("\n=== TOP DENOMINATIONS BY ARDA COVERAGE ===")
    cur.execute("""
        SELECT SUBSTR(denomination, 1, 40), COUNT(*), 
               SUM(CASE WHEN attendance_source != '' THEN 1 ELSE 0 END) as with_arda,
               SUM(CASE WHEN attendance_source = 'arda_direct' THEN 1 ELSE 0 END) as direct
        FROM churches 
        WHERE county_fips_5 != '' AND county_fips_5 IS NOT NULL
          AND denomination != '' AND denomination IS NOT NULL
        GROUP BY denomination
        HAVING COUNT(*) >= 5
        ORDER BY with_arda DESC
        LIMIT 20
    """)
    for denom, total, with_arda, direct in cur.fetchall():
        pct = 100 * with_arda / total if total else 0
        print(f"  {denom:40s}: {with_arda:5d}/{total:5d} ({pct:.0f}%) direct={direct}")
    
    db.close()

if __name__ == "__main__":
    args = sys.argv[1:] if len(sys.argv) > 1 else ["--all"]
    
    if "--extract" in args:
        phase1_extract()
    elif "--compute" in args:
        phase2_compute()
        phase3_report()
    elif "--report" in args:
        phase3_report()
    else:
        log("Starting full ARDA attendance pipeline")
        phase1_extract()
        phase2_compute()
        phase3_report()
        log("All phases complete!")
