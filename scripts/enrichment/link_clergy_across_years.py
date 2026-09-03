#!/usr/bin/env python3
"""Link clergy across years: same-parish first, then name-only for movers."""
import sqlite3, re
from pathlib import Path
from collections import defaultdict

DIR_DB = Path("E:/grid/data/catholic_directory.db")
db = sqlite3.connect(str(DIR_DB))
db.row_factory = sqlite3.Row

# Create cross-clergy table
db.execute("""
    CREATE TABLE IF NOT EXISTS dir_clergy_cross (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        clergy_1865_id INTEGER REFERENCES dir_clergy(id),
        clergy_1868_id INTEGER REFERENCES dir_clergy(id),
        match_confidence REAL,
        match_method TEXT,
        same_parish INTEGER
    )
""")
db.execute("DELETE FROM dir_clergy_cross")
db.commit()

def clean_name(n):
    if not n: return ''
    n = n.upper().strip()
    # Normalize: strip titles, punctuation
    n = re.sub(r'REV\.?\s*', '', n)
    n = re.sub(r'VERY\s+REV\.?\s*', '', n)
    n = re.sub(r'RT\.?\s*REV\.?\s*', '', n)
    n = re.sub(r'MOST\s+REV\.?\s*', '', n)
    n = re.sub(r'[.,]', '', n)
    return re.sub(r'\s+', ' ', n).strip()

def norm_diocese(d):
    """Normalize diocese name to strip OCR junk and standardize variants."""
    if not d: return ''
    d = d.upper().strip()
    # Strip trailing junk: periods, single chars, page numbers
    d = re.sub(r'\s+[\.\:\;\|\}\~\{\*\-]+$', '', d)
    d = re.sub(r'\s+\d+$', '', d)
    d = re.sub(r'\s+[A-Z]{1,2}$', '', d)  # trailing 1-2 uppercase chars
    d = re.sub(r'[\.\:\;\|\}\~\{\*\-]+$', '', d)
    d = d.strip()
    # Fix common variants
    d = d.replace('NEW-YORK', 'NEW YORK')
    d = d.replace('NEW-ORLEANS', 'NEW ORLEANS')
    d = d.replace('PIITSBURGH', 'PITTSBURGH')
    return re.sub(r'\s+', ' ', d).strip()

# ── Load all clergy with their parish info ──
def load_clergy(year):
    clergy = db.execute(f"""
        SELECT c.id, UPPER(c.name) as name, c.role,
               d.name as parish, d.city, d.state, d.diocese, d.id as entry_id
        FROM dir_clergy c
        JOIN dir_entries d ON c.entry_id = d.id
        WHERE c.directory_year={year} AND c.name IS NOT NULL
    """).fetchall()
    return clergy

c1865 = load_clergy(1865)
c1868 = load_clergy(1868)
print(f"Loaded: {len(c1865):,} clergy from 1865, {len(c1868):,} from 1868")

# ── Pass 1: Same parish (same name + same city) ──
print("\nPass 1: Same-parish matches...")
# Build 1868 lookup by (clean_name, parish, city, diocese)
lookup_parish = defaultdict(list)
for c in c1868:
    key = (clean_name(c['name']), c['parish'].upper().strip(), (c['city'] or '').upper().strip(), norm_diocese(c['diocese']))
    lookup_parish[key].append(c)

matched_1868_ids = set()
pass1 = 0
for c in c1865:
    key = (clean_name(c['name']), c['parish'].upper().strip(), (c['city'] or '').upper().strip(), norm_diocese(c['diocese']))
    if key in lookup_parish:
        for c2 in lookup_parish[key]:
            if c2['id'] not in matched_1868_ids:
                db.execute("""
                    INSERT INTO dir_clergy_cross (clergy_1865_id, clergy_1868_id, match_confidence, match_method, same_parish)
                    VALUES (?, ?, 0.95, 'same_parish', 1)
                """, (c['id'], c2['id']))
                matched_1868_ids.add(c2['id'])
                pass1 += 1
                break
