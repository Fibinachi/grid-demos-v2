import sqlite3
db = sqlite3.connect('E:/grid/data/catholic_directory.db')
total = db.execute('SELECT COUNT(*) FROM dir_entries').fetchone()[0]
matched = db.execute('SELECT COUNT(*) FROM dir_entries WHERE grid_church_id IS NOT NULL').fetchone()[0]
state_filled = db.execute('SELECT COUNT(*) FROM dir_entries WHERE state IS NOT NULL AND state != ""').fetchone()[0]
print(f'Total: {total:,}')
print(f'Matched: {matched:,} ({100*matched/total:.1f}%)')
print(f'State filled: {state_filled:,}')

print()
print('Match rate by year:')
for r in db.execute('SELECT directory_year, COUNT(*) as t, SUM(CASE WHEN grid_church_id IS NOT NULL THEN 1 ELSE 0 END) as m FROM dir_entries GROUP BY directory_year ORDER BY directory_year').fetchall()[:20]:
    pct = 100 * r[2] / r[1] if r[1] > 0 else 0
    print(f'  {r[0]}: {r[2]:,}/{r[1]:,} ({pct:.1f}%)')

db.close()