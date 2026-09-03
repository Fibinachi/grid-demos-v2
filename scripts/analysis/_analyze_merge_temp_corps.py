"""Analyze what non-name data the merge_temp records carry."""
import sqlite3
from collections import Counter

db = sqlite3.connect(r'E:\grid\churches_merge_temp.db')
cols = [c[1] for c in db.execute('PRAGMA table_info(churches)').fetchall()]

# Get all records matching our umbrella patterns
import re
patterns = [
    '%ROMAN CATHOLIC EPISCOPAL CORPORATION%',
    '%THE ROMAN CATHOLIC EPISCOPAL CORPORATION%',
    '%CATHOLIC EPISCOPAL CORPORATION%',
    '%EPISCOPAL CORPORATION OF%',
    '%CORPORATION OF THE PRESIDING BISHOP%',
    '%CORPORATION OF THE PRESIDENT%',
]

all_rows = []
for pat in patterns:
    cur = db.execute("SELECT * FROM churches WHERE name LIKE ?", (pat,))
    all_rows.extend(cur.fetchall())

print(f"Total records: {len(all_rows)}")

# Analyze non-null field distribution
field_counts = Counter()
for row in all_rows:
    for i, val in enumerate(row):
        if val is not None and str(val).strip() not in ('', '0', '0.0'):
            field_counts[cols[i]] += 1

total = len(all_rows)
print(f"\n=== Non-null fields (out of {total} records) ===")
for k, cnt in sorted(field_counts.most_common(), key=lambda x: -x[1]):
    pct = cnt * 100 / total
    print(f"  {k}: {cnt}/{total} ({pct:.1f}%)")

# Show some sample records' key data
print(f"\n=== Sample records (non-null key fields) ===")
seen = set()
for row in all_rows[:10]:
    name = row[cols.index('name')]
    if name[:30] not in seen:
        seen.add(name[:30])
        print(f"\n  {name[:70]}")
        for i, val in enumerate(row):
            c = cols[i]
            if val and str(val).strip() not in ('', '0', '0.0') and c not in ('id', 'name', 'source', 'last_updated'):
                s = str(val).strip()
                if len(s) > 60:
                    s = s[:60] + '...'
                print(f"    {c}: {s}")

db.close()
