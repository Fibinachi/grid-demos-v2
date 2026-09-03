"""
Classify Jain entries in churches.db — tradition (Digambar/Shwetambar/Sthanakvasi/Mixed),
sub-traditions, and landmark type refinement.

7,530 entries — enough for meaningful DeepSeek batch processing.
"""
import sqlite3, re, json, time
from pathlib import Path
from collections import Counter

DB = "churches.db"
BATCH_SIZE = 500
OUT = Path("outputs/enrichment")
OUT.mkdir(parents=True, exist_ok=True)

# Step 1: SQL-based pre-classification using name patterns
print("=== Pre-classifying Jain entries by name patterns ===")

db = sqlite3.connect(DB)
db.row_factory = sqlite3.Row

# Get all Jain entries that need classification
entries = db.execute("""
    SELECT id, name, landmark_type, tradition, source
    FROM churches
    WHERE faith = 'Jain'
      AND (tradition IS NULL OR tradition = 'Jain' OR tradition = '')
    ORDER BY id
""").fetchall()

print(f"Jain entries needing classification: {len(entries)}")

patterns_digambar = [
    r'\bDIGAMBAR\b', r'\bDIGAMBER\b', r'\bDIG\.\b',
    r'\bDIG\b', r'\bNAKODA\b', r'\bATISHAY\b',
    r'\bBAHUBALI\b', r'\bGOMMATESHWAR\b',
]

patterns_shwetambar = [
    r'\bSHWETAMBAR\b', r'\bSHWETAMBER\b', r'\bSHVETAMBAR\b',
    r'\bSVE\b', r'\bMURTIPUJAK\b', r'\bDERASAR\b',
]

patterns_sthanakvasi = [
    r'\bSTHANAKVASI\b', r'\bSTHANAK\b', r'\bSTHANAKWASI\b',
]

pre_classified = {d: [] for d in ['digambar', 'shwetambar', 'sthanakvasi', 'mixed', 'name_heuristic']}

for row in entries:
    name = row['name'].upper() if row['name'] else ''
    landmark = row['landmark_type'] or ''
    source = row['source'] or ''
    
    is_digambar = bool(re.search('|'.join(patterns_digambar), name))
    is_shwetambar = bool(re.search('|'.join(patterns_shwetambar), name))
    is_sthanakvasi = bool(re.search('|'.join(patterns_sthanakvasi), name))
    
    tradition = None
    
    if is_digambar and not is_shwetambar and not is_sthanakvasi:
        tradition = 'Digambar'
        pre_classified['digambar'].append(row['id'])
    elif is_shwetambar and not is_digambar and not is_sthanakvasi:
        tradition = 'Shwetambar'
        pre_classified['shwetambar'].append(row['id'])
    elif is_sthanakvasi and not is_digambar and not is_shwetambar:
        tradition = 'Sthanakvasi'
        pre_classified['sthanakvasi'].append(row['id'])
    elif is_digambar and is_shwetambar:
        tradition = 'Mixed'
        pre_classified['mixed'].append(row['id'])
    
    if tradition:
        db.execute("UPDATE churches SET tradition = ? WHERE id = ?", (tradition, row['id']))

db.commit()

print(f"  Digambar:    {len(pre_classified['digambar'])}")
print(f"  Shwetambar:  {len(pre_classified['shwetambar'])}")
print(f"  Sthanakvasi: {len(pre_classified['sthanakvasi'])}")
print(f"  Mixed:       {len(pre_classified['mixed'])}")

# Remaining unclassified
remaining = db.execute("SELECT COUNT(*) FROM churches WHERE faith='Jain' AND (tradition IS NULL OR tradition='Jain' OR tradition='')").fetchone()[0]
total = db.execute("SELECT COUNT(*) FROM churches WHERE faith='Jain'").fetchone()[0]
print(f"\n  Unclassified: {remaining}")
print(f"  Total Jain:   {total}")

# Step 2: Landmark type refinement
print(f"\n=== Landmark type refinement ===")
lm_counts = Counter()
for row in entries:
    lm_counts[row['landmark_type'] or 'none'] += 1

print("Current landmark types:")
for t, c in lm_counts.most_common():
    print(f"  {t:25s} {c}")

# Fix common issues: entries named 'Temple' but landmark_type is wrong
fixes = db.execute("""
    SELECT id, name, landmark_type FROM churches
    WHERE faith='Jain' AND landmark_type IS NOT NULL AND landmark_type != ''
      AND landmark_type NOT IN ('temple', 'school', 'community_center', 'hospital', 'library', 'dining_hall', 'museum', 'caves', 'statue', 'other')
""").fetchall()

print(f"\nEntries with non-standard landmark types: {len(fixes)}")
for f in fixes[:20]:
    print(f"  {f['name'][:50]:50s} -> {f['landmark_type']}")

db.close()
print(f"\nDone. {total} Jain entries in DB, {total - remaining} classified by tradition.")
