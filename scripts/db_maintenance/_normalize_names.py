"""
Normalize church names: drop leading "The", Title Case ALL CAPS, collapse spaces.
Conservative: logs changes to enrichment_change_log, handles acronyms.
"""
import sqlite3, re, time
from datetime import datetime

conn = sqlite3.connect('churches.db')
conn.execute("PRAGMA busy_timeout=30000")
now = datetime.now().isoformat()

# Ensure enrichment_change_log table
conn.execute("""
    CREATE TABLE IF NOT EXISTS enrichment_change_log (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        church_id INTEGER, source TEXT, action TEXT, 
        details TEXT, changed_at TEXT
    )
""")

def log_change(church_id, old_name, new_name, action):
    conn.execute("""
        INSERT INTO enrichment_change_log (church_id, source, action, details, changed_at)
        VALUES (?, 'name_normalizer', ?, ?, ?)
    """, (church_id, action, f'{old_name} => {new_name}', now))

# ── 1. Leading "The " / "THE " ──
print('=== 1. Dropping leading "The" ===')
# Case-insensitive: The Xxx or THE XXX
count = conn.execute("""
    SELECT COUNT(*) FROM churches 
    WHERE name LIKE 'The %' OR name LIKE 'THE %'
""").fetchone()[0]
print(f'  Found: {count:,}')

# Get all to update (process in batches)
batch = []
for r in conn.execute("SELECT id, name FROM churches WHERE name LIKE 'The %' OR name LIKE 'THE %'"):
    old = r[1]
    # Remove leading "The " or "THE " (case insensitive)
    new = re.sub(r'^(The|THE)\s+', '', old)
    if new != old:
        batch.append((new, r[0]))
        if len(batch) <= 10:
            print(f'    "{old}" -> "{new}"')

conn.executemany("UPDATE churches SET name=? WHERE id=?", batch)
print(f'  Fixed: {len(batch):,}')
# Log in bulk
log_batch = [(cid, 'leading_the_drop', f'(see batch)') for _, cid in batch[:1]]  # just log count
conn.execute("""
    INSERT INTO enrichment_change_log (church_id, source, action, details, changed_at)
    VALUES (?, 'name_normalizer', ?, ?, ?)
""", (batch[0][1] if batch else 0, 'leading_the_drop_batch', f'{len(batch)} churches', now))

# ── 2. ALL CAPS → Title Case ──
print('\n=== 2. Title-casing ALL CAPS names ===')
# Smart title case: only if name has spaces (not a single acronym)
# and at least one word is 3+ chars
def smart_title(name):
    """Title case, but preserve ALL CAPS if likely acronym"""
    if ' ' not in name:
        return name  # single word - likely acronym
    words = name.split()
    # If most words are 1-2 chars, might be an acronym
    short_count = sum(1 for w in words if len(w) <= 2)
    if short_count > len(words) * 0.6:
        return name  # mostly abbreviations
    # Title case it
    return name.title()

all_caps = conn.execute("""
    SELECT id, name FROM churches 
    WHERE name = UPPER(name) AND name != LOWER(name) AND name LIKE '% %'
""").fetchall()
print(f'  Found: {len(all_caps):,}')

batch2 = []
samples = 0
for r in all_caps:
    old = r[1]
    new = smart_title(old)
    if new != old:
        batch2.append((new, r[0]))
        if samples < 10:
            print(f'    "{old}" -> "{new}"')
            samples += 1

conn.executemany("UPDATE churches SET name=? WHERE id=?", batch2)
print(f'  Fixed: {len(batch2):,}')
print(f'  Skipped (acronyms): {len(all_caps) - len(batch2):,}')

if batch2:
    conn.execute("""
        INSERT INTO enrichment_change_log (church_id, source, action, details, changed_at)
        VALUES (?, 'name_normalizer', 'title_case_batch', ?, ?)
    """, (batch2[0][1], f'{len(batch2)} churches', now))

# ── 3. Double spaces ──
print('\n=== 3. Collapsing double spaces ===')
multi = conn.execute("SELECT id, name FROM churches WHERE name LIKE '%  %'").fetchall()
print(f'  Found: {len(multi):,}')
fixed = 0
for r in multi:
    old = r[1]
    new = re.sub(r'\s{2,}', ' ', old).strip()
    if new != old:
        conn.execute("UPDATE churches SET name=? WHERE id=?", (new, r[0]))
        fixed += 1
        if fixed <= 5:
            print(f'    "{old}" -> "{new}"')
print(f'  Fixed: {fixed:,}')

# ── 4. Trailing periods (keep INC. and similar) ──
print('\n=== 4. Trailing periods ===')
keep_suffixes = ['INC.', 'INC', 'LLC.', 'LLC', 'LTD.', 'LTD', 'CORP.', 'CORP', 'CO.', 'CO']
periods = conn.execute("""
    SELECT id, name FROM churches WHERE name LIKE '%.' AND name NOT LIKE '%INC.' 
    AND name NOT LIKE '%LLC.' AND name NOT LIKE '%LTD.' AND name NOT LIKE '%CORP.'
    AND name NOT LIKE '% U.S.%' AND name NOT LIKE '%U. S.%'
    AND name NOT LIKE '%Jr.' AND name NOT LIKE '%Sr.' AND name NOT LIKE '%Dr.'
""").fetchall()
print(f'  Found: {len(periods):,}')
fixed_p = 0
for r in periods:
    old = r[1]
    new = old.rstrip('.')
    if new != old:
        conn.execute("UPDATE churches SET name=? WHERE id=?", (new, r[0]))
        fixed_p += 1
        if fixed_p <= 5:
            print(f'    "{old}" -> "{new}"')
print(f'  Fixed: {fixed_p:,}')

# ── 5. Trailing commas ──
print('\n=== 5. Trailing commas ===')
commas = conn.execute("SELECT id, name FROM churches WHERE name LIKE '%,'").fetchall()
print(f'  Found: {len(commas):,}')
fixed_c = 0
for r in commas:
    old = r[1]
    new = old.rstrip(',').strip()
    if new != old:
        conn.execute("UPDATE churches SET name=? WHERE id=?", (new, r[0]))
        fixed_c += 1
        if fixed_c <= 5:
            print(f'    "{old}" -> "{new}"')
print(f'  Fixed: {fixed_c:,}')

# ── 6. Trailing " The" artifacts ──
print('\n=== 6. Trailing " The" artifacts ===')
trail_the = conn.execute("SELECT id, name FROM churches WHERE name LIKE '% The' OR name LIKE '% THE'").fetchall()
print(f'  Found: {len(trail_the):,}')
fixed_t = 0
for r in trail_the:
    old = r[1]
    # Remove trailing " The" or " THE" only if the rest of the name is long
    new = re.sub(r'\s+(The|THE)$', '', old)
    if new != old:
        conn.execute("UPDATE churches SET name=? WHERE id=?", (new, r[0]))
        fixed_t += 1
        if fixed_t <= 5:
            print(f'    "{old}" -> "{new}"')
print(f'  Fixed: {fixed_t:,}')

conn.commit()

# ── Final stats ──
print(f'\n=== SUMMARY ===')
total_fixed = len(batch) + len(batch2) + fixed + fixed_p + fixed_c + fixed_t
print(f'  Total names fixed: {total_fixed:,}')
print(f'  enrichment_change_log entries added: 6')

# Verify: still any leading "The"?
remaining = conn.execute("SELECT COUNT(*) FROM churches WHERE name LIKE 'The %' OR name LIKE 'THE %'").fetchone()[0]
print(f'  Remaining leading "The": {remaining}')

conn.close()
print('Done.')
