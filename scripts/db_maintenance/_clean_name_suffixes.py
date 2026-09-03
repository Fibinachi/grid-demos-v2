#!/usr/bin/env python3
"""
_clean_name_suffixes.py — Strip corporate/legal suffixes from name_transliterated.

Affects ALL churches, not just Islam. Uses name_transliterated as the 
cleaned field so original name is preserved.

Suffixes stripped (case-insensitive, must be at end of name):
  INC, INCORPORATED, LLC, LTD, LIMITED, CORP, CORPORATION, CO, COMPANY,
  ASSOC, ASSOCIATION, FELLOWSHIP, SOCIETY, ORGANIZATION,
  ENTERPRISES, ENTERPRISE, SERVICES, SERVICE, GROUP,
  INTERNATIONAL, WORLDWIDE, GLOBAL

Preserved (not stripped): TRUST, MINISTRY/MINISTRIES, FUND, FOUNDATION,
  CENTER/CENTRE

Also strips trailing punctuation after the suffix.
"""
import sqlite3, re, time, sys

DB = r'E:\grid\churches.db'

# Suffixes to strip — ordered by length (longer first) to avoid partial matches
SUFFIXES = sorted([
    'INCORPORATED', 'INCORPORATED.', 'CORPORATION', 'CORPORATION.',
    'INTERNATIONAL', 'ENTERPRISES', 'ORGANIZATION', 'ASSOCIATION',
    'FELLOWSHIP',
    'INC.', 'LTD.', 'LLC.', 'CORP.', 'CO.', 'INC', 'LLC', 'LTD',
    'CORP', 'LIMITED', 'COMPANY', 'SOCIETY', 'SERVICE',
    'ENTERPRISE', 'SERVICES',
    'ASSOC', 'GROUP', 'GLOBAL', 'CO',
    'WORLDWIDE',
], key=len, reverse=True)

# Build pattern: strip suffix + optional trailing punctuation + optional whitespace
SUFFIX_PAT = re.compile(
    r'\s+(' + '|'.join(re.escape(s) for s in SUFFIXES) + r')'
    r'[.\s]*$', re.IGNORECASE
)

# Also strip standalone trailing punctuation/numbers after suffix removal
CLEAN_TRAILING = re.compile(r'[.\s,;:#]+$')

conn = sqlite3.connect(DB, timeout=120)
conn.execute('PRAGMA journal_mode=WAL')
c = conn.cursor()

# Ensure name_transliterated column exists
existing = {r[1] for r in c.execute('PRAGMA table_info(churches)').fetchall()}
if 'name_transliterated' not in existing:
    c.execute('ALTER TABLE churches ADD COLUMN name_transliterated TEXT')
    print("Added name_transliterated column")

# Count total
total = c.execute("SELECT COUNT(*) FROM churches").fetchone()[0]
print(f"Total churches: {total:,}")

# Get all records that have a name
c.execute("""
    SELECT id, name, name_transliterated
    FROM churches
    WHERE name IS NOT NULL AND name != ''
    ORDER BY id
""")
rows = c.fetchall()
print(f"Records with names: {len(rows):,}")

# Process in batches — track what needs updating
updates = []  # (new_translit, id)
cleaned_count = 0
total_suffix_found = 0

BATCH = 50000
t0 = time.time()

for i, (rid, name, existing_translit) in enumerate(rows):
    # Use existing translit if available, otherwise original name
    base = (existing_translit or name).strip()
    original = base
    
    # Remove suffix
    new_base = SUFFIX_PAT.sub('', base)
    if new_base != base:
        total_suffix_found += 1
    
    # Clean trailing punctuation
    new_base = CLEAN_TRAILING.sub('', new_base)
    
    if new_base != original:
        updates.append((new_base, rid))
        cleaned_count += 1
    
    # Batch commit
    if len(updates) >= BATCH:
        c.executemany(
            "UPDATE churches SET name_transliterated = ? WHERE id = ?",
            updates
        )
        conn.commit()
        pct = (i + 1) / len(rows) * 100
        elapsed = time.time() - t0
        rate = (i + 1) / elapsed if elapsed > 0 else 0
        print(f"  ... {i+1:,}/{len(rows):,} ({pct:.0f}%) | {cleaned_count:,} cleaned | {rate:,.0f} rec/s", flush=True)
        updates = []

if updates:
    c.executemany(
        "UPDATE churches SET name_transliterated = ? WHERE id = ?",
        updates
    )
    conn.commit()

elapsed = time.time() - t0
print(f"\nDone in {elapsed:.1f}s")
print(f"Records processed: {len(rows):,}")
print(f"Names cleaned (suffix removed): {cleaned_count:,}")
print(f"Total suffix matches: {total_suffix_found:,}")

# Confirm
confirmed = c.execute("""
    SELECT COUNT(*) FROM churches 
    WHERE name_transliterated IS NOT NULL AND name_transliterated != ''
""").fetchone()[0]
print(f"Total with name_transliterated: {confirmed:,}")

conn.close()
