"""Find names with legal-entity prefixes that bury the actual church name."""
import sqlite3
import re

db = sqlite3.connect(r'E:\grid\churches.db')
OUT = r'E:\grid\_corp_prefixes.txt'

# Specific phrases that indicate an umbrella/corp legal prefix
LEGAL_PREFIXES = [
    'EPISCOPAL CORPORATION',
    'EPISC CORP',
    'CATHOLIC EPISCOPAL',
    'CORPORATION OF THE',
    'EPISCOPAL CORP OF',
]

print("Scanning for legal-entity prefix names...")
results = []

cur = db.execute("SELECT id, name, LENGTH(name) FROM churches")
for row in cur:
    n = row[1]
    for prefix in LEGAL_PREFIXES:
        if prefix in n:
            results.append(row)
            break

db.close()

results.sort(key=lambda r: -r[2])

with open(OUT, 'w', encoding='utf-8') as f:
    f.write(f"Total records with legal-entity prefixes: {len(results):,}\n\n")
    f.write(f"{'='*80}\n")
    f.write(f"  {'#':>6}  {'Len':>3}  Name\n")
    f.write(f"{'='*80}\n")
    for i, (rid, name, length) in enumerate(results):
        f.write(f"  [{i+1:>6}] ({length:>3}) {name}\n")

print(f"Done. Wrote {len(results)} records to {OUT}")
