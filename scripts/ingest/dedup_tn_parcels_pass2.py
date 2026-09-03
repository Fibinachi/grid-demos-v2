"""
Second-pass TN parcel dedup with faster fuzzy name matching.
Builds a word index for O(1) lookups instead of O(n*m) Jaccard.
"""
import sqlite3, sys, re
from datetime import datetime, timezone
from collections import defaultdict

DB = 'churches.db'
TN_DB = 'data/tn_parcels/tn_religious_parcels.db'
DRY_RUN = '--dry-run' in sys.argv
NOW = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')

db = sqlite3.connect(DB)
c = db.cursor()
tndb = sqlite3.connect(TN_DB)
tc = tndb.cursor()

print("=" * 70)
print("TN PARCELS DEDUP — PASS 2 (word-index fuzzy)")
print("=" * 70)
print(f"DRY RUN: {DRY_RUN}")

def clean_city(raw):
    if not raw: return ''
    return re.sub(r'^\d+\s+', '', raw).strip().lower()

def sig_words(s):
    if not s: return set()
    s = s.strip().upper()
    s = re.sub(r'[^A-Z0-9\s]', ' ', s)
    s = re.sub(r'\s+', ' ', s).strip()
    noise = {'THE','OF','AND','A','AN','IN','AT','FOR','INC','LTD','CO',
             'BPST','BAPTISIT','CHURCH','TEMPLE','CHAPEL','CATHEDRAL'}
    return {w for w in s.split() if w not in noise and len(w) > 2}

# Step 1: Build word index
print("\n--- Step 1: Build word index ---")
cur = c.execute("SELECT rowid, name, city FROM churches WHERE country='US' AND state='TN'")
existing = cur.fetchall()
print(f"  Existing TN churches: {len(existing):,}")

word_index = defaultdict(list)
for rowid, name, city in existing:
    ccity = clean_city(city)
    for w in sig_words(name):
        word_index[w].append((rowid, ccity))

# Also index owner names from already-linked parcels for cross-ref
cur2 = tc.execute("SELECT tn_owner_raw, grid_church_id FROM tn_religious_parcels WHERE grid_church_id IS NOT NULL AND tn_owner_raw IS NOT NULL")
owner_index = defaultdict(list)
for owner, grid_id in cur2.fetchall():
    for w in sig_words(owner):
        owner_index[w].append(grid_id)

print(f"  Word index: {len(word_index):,} words, {len(owner_index):,} owner words")

# Step 2: Get unlinked parcels
cur = tc.execute("""
    SELECT id, name, city, zip, tn_owner_raw
    FROM tn_religious_parcels
    WHERE grid_church_id IS NULL AND landmark_type IN ('church', 'parsonage')
      AND name IS NOT NULL AND name != ''
""")
parcels = cur.fetchall()
print(f"  Unlinked parcels with names: {len(parcels):,}")

# Step 3: Match by word overlap
print("\n--- Step 3: Matching ---")
new_matches = []

for p in parcels:
    pid, pname, pcity_raw, pzip, powner = p
    pcity = clean_city(pcity_raw)
    
    pwords = sig_words(pname)
    if powner:
        pwords |= sig_words(powner)
    if not pwords:
        continue
    
    # Score candidates by shared word count (with city bonus)
    candidates = defaultdict(float)
    for w in pwords:
        for church_rowid, church_city in word_index.get(w, []):
            bonus = 1.5 if church_city == pcity else 1.0
            candidates[church_rowid] += bonus
    
    if not candidates:
        continue
    
    best_rowid = max(candidates, key=candidates.get)
    best_score = candidates[best_rowid]
    
    if best_score >= 2.0:
        new_matches.append((pid, best_rowid, best_score))

print(f"  Matched: {len(new_matches):,}")

# Step 4: Update
if new_matches and not DRY_RUN:
    updated = 0
    for pid, church_rowid, score in new_matches:
        tc.execute("UPDATE tn_religious_parcels SET grid_church_id = ? WHERE id = ?", (church_rowid, pid))
        if tc.rowcount > 0:
            updated += 1
    tndb.commit()
    print(f"  Updated {updated:,} links")
    db.execute("PRAGMA wal_checkpoint(TRUNCATE)")
    print("  WAL checkpointed")

# Summary
linked = tc.execute("SELECT COUNT(*) FROM tn_religious_parcels WHERE grid_church_id IS NOT NULL").fetchone()[0]
remaining = tc.execute("SELECT COUNT(*) FROM tn_religious_parcels WHERE grid_church_id IS NULL AND landmark_type='church'").fetchone()[0]
print(f"\nTotal linked: {linked:,} | Unlinked: {remaining:,}")

db.close()
tndb.close()