db.commit()
print(f"  Pass 1: {pass1:,} clergy at same parish in both years")

# ── Pass 2: Name-only matches for remaining (movers) ──
print("\nPass 2: Name-only matches (movers)...")
# Get unmatched 1865 and 1868 clergy
unmatched_1865 = [c for c in c1865 if not db.execute(
    "SELECT 1 FROM dir_clergy_cross WHERE clergy_1865_id=?", (c['id'],)
).fetchone()]

unmatched_1868 = [c for c in c1868 if c['id'] not in matched_1868_ids]

# Build name+diocese lookup for 1868 (diocese required — priests don't cross dioceses)
name_lookup = defaultdict(list)
for c in unmatched_1868:
    key = (clean_name(c['name']), norm_diocese(c['diocese']))
    name_lookup[key].append(c)

pass2 = 0
for c in unmatched_1865:
    cn = clean_name(c['name'])
    cdioc = norm_diocese(c['diocese'])
    key = (cn, cdioc)
    if key in name_lookup:
        for c2 in name_lookup[cn]:
            if c2['id'] not in matched_1868_ids:
                db.execute("""
                    INSERT INTO dir_clergy_cross (clergy_1865_id, clergy_1868_id, match_confidence, match_method, same_parish)
                    VALUES (?, ?, 0.80, 'name_only', 0)
                """, (c['id'], c2['id']))
                matched_1868_ids.add(c2['id'])
                pass2 += 1
                break
db.commit()
print(f"  Pass 2: {pass2:,} clergy matched by name (moved parishes)")

# ── Summary ──
total_1865 = len(c1865)
total_1868 = len(c1868)
linked_1865 = pass1 + pass2
print(f"\n{'='*50}")
print(f"Clergy Cross-Year Links: 1865 <-> 1868")
print(f"{'='*50}")
print(f"  1865 clergy total:     {total_1865:>6,}")
print(f"  1868 clergy total:     {total_1868:>6,}")
print(f"  Same parish (Pass 1):  {pass1:>6,} ({pass1/total_1865*100:.0f}%)")
print(f"  Name only (Pass 2):    {pass2:>6,} ({pass2/total_1865*100:.0f}%)")
print(f"  Total linked:          {linked_1865:>6,} ({linked_1865/total_1865*100:.0f}%)")
print(f"  Unmatched 1865:        {total_1865 - linked_1865:>6,}")

# Sample same-parish matches
print("\nSample SAME-PARISH matches (stayed put):")
for r in db.execute("""
    SELECT c1.name, c1.role, d1.name as p1, d2.name as p2, d1.city, d1.state
    FROM dir_clergy_cross x
    JOIN dir_clergy c1 ON x.clergy_1865_id = c1.id
    JOIN dir_clergy c2 ON x.clergy_1868_id = c2.id
    JOIN dir_entries d1 ON c1.entry_id = d1.id
    JOIN dir_entries d2 ON c2.entry_id = d2.id
    WHERE x.same_parish=1 LIMIT 10
"""):
    print(f"  {r[0][:30]:30s} {r[1] or '':12s} {r[2][:25]:25s} -> {r[3][:25]:25s}  ({r[4]}, {r[5]})")

# Sample movers
print("\nSample MOVERS (same name, different parish):")
for r in db.execute("""
    SELECT c1.name, c1.role, d1.name as p1, d2.name as p2, d1.city, d1.state
    FROM dir_clergy_cross x
    JOIN dir_clergy c1 ON x.clergy_1865_id = c1.id
    JOIN dir_clergy c2 ON x.clergy_1868_id = c2.id
    JOIN dir_entries d1 ON c1.entry_id = d1.id
    JOIN dir_entries d2 ON c2.entry_id = d2.id
    WHERE x.same_parish=0 LIMIT 10
"""):
    print(f"  {r[0][:30]:30s} {r[1] or '':12s} {r[2][:25]:25s} -> {r[3][:25]:25s}  ({r[4]}, {r[5]})")

db.close()
print("\nDone.")
