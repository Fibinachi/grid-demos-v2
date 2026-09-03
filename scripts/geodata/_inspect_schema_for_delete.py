"""Quick schema inspection for safe deletion planning."""
import sqlite3

db = sqlite3.connect('E:/grid/churches.db')

# Foreign keys on churches
print("FOREIGN KEYS on churches:")
fks = db.execute('PRAGMA foreign_key_list(churches)').fetchall()
for fk in fks:
    print(f"  {fk}")

# Tables that might reference churches
print("\nTABLES with FK refs to churches:")
tables = [r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")]
for tname in tables:
    t_fks = db.execute(f'PRAGMA foreign_key_list("{tname}")').fetchall()
    for fk in t_fks:
        if fk[2] == 'churches' or fk[4] == 'church_id':
            print(f"  {tname}: {fk}")

# Count child records for target state-only records
print("\nChild records for target scraper state-only records:")
so_data = db.execute("""
    SELECT c.id FROM churches c
    WHERE c.latitude IS NULL AND c.longitude IS NULL
    AND c.country = 'US' AND c.state IS NOT NULL AND c.state != ''
    AND (c.city IS NULL OR c.city = '')
    AND (c.zip IS NULL OR c.zip = '')
    AND (c.address IS NULL OR c.address = '')
    AND c.source IN ('catholic_diocese_scrape', 'diocese_sitemap')
    LIMIT 1000
""").fetchall()
if so_data:
    ids = [str(r[0]) for r in so_data]
    id_str = ','.join(ids)
    for tname in tables:
        if tname == 'churches':
            continue
        cols = [c[1] for c in db.execute(f'PRAGMA table_info("{tname}")')]
        if 'church_id' in cols:
            cnt = db.execute(f'SELECT COUNT(*) FROM "{tname}" WHERE church_id IN ({id_str})').fetchone()[0]
            if cnt > 0:
                print(f"  {tname}: {cnt:,} rows referencing target records")

# Total child records across all tables
print("\nTotal target records:")
cnt = db.execute("""
    SELECT COUNT(*) FROM churches c
    WHERE c.latitude IS NULL AND c.longitude IS NULL
    AND c.country = 'US' AND c.state IS NOT NULL AND c.state != ''
    AND (c.city IS NULL OR c.city = '')
    AND (c.zip IS NULL OR c.zip = '')
    AND (c.address IS NULL OR c.address = '')
    AND c.source IN ('catholic_diocese_scrape', 'diocese_sitemap')
""").fetchone()[0]
print(f"  Total target records: {cnt:,}")

db.close()
