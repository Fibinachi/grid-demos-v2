#!/usr/bin/env python3
"""
_clean_islam_suffixes.py — Strip corporate suffixes from Islam name_transliterated only.

Uses simple SQL REPLACE for speed. Only processes the ~355K Islam records.
"""
import sqlite3, time, sys

DB = r'E:\grid\churches.db'

conn = sqlite3.connect(DB, timeout=120)
conn.execute('PRAGMA journal_mode=WAL')
c = conn.cursor()

# Suffixes to strip (sorted by length descending to avoid partial matches)
SUFFIXES = ['INCORPORATED', 'CORPORATION', 'INTERNATIONAL', 'ENTERPRISES', 
            'ORGANIZATION', 'ASSOCIATION', 'FELLOWSHIP',
            'LIMITED', 'COMPANY', 'SERVICES', 'SOCIETY',
            'ENTERPRISE', 'SERVICE', 'GROUP',
            'GLOBAL', 'WORLDWIDE',
            'INC', 'LLC', 'LTD', 'CORP', 'ASSOC']

# Count Islam with names
total = c.execute("SELECT COUNT(*) FROM churches WHERE faith='Islam' AND name IS NOT NULL AND name != ''").fetchone()[0]
print(f"Islam records with names: {total:,}")

# Build SQL: strip each suffix from the end of name_transliterated
# Use a chain of CASE WHEN ... THEN ... to handle suffix stripping
t0 = time.time()

# Step 1: Ensure name_transliterated is populated for all Islam entries
c.execute("""
    UPDATE churches 
    SET name_transliterated = COALESCE(NULLIF(TRIM(name_transliterated), ''), name)
    WHERE faith='Islam' AND name IS NOT NULL AND name != ''
""")
conn.commit()
print(f"  name_transliterated seeded for Islam in {time.time()-t0:.1f}s")

# Step 2: Strip each suffix from the end using LIKE
t1 = time.time()
stripped_total = 0
for suffix in SUFFIXES:
    # Match suffix at end of name, possibly with trailing punctuation/space
    c.execute(f"""
        UPDATE churches
        SET name_transliterated = TRIM(SUBSTR(name_transliterated, 1, LENGTH(name_transliterated) - LENGTH(?)))
        WHERE faith='Islam'
          AND name_transliterated LIKE '% ' || ?
          AND SUBSTR(name_transliterated, -LENGTH(?)) = ?
    """, (suffix + ' ', suffix + ' ', suffix + ' ', suffix + ' '))
    n = c.rowcount
    if n:
        print(f"  -{suffix}: {n:,} stripped", flush=True)
        stripped_total += n
    conn.commit()
    
    # Also handle with period: "INC."
    if suffix.endswith('.') or suffix in ('INC', 'LLC', 'LTD', 'CORP', 'CO', 'ASSOC'):
        dotted = suffix + '.'
        c.execute(f"""
            UPDATE churches
            SET name_transliterated = TRIM(SUBSTR(name_transliterated, 1, LENGTH(name_transliterated) - LENGTH(?)))
            WHERE faith='Islam'
              AND name_transliterated LIKE '% ' || ?
              AND SUBSTR(name_transliterated, -LENGTH(?)) = ?
        """, (dotted + ' ', dotted + ' ', dotted + ' ', dotted + ' '))
        n2 = c.rowcount
        if n2:
            print(f"  -{dotted}: {n2:,} stripped", flush=True)
            stripped_total += n2
        conn.commit()

# Step 3: Clean trailing punctuation
c.execute("""
    UPDATE churches 
    SET name_transliterated = RTRIM(RTRIM(RTRIM(RTRIM(RTRIM(
        name_transliterated, '.'), ','), ';'), ':'), ' ')
    WHERE faith='Islam'
      AND (name_transliterated LIKE '%,' 
           OR name_transliterated LIKE '%.'
           OR name_transliterated LIKE '%;'
           OR name_transliterated LIKE '%:'
           OR name_transliterated LIKE '% ')
""")
n = c.rowcount
print(f"  Trailing punctuation cleaned: {n:,}")

elapsed = time.time() - t1
print(f"\nDone in {elapsed:.1f}s")
print(f"Total suffix strips: {stripped_total:,}")

# Verify
c.execute("SELECT name, name_transliterated FROM churches WHERE faith='Islam' AND name != name_transliterated LIMIT 20")
examples = c.fetchall()
if examples:
    print(f"\nSample changes (first 20):")
    for name, new_name in examples:
        print(f"  '{name[:60]}'")
        print(f"  → '{new_name[:60]}'")
        print()

conn.close()
