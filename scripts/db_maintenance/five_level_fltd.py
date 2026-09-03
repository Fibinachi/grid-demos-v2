"""
Revert faith to specific religion extracted from taxonomy path.
New 5-level hierarchy:
  1. civilizational_family (already populated)
  2. faith (specific religion from taxonomy)
  3. legacy
  4. tradition
  5. denomination
"""
import sqlite3
db = sqlite3.connect('E:/grid/churches.db')
c = db.cursor()

# Helper: extract 2nd segment from taxonomy path
# full_path like "Abrahamic/Christian/Protestant/Baptist"
# We want "Christian"
sql_extract = """
    SUBSTR(t.full_path, 
           INSTR(t.full_path, '/') + 1, 
           INSTR(SUBSTR(t.full_path, INSTR(t.full_path, '/') + 1), '/') - 1)
"""

# ============================================================
# 1. Abrahamic faiths: extract Christian/Islam/Judaism
# ============================================================
c.execute(f"""
    UPDATE churches SET faith = {sql_extract}
    FROM taxonomy t
    WHERE churches.taxonomy_id = t.id
    AND churches.civilizational_family = 'ABRAHAMIC'
    AND t.full_path LIKE 'Abrahamic/%'
""")
print(f"Abrahamic faiths restored: {c.rowcount:,}")

# ============================================================
# 2. Dharmic faiths: extract Hindu/Buddhist/Sikh/Jain
# ============================================================
c.execute(f"""
    UPDATE churches SET faith = {sql_extract}
    FROM taxonomy t
    WHERE churches.taxonomy_id = t.id
    AND churches.civilizational_family = 'DHARMIC'
    AND t.full_path LIKE 'Dharmic/%'
""")
print(f"Dharmic faiths restored: {c.rowcount:,}")

# ============================================================
# 3. Taoic faiths: extract Shinto/Taoist/Confucian
# ============================================================
c.execute(f"""
    UPDATE churches SET faith = {sql_extract}
    FROM taxonomy t
    WHERE churches.taxonomy_id = t.id
    AND churches.civilizational_family = 'TAOIC'
    AND t.full_path LIKE 'Taoic/%'
""")
print(f"Taoic faiths restored: {c.rowcount:,}")

# ============================================================
# 4. OTHER: set faith = 'Other'
# ============================================================
c.execute("""
    UPDATE churches SET faith = 'Other'
    WHERE civilizational_family = 'OTHER'
""")
print(f"Other faiths: {c.rowcount:,}")

# ============================================================
# 5. Handle any records with no taxonomy_id
# ============================================================
# Use civilizational_family as fallback for records with NULL taxonomy_id
c.execute("""
    UPDATE churches SET faith = 'Abrahamic'
    WHERE civilizational_family = 'ABRAHAMIC' AND taxonomy_id IS NULL AND (faith IS NULL OR faith = '' OR faith = 'Abrahamic')
""")
c.execute("""
    UPDATE churches SET faith = 'Dharmic'
    WHERE civilizational_family = 'DHARMIC' AND taxonomy_id IS NULL AND (faith IS NULL OR faith = '' OR faith = 'Dharmic')
""")
c.execute("""
    UPDATE churches SET faith = 'Taoic'
    WHERE civilizational_family = 'TAOIC' AND taxonomy_id IS NULL AND (faith IS NULL OR faith = '' OR faith = 'Taoic')
""")

db.commit()

# ============================================================
# VERIFY
# ============================================================
print("\n=== Faith counts ===")
c.execute("SELECT faith, COUNT(*) FROM churches WHERE faith IS NOT NULL AND faith != '' GROUP BY faith ORDER BY COUNT(*) DESC")
for r in c.fetchall():
    c.execute("SELECT civilizational_family FROM churches WHERE faith=? LIMIT 1", (r[0],))
    cf = c.fetchone()[0] if c.fetchone() else '?'
    print(f"  {r[0]:20s} {r[1]:>8,}  [{cf}]")

print(f"\n=== FLTD coverage ===")
for f in ['Christian', 'Islam', 'Judaism', 'Hindu', 'Buddhist', 'Sikh', 'Shinto', 'Taoist', 'Other']:
    c.execute("SELECT COUNT(*) FROM churches WHERE faith=?", (f,))
    total = c.fetchone()[0]
    if total == 0: continue
    c.execute("SELECT COUNT(*) FROM churches WHERE faith=? AND legacy IS NOT NULL AND legacy != ''", (f,))
    legacy = c.fetchone()[0]
    print(f"  {f:15s}: {total:>7,} total, legacy={legacy:>7,} ({legacy/total*100:5.1f}%)")

c.execute("SELECT COUNT(*) FROM churches WHERE faith IS NULL OR faith=''")
print(f"\n  NULL faith: {c.fetchone()[0]:,}")

c.execute("SELECT civilizational_family, COUNT(*) FROM churches GROUP BY civilizational_family ORDER BY COUNT(*) DESC")
print(f"\n=== Civilizational families ===")
for r in c.fetchall():
    print(f"  {r[0]:15s} {r[1]:>8,}")

db.close()
print("\nDone!")
