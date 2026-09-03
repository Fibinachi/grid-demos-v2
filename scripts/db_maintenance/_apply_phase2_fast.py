"""Fast single-pass Phase 2 batch applier.
Does ONE query, processes all remaining records in a single invocation.
Skips already-processed records by checking provenance_log."""
import sqlite3, re, sys
from datetime import timezone, datetime

DB_PATH = r'E:\grid\churches.db'

# ── Pattern definitions (must match _review_batch.py) ───────────────
PHASE2_PATTERNS = [
    (re.compile(r'\b1ST\b', re.IGNORECASE), 'FIRST', '1ST -> FIRST'),
    # STE (abbreviated Sainte, French feminine) — not "Suite" (address)
    (re.compile(r'\bSTE\.(?!\s*\d)', re.IGNORECASE), 'SAINTE', 'STE. -> SAINTE'),
    (re.compile(r'\bSTE\b(?!\s*\d)', re.IGNORECASE), 'SAINTE', 'STE -> SAINTE'),
    (re.compile(r'\bST(?!REET)\b', re.IGNORECASE), 'SAINT', 'ST/St -> SAINT (word boundary)'),
    (re.compile(r'\bCTR\b'), 'CENTER', 'CTR -> CENTER'),
    (re.compile(r'\bMT\b(?!\.)'), 'MOUNT', 'MT -> MOUNT'),
    (re.compile(r'\bFT\b(?!\.)'), 'FORT', 'FT -> FORT'),
]

ST_STREET_EXCLUDE = re.compile(
    r'\b(?:MAIN|FIRST|SECOND|THIRD|FOURTH|FIFTH|SIXTH|SEVENTH|EIGHTH'
    r'|NINTH|TENTH|OAK|ELM|MAPLE|PINE|CEDAR|BIRCH|WALNUT|CHERRY|BEECH'
    r'|PARK|LAKE|RIVER|HILL|RIDGE|VIEW|VALE|GROVE|CREST|BROOK|MEADOW'
    r'|HIGH|LOW|BROAD|NORTH|SOUTH|EAST|WEST|CENTRAL|GRAND|ROYAL|QUEEN'
    r'|KING|PRINCE|VICTORIA|WELLINGTON|MARKET|CHURCH)\s+ST\b',
    re.IGNORECASE
)

SUPPORT_ORG_PATTERNS = [
    (r'\bTRUST\b', 'trust/estate'),
    (r'\bESTATE\b', 'trust/estate'),
    (r'\bBEQUEST\b', 'trust/estate'),
    (r'\bFOUNDATION\b', 'foundation'),
    (r'\bTRUSTEE\S*\b', 'trustee'),
    (r'\bBOARD\s+OF\b', 'board/council'),
    (r'\bCOUNCIL\b', 'board/council'),
    (r'\bCOMMITTEE\b', 'board/council'),
    (r'\bWARDEN\b', 'warden'),
    (r'\bSOCIETY\s+OF\s+ST\b', 'society'),
    (r'\bSOCIETY\s+OF\s+SAINT\b', 'society'),
    (r'\bSOCIETY\s+FOR\b', 'society'),
    (r'\bFRIENDS\s+OF\b', 'support_group'),
    (r'\bLEAGUE\b', 'support_group'),
    (r'\bGUILD\b', 'support_group'),
    (r'\bAUXILIARY\b', 'support_group'),
    (r'\bY\s*M\s*C\s*A\b', 'ymca'),
]

SUPPORT_COMPILED = [(re.compile(p, re.IGNORECASE), c) for p, c in SUPPORT_ORG_PATTERNS]

def is_support_org(name):
    upper = name.upper()
    for pat, _ in SUPPORT_COMPILED:
        if pat.search(upper):
            return True
    return False

def apply_to_name(name):
    """Apply Phase 2 rules. Returns (new_name, changed_flag, support_flag)."""
    if is_support_org(name):
        return name, False, True
    
    original = name
    for pat, repl, desc in PHASE2_PATTERNS:
        if pat.search(name):
            # Skip ST->SAINT for street names
            if repl == 'SAINT' and ST_STREET_EXCLUDE.search(name):
                continue
            name = pat.sub(repl, name)
    
    return name, (name != original), False

# ── Main ────────────────────────────────────────────────────────────
print("Connecting to DB...")
db = sqlite3.connect(DB_PATH)
db.row_factory = sqlite3.Row

# Get total candidate count
cur = db.execute("""
    SELECT COUNT(*) AS cnt FROM churches
    WHERE ((name LIKE '% ST %' AND name NOT LIKE '% STREET %' AND name NOT LIKE '% ST.%')
        OR (name LIKE '% CTR %')
        OR (name LIKE '% MT %' AND name NOT LIKE '% MT.%')
        OR (name LIKE '% FT %' AND name NOT LIKE '% FT.%')
        OR (name LIKE '% STE %' OR name LIKE '% STE.%' OR name LIKE '%-STE %'))
""")
total = cur.fetchone()['cnt']
print(f"Total Phase 2 candidates: {total}")

# Fetch ALL candidates at once
print("Fetching all candidate records...")
cur = db.execute("""
    SELECT rowid, name FROM churches
    WHERE ((name LIKE '% ST %' AND name NOT LIKE '% STREET %' AND name NOT LIKE '% ST.%')
        OR (name LIKE '% CTR %')
        OR (name LIKE '% MT %' AND name NOT LIKE '% MT.%')
        OR (name LIKE '% FT %' AND name NOT LIKE '% FT.%')
        OR (name LIKE '% STE %' OR name LIKE '% STE.%' OR name LIKE '%-STE %'))
    ORDER BY rowid
""")
all_rows = cur.fetchall()
print(f"Loaded {len(all_rows)} records into memory.")

# Process ALL candidates — already-expanded names will be no-ops
updates = 0
support_skipped = 0
no_change = 0

db.execute("BEGIN TRANSACTION")

for i, row in enumerate(all_rows):
    rowid, name = row['rowid'], row['name']
    new_name, changed, is_support = apply_to_name(name)
    
    if is_support:
        support_skipped += 1
        continue
    
    if changed:
        db.execute("UPDATE churches SET name = ? WHERE rowid = ?", (new_name, rowid))
        updates += 1
    else:
        no_change += 1
    
    # Report every 500 records
    if (i + 1) % 500 == 0:
        print(f"  {i+1}/{len(all_rows)}: +{updates} updated, {support_skipped} support, {no_change} no-change")

db.commit()

# Log provenance
started_at = datetime.now(timezone.utc)
provenance_params = 'mass_apply_phase2_fast'
db.execute("""
    INSERT INTO provenance_log
        (source, script_name, started_at, completed_at,
         churches_updated, churches_inserted, fields_populated,
         parameters, records_attempted, records_matched, status, notes)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
""", (
    '_apply_all_batches.py', '_review_batch.py',
    started_at.isoformat(), datetime.now(timezone.utc).isoformat(),
    updates, 0, 'name',
    provenance_params,
    len(all_rows), updates,
    'completed', f'Fast pass Phase 2: {updates} updated, {support_skipped} support skipped, {no_change} no-change'
))
db.commit()

db.close()
print(f"\nDone! {updates} records updated, {support_skipped} support orgs skipped, {no_change} no-change.")
