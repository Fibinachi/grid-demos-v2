import sqlite3
db = sqlite3.connect('E:/grid/data/catholic_directory.db')
print('=== FINAL STATUS ===')
print('Total entries:', db.execute('SELECT COUNT(*) FROM dir_entries').fetchone()[0])
print('Years:', db.execute('SELECT MIN(directory_year), MAX(directory_year) FROM dir_entries').fetchone())
print('With state:', db.execute('SELECT COUNT(*) FROM dir_entries WHERE state IS NOT NULL AND state != ""').fetchone()[0])
print('Matched:', db.execute('SELECT COUNT(*) FROM dir_entries WHERE grid_church_id IS NOT NULL').fetchone()[0])
db.close()