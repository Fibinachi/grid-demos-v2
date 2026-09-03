#!/usr/bin/env python3
"""Use clergy matches to link churches across years. Priest-anchored church matching."""
import sqlite3, re
from collections import defaultdict
from pathlib import Path

DIR_DB = Path("E:/grid/data/catholic_directory.db")
db = sqlite3.connect(str(DIR_DB))
db.row_factory = sqlite3.Row

# Create church cross-year table
db.execute("""
    CREATE TABLE IF NOT EXISTS dir_entries_cross (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        year_from INTEGER, entry_from_id INTEGER,
        year_to INTEGER, entry_to_id INTEGER,
        match_confidence REAL, match_method TEXT,
        anchor_clergy_count INTEGER
    )
""")
db.execute("DELETE FROM dir_entries_cross")
db.execute("DELETE FROM dir_clergy_cross")
db.commit()

def clean_name(n):
    if not n: return ''
    n = n.upper().strip()
    for prefix in ['REV.', 'REV ', 'VERY REV.', 'VERY REV ', 'RT. REV.', 'RT. REV ', 'MOST REV.', 'MOST REV ']:
        if n.startswith(prefix): n = n[len(prefix):].strip()
    n = re.sub(r'[.,]', '', n)
    return re.sub(r'\s+', ' ', n).strip()

# ── Load all clergy with entry info ──
def load(year):
    return db.execute(f"""
        SELECT c.id as clergy_id, c.name, c.role, d.id as entry_id,
               d.name as parish, d.city, d.state,
               COALESCE(d.diocese_canonical, d.diocese) as diocese
        FROM dir_clergy c JOIN dir_entries d ON c.entry_id = d.id
        WHERE c.directory_year={year} AND c.name IS NOT NULL
    """).fetchall()

c65 = load(1865)
c68 = load(1868)
print(f"Clergy: {len(c65):,} (1865), {len(c68):,} (1868)")

# ── Step 1: Match clergy by name + diocese ──
c68_by_key = defaultdict(list)
for c in c68:
    key = (clean_name(c['name']), (c['diocese'] or '').upper().strip())
    if key[0] and len(key[0]) > 2:
        c68_by_key[key].append(c)

clergy_links = []  # (c65_id, c68_id, entry65_id, entry68_id)
used_68 = set()

for c in c65:
    cn = clean_name(c['name'])
    cd = (c['diocese'] or '').upper().strip()
    if not cn or len(cn) < 3: continue
    key = (cn, cd)
    if key in c68_by_key:
        for c2 in c68_by_key[key]:
            if c2['clergy_id'] not in used_68:
                clergy_links.append((c['clergy_id'], c2['clergy_id'], c['entry_id'], c2['entry_id']))
                used_68.add(c2['clergy_id'])
                break

print(f"Clergy matched: {len(clergy_links):,} ({len(clergy_links)/len(c65)*100:.0f}% of 1865)")

# ── Step 2: Aggregate clergy links into church links ──
# Multiple clergy at same church pair = stronger evidence
church_pairs = defaultdict(list)  # (entry65_id, entry68_id) -> [(clergy65_id, clergy68_id)]
for cl65, cl68, e65, e68 in clergy_links:
    church_pairs[(e65, e68)].append((cl65, cl68))

# Insert clergy links
for cl65, cl68, e65, e68 in clergy_links:
    db.execute("""
        INSERT INTO dir_clergy_cross (clergy_1865_id, clergy_1868_id, match_confidence, match_method, same_parish)
        VALUES (?, ?, 0.80, 'name_diocese', 1)
    """, (cl65, cl68))

# Insert church links with confidence based on anchor clergy count
church_links = 0
for (e65, e68), anchors in church_pairs.items():
    n = len(anchors)
    conf = min(0.95, 0.60 + n * 0.10)  # 1 anchor=0.70, 2=0.80, 3+=0.90+
    db.execute("""
        INSERT INTO dir_entries_cross (year_from, entry_from_id, year_to, entry_to_id, match_confidence, match_method, anchor_clergy_count)
        VALUES (1865, ?, 1868, ?, ?, 'clergy_anchored', ?)
    """, (e65, e68, conf, n))
    church_links += 1

db.commit()
print(f"Church links (clergy-anchored): {church_links:,}")

# ── Stats ──
by_anchors = defaultdict(int)
for (_, _), anchors in church_pairs.items():
    by_anchors[min(len(anchors), 4)] += 1

print(f"\nChurch links by anchor strength:")
for n in sorted(by_anchors):
    label = f"{n} priest(s)" if n < 4 else "4+ priests"
    print(f"  {label:15s} {by_anchors[n]:>6,}")

# ── Show examples ──
print("\nMulti-priest anchored churches (strongest links):")
multi = sorted(church_pairs.items(), key=lambda x: -len(x[1]))[:10]
for (e65, e68), anchors in multi:
    n65 = db.execute("SELECT name, city FROM dir_entries WHERE id=?", (e65,)).fetchone()
    n68 = db.execute("SELECT name, city FROM dir_entries WHERE id=?", (e68,)).fetchone()
    priest_names = []
    for cl65, _ in anchors[:3]:
        pn = db.execute("SELECT name FROM dir_clergy WHERE id=?", (cl65,)).fetchone()
        priest_names.append((pn[0] or '')[:20])
    print(f"  {n65[0][:25]:25s} -> {n68[0][:25]:25s}  ({n65[1]})  [{len(anchors)} priests: {', '.join(priest_names)}]")

# 1865 parishes still unmatched
linked_e65 = set(e65 for e65, _ in church_pairs)
total_e65 = db.execute("SELECT COUNT(DISTINCT id) FROM dir_entries WHERE directory_year=1865").fetchone()[0]
print(f"\n1865 entries linked via clergy: {len(linked_e65):,}/{total_e65:,} ({len(linked_e65)/total_e65*100:.0f}%)")

db.close()
print("\nDone.")
