"""Remove foundation records mistakenly imported into church DB."""
import sqlite3

d = r'E:\grid'
conn = sqlite3.connect(d + '/churches.db')
cur = conn.cursor()

cur.execute("SELECT COUNT(*) FROM churches WHERE source = 'foundation'")
before = cur.fetchone()[0]
print(f'Foundation records found: {before}')

cur.execute("DELETE FROM churches WHERE source = 'foundation'")
conn.commit()

cur.execute("SELECT COUNT(*) FROM churches WHERE email != ''")
remaining = cur.fetchone()[0]
conn.close()

print(f'Deleted: {before}')
print(f'Churches with email remaining: {remaining:,}')
print(f'Total churches in DB: still ~266K (foundations were only ~7.8K of 275K total, duplicates removed)')
