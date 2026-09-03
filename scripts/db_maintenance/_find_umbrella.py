"""Fast analysis of umbrella corp patterns - writes to file."""
import re
import sqlite3
from collections import Counter

db = sqlite3.connect(r'E:\grid\churches.db')
OUT = r'E:\grid\_umbrella_report.txt'

# ── Keywords that suggest entity/corp/diocese prefix ────────────────
CORP_KEYWORDS = [
    'CORP', 'CORPORATION', 'EPISC', 'EPISCOPAL',
    'DIOCESE', 'ARCHDIOCESE', 'ARCHDIOCESAN',
    'OBLATES', 'FABRIQUE',
    'TRUST', 'TRUSTEES',
]

# ── Single pass: iterate all names and classify ─────────────────────
results = []
corp_counts = Counter()
total = 0

cur = db.execute("SELECT id, name FROM churches")
for row in cur:
    total += 1
    name = row[1]
    
    # Check for corp keywords
    matched = [kw for kw in CORP_KEYWORDS if kw in name]
    if matched:
        corp_counts.update(matched)
        results.append((row[0], name))

db.close()

# Write report
with open(OUT, 'w', encoding='utf-8') as f:
    f.write(f"Total churches scanned: {total:,}\n")
    f.write(f"Records with corp keywords: {len(results):,}\n\n")
    
    f.write("=" * 80 + "\n")
    f.write("KEYWORD BREAKDOWN\n")
    f.write("=" * 80 + "\n")
    for kw, cnt in sorted(corp_counts.items(), key=lambda x: -x[1]):
        f.write(f"  {kw:20s} {cnt:>8,}\n")
    
    # Show all unique corp-type prefixes found (first ~5 words)
    f.write("\n" + "=" * 80 + "\n")
    f.write("ALL RECORDS WITH CORP KEYWORDS (full names)\n")
    f.write("=" * 80 + "\n")
    for i, (cid, name) in enumerate(results):
        f.write(f"  [{i+1:6d}] (id={cid}) [{len(name):3d}] {name}\n")
        if (i+1) % 1000 == 0:
            f.write(f"  ... ({len(results)-i-1} more)\n\n")

print(f"Done. Wrote {len(results)} records to {OUT}")
print(f"\nTop keyword counts:")
for kw, cnt in corp_counts.most_common(20):
    print(f"  {kw:20s} {cnt:>8,}")
