import sqlite3
cath = sqlite3.connect('E:/grid/data/catholic_directory.db')

print('=== Final Catholic Directory Status ===')
print()

total = cath.execute('SELECT COUNT(*) FROM dir_entries').fetchone()[0]
print(f'Total entries: {total:,}')

years = cath.execute('SELECT MIN(directory_year), MAX(directory_year), COUNT(DISTINCT directory_year) FROM dir_entries').fetchone()
print(f'Year range: {years[0]} - {years[1]} ({years[2]} years)')

matched = cath.execute('SELECT COUNT(*) FROM dir_entries WHERE grid_church_id IS NOT NULL').fetchone()[0]
print(f'Matched to GRID: {matched:,} ({100*matched/total:.1f}%)')

print()

# Count by year
print('Top matched years:')
for r in cath.execute('SELECT directory_year, SUM(CASE WHEN grid_church_id IS NOT NULL THEN 1 ELSE 0 END) as m, COUNT(*) as t FROM dir_entries GROUP BY directory_year ORDER BY m DESC LIMIT 15').fetchall():
    print(f'  {r[0]}: {r[1]:,}/{r[2]:,}')

cath.close()