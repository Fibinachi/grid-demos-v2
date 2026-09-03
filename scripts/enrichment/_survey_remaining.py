import sqlite3
db = sqlite3.connect(r'E:\grid\churches.db')

cols = [r[1] for r in db.execute('PRAGMA table_info(church_enrichment)').fetchall()]
print(f'Total columns in church_enrichment: {len(cols)}')
print()

# All columns with data
print("=== Columns WITH data (non-null count) ===")
for c in cols:
    cnt = db.execute(f'SELECT COUNT(*) FROM church_enrichment WHERE "{c}" IS NOT NULL AND "{c}" != "" AND "{c}" != 0').fetchone()[0]
    if cnt > 0:
        print(f'  {cnt:>7,}  {c}')
print()

# Hierarchy columns specifically
hierarchy_keywords = ['diocese', 'archdiocese', 'deanery', 'synod', 'presbytery', 'conference', 'district', 'province', 'hierarchy', 'bishop', 'parish']
print("=== Hierarchy columns (any data) ===")
for c in cols:
    for kw in hierarchy_keywords:
        if kw in c.lower():
            cnt = db.execute(f'SELECT COUNT(*) FROM church_enrichment WHERE "{c}" IS NOT NULL AND "{c}" != "" AND "{c}" != 0').fetchone()[0]
            print(f'  {cnt:>7,}  {c}')
            break
print()

# Also check which other tables reference church_enrichment
tables = [r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()]
print("=== All tables in DB ===")
for t in sorted(tables):
    rc = db.execute(f'SELECT COUNT(*) FROM "{t}"').fetchone()[0]
    print(f'  {rc:>9,}  {t}')
