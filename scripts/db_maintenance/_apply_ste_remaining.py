"""Apply Phase 2 to remaining unexpanded records (French Ste patterns)."""
import sqlite3, re
from datetime import timezone, datetime

DB_PATH = r'E:\grid\churches.db'

PHASE2_IGNORE = [
    (re.compile(r'\bSTE\.(?!\s*\d)', re.IGNORECASE), 'SAINTE', 'STE. -> SAINTE'),
    (re.compile(r'\bSTE\b(?!\s*\d)', re.IGNORECASE), 'SAINTE', 'STE -> SAINTE'),
]

SUPPORT_PATTERNS = [
    (re.compile(r'\bTRUST\b'), 'trust'), (re.compile(r'\bESTATE\b'), 'estate'),
    (re.compile(r'\bFOUNDATION\b'), 'foundation'), (re.compile(r'\bTRUSTEE\S*\b'), 'trustee'),
    (re.compile(r'\bBOARD\s+OF\b'), 'board'), (re.compile(r'\bCOUNCIL\b'), 'council'),
    (re.compile(r'\bSOCIETY\s+OF\s+ST\b'), 'society'), (re.compile(r'\bSOCIETY\s+OF\s+SAINT\b'), 'society'),
]

def is_support(name):
    u = name.upper()
    for p, _ in SUPPORT_PATTERNS:
        if p.search(u):
            return True
    return False

db = sqlite3.connect(DB_PATH)

# Find all records with unexpanded STE (any case) 
rows = db.execute("""
    SELECT rowid, name FROM churches
    WHERE (name LIKE '% STE %' OR name LIKE '% STE.%')
      AND name NOT LIKE '% SAINTE %'
    ORDER BY rowid
""").fetchall()

print(f"Remaining unexpanded STE records: {len(rows)}")

updates = 0
support = 0
no_change = 0
db.execute("BEGIN")

for rowid, name in rows:
    if is_support(name):
        support += 1
        continue
    
    original = name
    for pat, repl, desc in PHASE2_IGNORE:
        if pat.search(name):
            name = pat.sub(repl, name)
    
    if name != original:
        db.execute("UPDATE churches SET name = ? WHERE rowid = ?", (name, rowid))
        updates += 1
    else:
        no_change += 1

db.commit()

# Log provenance
db.execute("""INSERT INTO provenance_log(source,script_name,started_at,completed_at,
    churches_updated,churches_inserted,fields_populated,parameters,records_attempted,records_matched,status,notes)
    VALUES(?,?,?,?,?,?,?,?,?,?,?,?)""",
    ('_apply_phase2_fast.py','_review_batch.py',
     datetime.now(timezone.utc).isoformat(), datetime.now(timezone.utc).isoformat(),
     updates, 0, 'name', 'phase2_ste_remaining',
     len(rows), updates, 'completed',
     f'STE catch-up (IGNORECASE): {updates} updated, {support} support, {no_change} no-change'))
db.commit()

db.close()
print(f"Done: {updates} updated, {support} support, {no_change} no-change")
