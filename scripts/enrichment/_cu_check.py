import sqlite3
conn = sqlite3.connect('churches.db')
new = conn.execute("SELECT COUNT(*) FROM churches WHERE source='churchunion_scraper'").fetchone()[0]
dup = conn.execute("SELECT COUNT(*) FROM church_sources WHERE source_name='churchunion_scraper'").fetchone()[0]
total = conn.execute('SELECT COUNT(*) FROM churches').fetchone()[0]
print(f'churchunion churches: {new:,}')
print(f'churchunion duplicates logged: {dup:,}')
print(f'total churches: {total:,}')
conn.close()
