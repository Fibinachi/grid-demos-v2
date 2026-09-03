import sqlite3
db = sqlite3.connect('E:/grid/data/catholic_directory.db')

# Check entries with truncated names (ending mid-word)
r = db.execute("""
    SELECT directory_year, COUNT(*) 
    FROM dir_entries 
    WHERE name LIKE '%, Rev' OR name LIKE '%, R'
    GROUP BY directory_year 
    ORDER BY directory_year
""").fetchall()
print('Truncated entries ending in , R or , Rev:')
for y,c in r:
    print(f'  {y}: {c}')

# Check sample entries
print('\nSample truncated entries:')
r = db.execute("""
    SELECT directory_year, name FROM dir_entries 
    WHERE name LIKE '%, Rev%' OR name LIKE '%; R%'
    LIMIT 10
""").fetchall()
for y,n in r:
    print(f'  {y}: {n}')