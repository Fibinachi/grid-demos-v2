"""
Fix synagogue/jewish faith mis-tags.
Only re-tags entries with CLEAR Jewish indicators and NO Christian indicators.
"""
import sqlite3
from datetime import datetime, timezone
from collections import Counter

DB = 'churches.db'
NOW = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')

# Clear Jewish indicators (lowercase matching)
JEWISH_PATTERNS = [
    'synagogue', 'chabad', 'hillel',
    'temple beth', 'temple israel', 'temple sinai', 'temple emanuel',
    'temple shalom', 'temple bnai', 'temple emanu',
    'congregation beth', 'congregation bnai', "congregation b'nai",
    'congregation adath', 'congregation agudas',
    'congregation shaare', 'congregation kehil',
    'jewish center', 'jewish centre', 'jcc ',
    'yeshiva', 'yeshivah',
]

# Christian indicators to EXCLUDE
CHRISTIAN_PATTERNS = [
    'church', 'iglesia', 'assembly of god',
    'lutheran', 'baptist', 'methodist', 'presbyterian',
    'pentecostal', 'catholic', 'episcopal', 'evangelical',
    'adventist', 'ministries', 'gospel', 'christian',
    'fellowship',
]

db = sqlite3.connect(DB)
db.execute("PRAGMA busy_timeout=30000")
c = db.cursor()

# Step 1: Find all candidates
all_candidates = []
for pattern in JEWISH_PATTERNS:
    c.execute("SELECT rowid, name, faith_tradition FROM churches WHERE name LIKE ?", (f'%{pattern}%',))
    all_candidates.extend(c.fetchall())

# Deduplicate
seen = set()
candidates = []
for rowid, name, faith in all_candidates:
    if rowid not in seen:
        seen.add(rowid)
        candidates.append((rowid, name, faith))

print(f"Candidates with Jewish name patterns: {len(candidates):,}")

# Step 2: Filter
need_fix = []
for rowid, name, faith in candidates:
    faith_lower = (faith or '').lower()
    # Skip already correctly tagged
    if any(w in faith_lower for w in ('jew', 'juda', 'synag', 'israel')):
        continue
    
    name_lower = name.lower()
    # Skip if any Christian indicator present
    if any(p in name_lower for p in CHRISTIAN_PATTERNS):
        continue
    
    need_fix.append((rowid, name, faith))

print(f"After filtering (already correct + Christian): {len(need_fix):,}")

# Step 3: Show samples
print("\nSample fixes:")
for rowid, name, old_faith in need_fix[:25]:
    print(f"  {rowid} | {str(old_faith or 'NULL'):20s} -> Jewish | {name[:70]}")
if len(need_fix) > 25:
    print(f"  ... and {len(need_fix)-25} more")

# Step 4: Breakdown
old_faith_counts = Counter(str(f or 'NULL') for _, _, f in need_fix)
print("\nOld faith distribution:")
for faith, cnt in old_faith_counts.most_common(15):
    print(f"  {faith:25s} | {cnt:,}")

# Step 5: Apply
if need_fix:
    print(f"\nApplying {len(need_fix):,} fixes...")
    for rowid, name, old_faith in need_fix:
        c.execute("UPDATE churches SET faith_tradition='Jewish' WHERE rowid=?", (rowid,))
    db.commit()
    
    c.execute("""INSERT INTO provenance_log 
    (source, script_name, started_at, completed_at, churches_updated, fields_populated, status, notes) 
    VALUES (?,?,?,?,?,?,?,?)""",
        ('synagogue_faith_fix', 'fix_synagogue_faith.py', NOW, NOW,
         len(need_fix), 'faith_tradition', 'completed',
         f'Fixed {len(need_fix):,} synagogues/Jewish orgs mis-tagged with non-Jewish faith. '
         f'Conservative: Jewish name patterns without Christian indicators.'))
    db.commit()
    print(f"Fixed {len(need_fix):,} entries. Provenance logged.")

db.close()
print("Done.")
