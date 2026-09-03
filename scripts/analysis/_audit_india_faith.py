"""
Audit India faith/denomination tags for misclassifications and fix them.
"""
import sqlite3
import json
from datetime import datetime

DB = 'churches.db'
conn = sqlite3.connect(DB, timeout=30)
c = conn.cursor()

# ── 1. Analyze all India faith × source combinations ───────────────────────
print("=== Faith × Source breakdown for India ===")
c.execute("""
    SELECT faith, source, COUNT(*) as cnt
    FROM churches WHERE country='IN'
    GROUP BY faith, source
    ORDER BY cnt DESC
""")
for faith, src, cnt in c.fetchall():
    print(f"  {faith or 'NULL':<15} | {str(src or 'NULL'):<30} | {cnt:>8,}")

# ── 2. Find Jewish-tagged records that are NOT synagogues ───────────────────
print("\n=== Jewish-tagged, likely misclassified ===")
synagogue_kw = ['synagogue', 'synagog', 'chabad', 'jewish', 'israel', 'beth', 
                'magen', 'keneseth', 'paradesi', 'succath', 'judah', 'beyth', 'beit']
c.execute("""
    SELECT id, name, source, faith_tradition
    FROM churches WHERE country='IN' AND faith='Jewish'
""")
jewish = c.fetchall()
misclass_jewish = []
for cid, name, src, ft in jewish:
    name_lower = str(name).lower() if name else ''
    if not any(kw in name_lower for kw in synagogue_kw):
        misclass_jewish.append((cid, name, src))

print(f"Jewish-tagged total: {len(jewish)}")
print(f"  Actual synagogues: {len(jewish) - len(misclass_jewish)}")
print(f"  Misclassified (likely Hindu): {len(misclass_jewish)}")
for cid, name, src in misclass_jewish[:10]:
    print(f"  ID={cid} | {name} | src={src}")
if len(misclass_jewish) > 10:
    print(f"  ... and {len(misclass_jewish) - 10} more")

# ── 3. Check for other faith misclassifications ─────────────────────────────
print("\n=== Other potential faith mismatches ===")

# Hindu-tagged: check for obviously non-Hindu names
c.execute("SELECT id, name, faith, source FROM churches WHERE country='IN' AND faith='Hindu'")
hindu = c.fetchall()
non_hindu_kw = ['church', 'mosque', 'masjid', 'synagogue', 'gurudwara', 'cathedral', 'chapel', 'christian', 'muslim', 'islamic']
wrong_hindu = [(cid, name, src) for cid, name, faith, src in hindu 
               if any(kw in str(name).lower() for kw in non_hindu_kw)]
print(f"Hindu-tagged but name suggests non-Hindu: {len(wrong_hindu)}")
for cid, name, src in wrong_hindu[:10]:
    print(f"  ID={cid} | {name} | src={src}")

# Christian-tagged: check for obviously non-Christian names
c.execute("SELECT id, name, faith, source FROM churches WHERE country='IN' AND faith='Christian'")
christian = c.fetchall()
non_christian_kw = ['temple', 'mandir', 'mosque', 'masjid', 'gurudwara', 'haveli']
wrong_christian = [(cid, name, src) for cid, name, faith, src in christian 
                   if any(kw in str(name).lower() for kw in non_christian_kw)]
print(f"Christian-tagged but name suggests non-Christian: {len(wrong_christian)}")
for cid, name, src in wrong_christian[:10]:
    print(f"  ID={cid} | {name} | src={src}")

# Islam-tagged: check for obviously non-Muslim names
c.execute("SELECT id, name, faith, source FROM churches WHERE country='IN' AND faith='Islam'")
islam = c.fetchall()
non_islam_kw = ['temple', 'mandir', 'church', 'synagogue', 'gurudwara']
wrong_islam = [(cid, name, src) for cid, name, faith, src in islam 
               if any(kw in str(name).lower() for kw in non_islam_kw)]
print(f"Islam-tagged but name suggests non-Muslim: {len(wrong_islam)}")
for cid, name, src in wrong_islam[:10]:
    print(f"  ID={cid} | {name} | src={src}")

conn.close()
