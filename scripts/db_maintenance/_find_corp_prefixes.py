"""Find names where a legal-entity/corp/diocese prefix IS the name (not just a denomination)."""
import sqlite3
import re

db = sqlite3.connect(r'E:\grid\churches.db')
OUT = r'E:\grid\_corp_prefixes.txt'

# Patterns that indicate a legal-entity prefix rather than a denomination
ENTITY_PATTERNS = [
    # Ukrainian / Eastern Rite legal entities
    r'\bUKRAINIAN\s+(?:CATH(?:OLIC)?\s+)?(?:EPISC(?:OPAL)?\s+)?CORP(?:ORATION)?',
    r'\b(?:CATH(?:OLIC)?\s+)?EPISC(?:OPAL)?\s+CORP(?:ORATION)?',
    r'\bGREEK\s+(?:CATH(?:OLIC)?\s+)?EPISC(?:OPAL)?\s+CORP(?:ORATION)?',
    
    # Corporation of / Episcopal Corporation of patterns
    r'\bCORPORATION\s+OF\s+(?:THE\s+)?(?:CATHOLIC\s+)?(?:ROMAN\s+)?(?:BISHOP|ARCHBISHOP|DIOCESE|CHURCH)',
    r'\bEPISCOPAL\s+CORP(?:ORATION)?\s+OF',
    r'\bEPISC\s+CORP\s+OF',
    
    # Diocese / Archdiocese prefixes
    r'\b(?:ARCH)?DIOCESE\s+OF\s+\w',
    r'\bARCHDIOCESAN\s+(?:CATHOLIC\s+)?(?:CENTRE|CENTER|OFFICE|CHANCERY)',
    
    # Trust / trustees patterns (not church names)
    r'\bTRUST(?:EES)?\s+OF\b',
    r'\bTRUST\s+UNDER\b',
    
    # Legal suffixes that dominate the name
    r'\bINC\.?\s*$',
]

# Also look specifically for truncated names where length=60 and contain corp boilerplate
SHORT_CORP = r'(?:UKRAINIAN|CORP|EPISC|DIOCESE).{20,60}$'

print("Scanning for legal-entity prefix patterns...")
results = []
seen = set()

cur = db.execute("SELECT id, name, LENGTH(name) FROM churches")

for row in cur:
    name = row[1]
    # Skip records where the entity keyword is just a denomination
    # e.g. "ST JOHN'S EPISCOPAL CHURCH" - not a legal entity
    n_upper = name
    
    # Check if name matches a legal-entity pattern
    for pat_src in ENTITY_PATTERNS:
        m = re.search(pat_src, n_upper)
        if m:
            # For EPISCOPAL: only flag if it says "EPISCOPAL CORPORATION" or "EPISC CORP"
            # not just "EPISCOPAL CHURCH"
            entity_start = m.start()
            # If the entity pattern is at or near the start, or the name is truncated
            results.append((row[1], row[2]))
            break

db.close()

# Deduplicate
unique_names = {}
for name, length in results:
    key = name[:60]
    if key not in unique_names:
        unique_names[key] = (name, length)

results_unique = list(unique_names.values())
results_unique.sort(key=lambda x: -x[1])

with open(OUT, 'w', encoding='utf-8') as f:
    f.write(f"Total potential legal-entity prefixes: {len(results_unique):,}\n\n")
    
    for i, (name, length) in enumerate(results_unique):
        f.write(f"  [{i+1:6d}] (len={length:3d}) {name}\n")
        if (i+1) % 500 == 0:
            remaining = len(results_unique) - i - 1
            f.write(f"  ... ({remaining:,} more)\n\n")

print(f"Done. Wrote {len(results_unique)} unique records to {OUT}")
