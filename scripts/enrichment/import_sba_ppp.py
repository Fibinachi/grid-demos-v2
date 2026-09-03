"""
SBA PPP Loan Import
===================
Downloads SBA PPP FOIA data, filters to religious orgs (NAICS 813110),
matches by EIN to existing churches, enriches matched records,
and inserts unmatched as new church candidates.

Pipeline:
  1. EIN match → church_external_ids(source='ein') → enrich ppp_loans table
  2. Unmatched EINs → fuzzy name+ZIP match → link + enrich
  3. Still unmatched → new church records with PPP loan data

Source: https://data.sba.gov/dataset/ppp-foia
"""
import csv, io, os, sys, sqlite3, time, urllib.request, zipfile, gzip
from datetime import datetime, timezone
from pathlib import Path
from difflib import SequenceMatcher

PROJECT = Path(__file__).resolve().parent.parent.parent
DATA_DIR = PROJECT / "data" / "sba"
DATA_DIR.mkdir(parents=True, exist_ok=True)
DB_PATH = PROJECT / "churches.db"

# SBA PPP FOIA URLs (latest: Sept 2024 release)
# SBA PPP FOIA URLs (Sept 2024 release — URLs updated 2026-07-02)
PPP_UNDER_150K_URLS = [
    "https://data.sba.gov/dataset/ppp-foia/resource/cff06664-1f75-4969-ab3d-6fa7d6b4c41e/download/public_up_to_150k_1_240930.csv",
    "https://data.sba.gov/dataset/ppp-foia/resource/1e6b6629-a5aa-46e6-a442-6e67366d2362/download/public_up_to_150k_2_240930.csv",
    "https://data.sba.gov/dataset/ppp-foia/resource/644c304a-f5ad-4cfa-b128-fe2cbcb7b26e/download/public_up_to_150k_3_240930.csv",
    "https://data.sba.gov/dataset/ppp-foia/resource/98af633d-eb1b-4d4b-995d-330962e6c38d/download/public_up_to_150k_4_240930.csv",
    "https://data.sba.gov/dataset/ppp-foia/resource/3b407e04-f269-47a0-a5fe-661d1a08a76c/download/public_up_to_150k_5_240930.csv",
    "https://data.sba.gov/dataset/ppp-foia/resource/7b7b5b58-9645-4b88-a675-a8a825e77076/download/public_up_to_150k_6_240930.csv",
    "https://data.sba.gov/dataset/ppp-foia/resource/dabdddb5-1807-44f6-97c6-d624a5372525/download/public_up_to_150k_7_240930.csv",
    "https://data.sba.gov/dataset/ppp-foia/resource/1fc6ddc4-ccb0-49d4-b632-0749e3292e57/download/public_up_to_150k_8_240930.csv",
    "https://data.sba.gov/dataset/ppp-foia/resource/e9f2c718-b95e-47da-8f3e-17154aab1c86/download/public_up_to_150k_9_240930.csv",
    "https://data.sba.gov/dataset/ppp-foia/resource/d9972f0d-c377-46ac-8637-a5c1265377c8/download/public_up_to_150k_10_240930.csv",
    "https://data.sba.gov/dataset/ppp-foia/resource/8db19ddc-f036-40df-89f9-d0d309aa58b5/download/public_up_to_150k_11_240930.csv",
    "https://data.sba.gov/dataset/ppp-foia/resource/7e4f672f-d163-4735-a5ec-f23afa2835db/download/public_up_to_150k_12_240930.csv",
]
PPP_OVER_150K = "https://data.sba.gov/dataset/ppp-foia/resource/c1275a03-c25c-488a-bd95-403c4b2fa036/download/public_150k_plus_240930.csv"

NAICS_RELIGIOUS = "813110"

def progress_bar(i, total, start, label=""):
    if total == 0: return
    elapsed = time.time() - start
    rate = (i + 1) / elapsed if elapsed > 0 else 0
    eta = (total - i - 1) / rate / 60 if rate > 0 else 0
    pct = (i + 1) / total * 100
    bar_len = 30
    filled = int(bar_len * (i + 1) / total)
    bar = chr(0x2588) * filled + chr(0x2591) * (bar_len - filled)
    print(f"\r    {bar} {i+1:,}/{total:,} ({pct:.0f}%) "
          f"rate={rate:.0f}/s ETA={eta:.0f}m {label}", end="", flush=True)

