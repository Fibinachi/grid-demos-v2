import sqlite3
cath = sqlite3.connect('E:/grid/data/catholic_directory.db')

print('=== Catholic Directory Database Final Status ===')
print()

total = cath.execute('SELECT COUNT(*) FROM dir_entries').fetchone()[0]
years = cath.execute('SELECT MIN(directory_year), MAX(directory_year), COUNT(DISTINCT directory_year) FROM dir_entries').fetchone()
matched = cath.execute('SELECT COUNT(*) FROM dir_entries WHERE grid_church_id IS NOT NULL').fetchone()[0]

print(f'Total entries: {total:,}')
print(f'Year range: {years[0]} - {years[1]} ({years[2]} years)')
print(f'Matched to GRID: {matched:,} ({100*matched/total:.1f}%)')
print()

# Source breakdown
deepseek = cath.execute('SELECT COUNT(*) FROM dir_entries WHERE directory_year IN (2021, 1865, 1868, 1938, 1944)').fetchone()[0]
cleaned = cath.execute("SELECT COUNT(*) FROM dir_entries WHERE notes LIKE '[Official CD%'").fetchone()[0]
clergy = cath.execute("SELECT COUNT(*) FROM dir_entries WHERE notes LIKE '%Catholic Directory%'").fetchone()[0]
print(f'DeepSeek-parsed: {deepseek:,}')
print(f'Cleaned v3: {cleaned:,}')
print(f'Clergy data: {clergy:,}')

cath.close()