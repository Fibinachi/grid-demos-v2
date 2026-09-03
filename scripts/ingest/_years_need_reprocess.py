import sqlite3
db = sqlite3.connect('E:/grid/data/catholic_directory.db')

# Years with high % of entries missing city
print('Years with entries but missing city (needs re-parse):')
r = db.execute("""
    SELECT directory_year, COUNT(*) as total, 
           SUM(CASE WHEN city IS NULL THEN 1 ELSE 0 END) as missing_city,
           SUM(CASE WHEN diocese IS NULL THEN 1 ELSE 0 END) as missing_diocese
    FROM dir_entries 
    GROUP BY directory_year
    ORDER BY missing_city DESC
    LIMIT 20
""").fetchall()
for y,t,c,d in r:
    pct = (c/t*100) if t > 0 else 0
    print(f'  {y}: {t} entries, {c} missing city ({pct:.0f}%)')

# Years with no clergy extracted
print('\nYears with entries but no clergy (needs re-parse):')
r = db.execute("""
    SELECT e.directory_year, COUNT(*) as entries, COUNT(c.id) as clergy
    FROM dir_entries e
    LEFT JOIN dir_clergy c ON c.entry_id = e.id
    GROUP BY e.directory_year
    ORDER BY clergy ASC
    LIMIT 20
""").fetchall()
for y,e,cl in r:
    if e > 50 and cl == 0:
        print(f'  {y}: {e} entries, {cl} clergy - RE-PARSE NEEDED')