def download_and_filter(url, label, naics_filter=NAICS_RELIGIOUS):
    """Stream-download PPP CSV and filter to religious orgs only."""
    fname = url.split("/")[-1]
    cache_path = DATA_DIR / f"ppp_religious_{fname}"

    if cache_path.exists():
        print(f"  Using cached: {cache_path.name} ({cache_path.stat().st_size/1e6:.0f}MB)")
        rows = []
        with open(cache_path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                rows.append(row)
        return rows

    print(f"  Downloading {label} ...", end="", flush=True)
    req = urllib.request.Request(url, headers={"User-Agent": "GRID/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=300) as resp:
            raw = resp.read()
    except Exception as e:
        print(f" FAILED: {e}")
        return []

    # Parse and filter
    print(f" {len(raw)/1e6:.0f}MB, filtering...", end="", flush=True)
    reader = csv.DictReader(io.StringIO(raw.decode("utf-8", errors="replace")))
    rows = []
    for row in reader:
        naics = row.get("NAICSCode", row.get("NAICS", ""))
        if str(naics).startswith("813"):
            rows.append(row)

    # Cache filtered results
    with open(cache_path, "w", encoding="utf-8", newline="") as f:
        if rows:
            w = csv.DictWriter(f, fieldnames=rows[0].keys())
            w.writeheader()
            w.writerows(rows)

    print(f" {len(rows):,} religious orgs")
    return rows

def normalize_ein(ein):
    """Normalize EIN to XX-XXXXXXX format."""
    ein = str(ein).strip().replace("-", "").replace(" ", "")
    if len(ein) == 9:
        return f"{ein[:2]}-{ein[2:]}"
    return ein

def create_tables(db):
    """Create ppp_loans table."""
    db.execute("""
        CREATE TABLE IF NOT EXISTS sba_ppp_loans (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            loan_number TEXT,
            ein TEXT,
            borrower_name TEXT,
            borrower_address TEXT,
            borrower_city TEXT,
            borrower_state TEXT,
            borrower_zip TEXT,
            naics_code TEXT,
            business_type TEXT,
            loan_amount REAL,
            jobs_reported INTEGER,
            date_approved TEXT,
            lender_name TEXT,
            forgiveness_amount REAL,
            forgiveness_date TEXT,
            church_id INTEGER,
            match_method TEXT,
            match_confidence REAL,
            loaded_at TEXT DEFAULT (datetime('now')),
            FOREIGN KEY (church_id) REFERENCES churches(id)
        )
    """)
    db.execute("CREATE INDEX IF NOT EXISTS idx_ppp_ein ON sba_ppp_loans(ein)")
    db.execute("CREATE INDEX IF NOT EXISTS idx_ppp_church ON sba_ppp_loans(church_id)")
    db.execute("CREATE INDEX IF NOT EXISTS idx_ppp_naics ON sba_ppp_loans(naics_code)")
    db.commit()

def load_ppp_data(db, rows):
    """Batch insert PPP loan data."""
    # Clear existing religious PPP data before reload
    db.execute("DELETE FROM sba_ppp_loans WHERE naics_code LIKE '813%'")
    db.commit()

    cols = [
        "loan_number", "ein", "borrower_name", "borrower_address",
        "borrower_city", "borrower_state", "borrower_zip", "naics_code",
        "business_type", "loan_amount", "jobs_reported", "date_approved",
        "lender_name", "forgiveness_amount", "forgiveness_date"
    ]

    sql = f"""INSERT INTO sba_ppp_loans
        ({','.join(cols)})
        VALUES ({','.join(['?']*len(cols))})"""

    batch = []
    start = time.time()
    total = len(rows)

    for i, row in enumerate(rows):
        # Map SBA column names (they changed over time)
        ein = normalize_ein(row.get("BorrowerEIN", row.get("EIN", "")))
        loan_num = row.get("LoanNumber", row.get("SBAGuaranty", ""))
        name = row.get("BorrowerName", row.get("Borrower", ""))
        addr = row.get("BorrowerAddress", row.get("Address", ""))
        city = row.get("BorrowerCity", row.get("City", ""))
        state = row.get("BorrowerState", row.get("State", ""))
        zip5 = (row.get("BorrowerZip", row.get("Zip", "")) or "")[:5]
        naics = row.get("NAICSCode", row.get("NAICS", ""))
        biz_type = row.get("BusinessType", "")
        loan_amt = float(row.get("CurrentApprovalAmount", row.get("InitialApprovalAmount", 0)) or 0)
        jobs = int(float(row.get("JobsReported", 0) or 0))
        date_app = row.get("DateApproved", "")
        lender = row.get("OriginatingLender", row.get("Lender", ""))
        forgive_amt = float(row.get("ForgivenessAmount", 0) or 0)
        forgive_date = row.get("ForgivenessDate", "")

        batch.append((
            loan_num, ein, name, addr, city, state, zip5,
            naics, biz_type, loan_amt, jobs, date_app, lender,
            forgive_amt, forgive_date
        ))

        if len(batch) >= 5000:
            db.executemany(sql, batch)
            db.commit()
            batch = []
            progress_bar(i, total, start)

    if batch:
        db.executemany(sql, batch)
        db.commit()

    elapsed = time.time() - start
    progress_bar(total - 1, total, start, f"done {elapsed:.0f}s")
    print()

def match_by_ein(db):
    """Match PPP loans to churches by EIN."""
    print("\n  === EIN MATCHING ===")
    # Get all PPP EINs
    cur = db.execute("SELECT DISTINCT ein FROM sba_ppp_loans WHERE naics_code LIKE '813%' AND ein IS NOT NULL AND ein != ''")
    ppp_eins = set(r[0] for r in cur.fetchall())
    print(f"  PPP religious EINs: {len(ppp_eins):,}")

    # Get all church EINs
    cur = db.execute("SELECT id_value, church_id FROM church_external_ids WHERE source='ein'")
    church_eins = {}
    for ein_val, church_id in cur.fetchall():
        norm = normalize_ein(ein_val)
        if norm in church_eins:
            # Multiple churches with same EIN? Skip ambiguous
            church_eins[norm] = None
        else:
            church_eins[norm] = church_id

    # Remove ambiguous
    church_eins = {k: v for k, v in church_eins.items() if v is not None}
    print(f"  Church EINs (unambiguous): {len(church_eins):,}")

    # Match
    matched = 0
    new_links = 0
    for ein in ppp_eins:
        if ein in church_eins:
            church_id = church_eins[ein]
            db.execute(
                "UPDATE sba_ppp_loans SET church_id=?, match_method='ein_exact', match_confidence=1.0 WHERE ein=? AND church_id IS NULL",
                (church_id, ein)
            )
            matched += 1

    db.commit()
    print(f"  EIN-matched: {matched:,} PPP loans linked to churches")

def fuzzy_match_unmatched(db):
    """For unmatched PPP loans, try name + ZIP fuzzy match."""
    print("\n  === FUZZY MATCHING ===")
    cur = db.execute("""
        SELECT p.id, p.borrower_name, p.borrower_zip, p.borrower_state
        FROM sba_ppp_loans p
        WHERE p.church_id IS NULL AND p.borrower_name IS NOT NULL
          AND p.naics_code LIKE '813%'
    """)
    unmatched = cur.fetchall()
    print(f"  Unmatched PPP loans: {len(unmatched):,}")

    if len(unmatched) == 0:
        return

    # Load US churches without EINs for potential matching
    cur = db.execute("""
        SELECT c.id, c.name, c.zip5, c.state FROM churches c
        WHERE c.country='US' AND c.zip5 IS NOT NULL AND c.zip5 != ''
          AND c.id NOT IN (SELECT DISTINCT church_id FROM sba_ppp_loans WHERE church_id IS NOT NULL)
    """)
    church_pool = cur.fetchall()
    print(f"  Church fuzzy-match pool: {len(church_pool):,}")

    # Build ZIP index
    zip_index = {}
    for ch_id, name, zip5, state in church_pool:
        if zip5:
            zip_index.setdefault(zip5, []).append((ch_id, name, state))

    matched = 0
    start = time.time()
    for i, (ppp_id, ppp_name, ppp_zip, ppp_state) in enumerate(unmatched):
        candidates = zip_index.get(ppp_zip, [])
        best_score = 0
        best_church = None

        for ch_id, ch_name, ch_state in candidates:
            # Compute name similarity
            score = SequenceMatcher(None,
                ppp_name.lower().strip(),
                ch_name.lower().strip()
            ).ratio()
            # Bonus for same state
            if ppp_state and ch_state and ppp_state.upper() == ch_state.upper():
                score += 0.05
            if score > best_score:
                best_score = score
                best_church = ch_id

        if best_score >= 0.85 and best_church:
            db.execute(
                "UPDATE sba_ppp_loans SET church_id=?, match_method='fuzzy_name_zip', match_confidence=? WHERE id=?",
                (best_church, round(best_score, 3), ppp_id)
            )
            matched += 1

        if (i + 1) % 5000 == 0:
            progress_bar(i, len(unmatched), start)

    db.commit()
    elapsed = time.time() - start
    progress_bar(len(unmatched) - 1, len(unmatched), start, f"done {elapsed:.0f}s")
    print()
    print(f"  Fuzzy-matched: {matched:,} additional PPP loans linked")

def insert_new_churches(db):
    """Insert unmatched PPP religious orgs as new church records."""
    print("\n  === NEW CHURCH CANDIDATES ===")

    # Get next church ID
    cur = db.execute("SELECT MAX(id) FROM churches")
    max_id = cur.fetchone()[0] or 0

    # PPP under-$150K has no EINs — group by name+ZIP+state instead
    cur = db.execute("""
        SELECT borrower_name, borrower_address, borrower_city,
               borrower_state, borrower_zip, ein, naics_code,
               loan_amount, jobs_reported
        FROM sba_ppp_loans
        WHERE church_id IS NULL AND naics_code = '813110'
          AND borrower_name IS NOT NULL
        GROUP BY UPPER(borrower_name), borrower_zip, borrower_state
    """)
    candidates = cur.fetchall()
    print(f"  Candidates: {len(candidates):,}")

    if len(candidates) == 0:
        return

    new_count = 0
    skipped = 0
    start = time.time()

    for i, (name, addr, city, state, zip5, ein, naics, loan_amt, jobs) in enumerate(candidates):
        # Check if name matches an existing church (deeper check)
        cur = db.execute("""
            SELECT id FROM churches
            WHERE name LIKE ? AND zip5=? AND country='US'
        """, (f"%{name[:30]}%", zip5))
        existing = cur.fetchone()
        if existing:
            # Link it
            db.execute(
                "UPDATE sba_ppp_loans SET church_id=?, match_method='name_exact_late', match_confidence=0.95 WHERE ein=?",
                (existing[0], ein)
            )
            skipped += 1
            continue

        # Insert new church
        max_id += 1
        db.execute("""
            INSERT INTO churches (id, name, address, city, state, zip5, country, faith,
                                  source, landmark_type, taxonomy_id)
            VALUES (?, ?, ?, ?, ?, ?, 'US', 'Christian', 'sba_ppp', 'church', 2)
        """, (max_id, name, addr, city, state, zip5))

        # Add EIN
        db.execute("""
            INSERT OR IGNORE INTO church_external_ids (church_id, source, id_value)
            VALUES (?, 'ein', ?)
        """, (max_id, ein))

        # Link PPP loan — match on name+zip+state since EINs are empty
        db.execute(
            "UPDATE sba_ppp_loans SET church_id=?, match_method='new_church_insert', match_confidence=1.0 "
            "WHERE UPPER(borrower_name)=UPPER(?) AND borrower_zip=? AND borrower_state=? AND church_id IS NULL",
            (max_id, name, zip5, state)
        )

        new_count += 1

        if (i + 1) % 1000 == 0:
            db.commit()
            progress_bar(i, len(candidates), start)

    db.commit()
    elapsed = time.time() - start
    progress_bar(len(candidates) - 1, len(candidates), start, f"done {elapsed:.0f}s")
    print()
    print(f"  New churches: {new_count:,}  |  Late-matched: {skipped:,}")

def find_shared_address_orgs(db):
    """Find non-church PPP recipients sharing an address with a church."""
    print("\n  === SHARED ADDRESS ORGS ===")
    
    db.execute("""
        CREATE TABLE IF NOT EXISTS church_related_ppp (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            church_id INTEGER,
            related_name TEXT,
            related_naics TEXT,
            related_loan_amount REAL,
            related_jobs INTEGER,
            shared_address TEXT,
            relationship_type TEXT,
            loaded_at TEXT DEFAULT (datetime('now')),
            FOREIGN KEY (church_id) REFERENCES churches(id)
        )
    """)
    db.execute("CREATE INDEX IF NOT EXISTS idx_relppp_church ON church_related_ppp(church_id)")
    db.commit()
    
    # Get all church addresses from PPP
    cur = db.execute("""
        SELECT c.id, p.borrower_address, p.borrower_zip, p.borrower_state
        FROM sba_ppp_loans p
        JOIN churches c ON p.church_id = c.id
        WHERE p.borrower_address IS NOT NULL AND p.borrower_address != ''
          AND p.naics_code = '813110'
        GROUP BY c.id, p.borrower_address, p.borrower_zip, p.borrower_state
    """)
    church_addrs = cur.fetchall()
    print(f"  Church addresses to check: {len(church_addrs):,}")
    
    if len(church_addrs) == 0:
        return
    
    # Build address lookup
    related = 0
    start = time.time()
    
    for i, (ch_id, addr, zip5, state) in enumerate(church_addrs):
        # Find non-813110 PPP entries at same address
        cur = db.execute("""
            SELECT borrower_name, naics_code, SUM(loan_amount), SUM(jobs_reported)
            FROM sba_ppp_loans
            WHERE borrower_address = ? AND borrower_zip = ?
              AND naics_code NOT LIKE '813%'
              AND naics_code IS NOT NULL AND naics_code != ''
            GROUP BY borrower_name, naics_code
        """, (addr, zip5))
        matches = cur.fetchall()
        
        for name, naics, loan, jobs in matches:
            # Classify relationship type
            rel_type = classify_relationship(naics, name)
            db.execute("""
                INSERT OR IGNORE INTO church_related_ppp
                (church_id, related_name, related_naics, related_loan_amount, related_jobs, shared_address, relationship_type)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (ch_id, name, naics, loan or 0, jobs or 0, addr, rel_type))
            related += 1
        
        if (i + 1) % 500 == 0:
            db.commit()
            progress_bar(i, len(church_addrs), start)
    
    db.commit()
    elapsed = time.time() - start
    progress_bar(len(church_addrs)-1, len(church_addrs), start, f"done {elapsed:.0f}s")
    print()
    
    cur = db.execute("SELECT COUNT(*), COUNT(DISTINCT church_id) FROM church_related_ppp")
    total_rel, churches_with = cur.fetchone()
    print(f"  Shared-address orgs: {total_rel:,} across {churches_with:,} churches")
    
    cur = db.execute("""
        SELECT relationship_type, COUNT(*) FROM church_related_ppp
        GROUP BY relationship_type ORDER BY COUNT(*) DESC LIMIT 10
    """)
    for rtype, count in cur.fetchall():
        print(f"    {rtype:30s} {count:,}")

def classify_relationship(naics, name):
    """Classify what kind of related organization this is."""
    naics = str(naics)[:6]
    name_lower = name.lower()
    
    if naics in ('624410', '624110', '624120'): return 'child_daycare'
    if naics in ('624210', '624221', '624230'): return 'food_shelter'
    if naics in ('611110', '611210', '611310'): return 'school'
    if naics in ('624190', '624310'): return 'social_services'
    if naics in ('621111', '621112', '621410'): return 'health_clinic'
    if naics in ('813410', '813910'): return 'civic_association'
    if naics.startswith('611'): return 'education'
    if naics.startswith('624'): return 'social_assistance'
    if naics.startswith('621'): return 'healthcare'
    if naics.startswith('813'): return 'other_nonprofit'
    if 'daycare' in name_lower or 'day care' in name_lower: return 'child_daycare'
    if 'academy' in name_lower or 'school' in name_lower: return 'school'
    if 'food' in name_lower or 'pantry' in name_lower or 'shelter' in name_lower: return 'food_shelter'
    if 'ministr' in name_lower or 'outreach' in name_lower: return 'ministry'
    return 'other'

def main():
    print(f"\n{'='*60}")
    print(f"  SBA PPP Loan Import — Religious Orgs (NAICS 813110)")
    print(f"{'='*60}")

    # Download all under-$150K files
    print("\n  --- DOWNLOAD ---")
    all_rows = []
    for k, url in enumerate(PPP_UNDER_150K_URLS, 1):
        rows = download_and_filter(url, f"PPP <$150K (#{k}/12)")
        all_rows.extend(rows)
    rows_over = download_and_filter(PPP_OVER_150K, "PPP >$150K")
    all_rows.extend(rows_over)
    print(f"  Total religious PPP loans: {len(all_rows):,}")

    if not all_rows:
        print("  No data. Exiting.")
        return

    # Load
    db = sqlite3.connect(str(DB_PATH))
    db.execute("PRAGMA journal_mode=WAL")
    db.execute("PRAGMA busy_timeout=30000")
    create_tables(db)

    print("\n  --- LOAD ---")
    load_ppp_data(db, all_rows)

    # Match
    match_by_ein(db)
    fuzzy_match_unmatched(db)

    # New churches
    insert_new_churches(db)

    # Shared-address organizations (daycares, food pantries, etc.)
    find_shared_address_orgs(db)

    # Summary
    cur = db.execute("""
        SELECT
            COUNT(*) AS total,
            SUM(CASE WHEN church_id IS NOT NULL THEN 1 ELSE 0 END) AS matched,
            SUM(CASE WHEN church_id IS NULL THEN 1 ELSE 0 END) AS unmatched,
            COUNT(DISTINCT church_id) AS unique_churches,
            SUM(loan_amount) AS total_loan_amt
        FROM sba_ppp_loans WHERE naics_code LIKE '813%'
    """)
    total, matched_count, unmatched_count, unique_churches, total_loan = cur.fetchone()

    cur = db.execute("SELECT match_method, COUNT(*) FROM sba_ppp_loans WHERE church_id IS NOT NULL GROUP BY match_method")
    methods = cur.fetchall()

    print(f"\n{'='*60}")
    print(f"  Results")
    print(f"{'='*60}")
    print(f"  Total PPP religious loans: {total:,}")
    print(f"  Matched to churches:     {matched_count:,} ({100*matched_count/total:.1f}%)")
    print(f"  Unique churches linked:  {unique_churches:,}")
    print(f"  Unmatched:               {unmatched_count:,}")
    print(f"  Total loan amount:       ${total_loan/1e9:.1f}B")
    print(f"\n  Match methods:")
    for method, count in methods:
        print(f"    {method}: {count:,}")

    # New churches added
    cur = db.execute("SELECT COUNT(*) FROM churches WHERE source='sba_ppp'")
    new_churches = cur.fetchone()[0]
    print(f"\n  New churches added: {new_churches:,}")

    # Provenance
    db.execute("""
        INSERT INTO provenance_log
        (source, script_name, started_at, completed_at, churches_updated, churches_inserted, status, notes)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        "sba_ppp", "import_sba_ppp.py",
        datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        unique_churches, new_churches, "completed",
        f"PPP FOIA Sept 2024. {total:,} religious loans, {matched_count:,} matched, "
        f"{new_churches:,} new churches. ${total_loan/1e9:.1f}B total."
    ))
    db.commit()
    db.close()

    print(f"\n  Done.")
    print(f"{'='*60}\n")

if __name__ == "__main__":
    main()
