import sqlite3
conn = sqlite3.connect('churches.db')
conn.execute("PRAGMA journal_mode=DELETE")
tables = [r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name")]
for t in tables:
    cnt = conn.execute(f"SELECT COUNT(*) FROM [{t}]").fetchone()[0]
    cols = [r[1] for r in conn.execute(f"PRAGMA table_info([{t}])")]
    link = ''
    if 'church_id' in cols: link = 'church_id'
    elif 'county_fips' in cols: link = 'county_fips'
    elif 'id' in cols and t != 'churches': link = 'id'
    elif t == 'churches': link = 'id (PK)'
    print(f"{t:40s} {cnt:>10,} {len(cols):>4} cols  link={link}")
conn.close()
