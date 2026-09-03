"""Assess current state for classifiers to run."""
import sqlite3

conn = sqlite3.connect(r'E:\grid\churches.db')
c = conn.cursor()

# Islam count
islam = c.execute("SELECT COUNT(*) FROM churches WHERE faith='Islam'").fetchone()[0]
aff = c.execute("SELECT COUNT(*) FROM churches WHERE faith='Islam' AND (muslim_affiliation IS NOT NULL AND muslim_affiliation != '')").fetchone()[0]
print(f"Islam total: {islam:,}")
print(f"Islam with muslim_affiliation: {aff:,}")
print(f"Islam without muslim_affiliation: {islam - aff:,}")

# Null faith
null_faith = c.execute("SELECT COUNT(*) FROM churches WHERE faith IS NULL OR faith=''").fetchone()[0]
print(f"\nNull faith total: {null_faith:,}")

# Shinto
shinto = c.execute("SELECT COUNT(*) FROM churches WHERE faith='Shinto'").fetchone()[0]
print(f"Shinto total: {shinto:,}")

# Jewish
jewish = c.execute("SELECT COUNT(*) FROM churches WHERE faith='Jewish'").fetchone()[0]
print(f"Jewish total: {jewish:,}")

# Check columns
cols = [r[1] for r in c.execute('PRAGMA table_info(churches)').fetchall()]
if 'mosque_type' in cols:
    mt = c.execute("SELECT mosque_type, COUNT(*) FROM churches WHERE faith='Islam' AND mosque_type IS NOT NULL AND mosque_type!='' GROUP BY mosque_type ORDER BY COUNT(*) DESC").fetchall()
    print(f"\nMosque_type distribution ({len(mt)} types):")
    for r in mt:
        print(f"  {r[0]}: {r[1]:,}")

if 'faith_tradition' in cols:
    ft = c.execute("SELECT faith_tradition, COUNT(*) FROM churches WHERE faith='Islam' AND faith_tradition IS NOT NULL AND faith_tradition!='' GROUP BY faith_tradition ORDER BY COUNT(*) DESC").fetchall()
    print(f"\nIslam faith_tradition distribution ({len(ft)} types):")
    for r in ft:
        print(f"  {r[0]}: {r[1]:,}")

# Check muslim_affiliation columns exist
muslim_cols = [c2 for c2 in cols if 'muslim' in c2.lower()]
print(f"\nMuslim columns: {muslim_cols}")

# Check name_transliterated sample for Islam entries
sample = c.execute("SELECT name, name_transliterated FROM churches WHERE faith='Islam' AND name_transliterated IS NOT NULL AND name != name_transliterated LIMIT 5").fetchall()
print(f"\nSample non-ASCII Islam names (transliterated):")
for r in sample:
    print(f"  '{r[0]}' -> '{r[1]}'")

# Check how many Islam names differ from transliterated
diff = c.execute("SELECT COUNT(*) FROM churches WHERE faith='Islam' AND name_transliterated IS NOT NULL AND name != name_transliterated").fetchone()[0]
print(f"\nIslam entries where name != name_transliterated: {diff:,}")

# How many Islam entries have NULL name_transliterated
null_trans = c.execute("SELECT COUNT(*) FROM churches WHERE faith='Islam' AND (name_transliterated IS NULL OR name_transliterated='')").fetchone()[0]
print(f"Islam entries without name_transliterated: {null_trans:,}")

conn.close()
