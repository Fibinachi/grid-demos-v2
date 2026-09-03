import sqlite3
c = sqlite3.connect('/home/ec2-user/grantwizard/churches.db')
cur = c.execute('SELECT COUNT(*) FROM churches')
total = cur.fetchone()[0]
cur = c.execute('SELECT source, COUNT(*) FROM churches GROUP BY source')
srcs = cur.fetchall()
cur = c.execute("SELECT COUNT(DISTINCT zip) FROM churches WHERE zip != '' AND zip IS NOT NULL")
zips = cur.fetchone()[0]
cur = c.execute("SELECT COUNT(*) FROM churches WHERE website != '' AND website IS NOT NULL")
websites = cur.fetchone()[0]
cur = c.execute("SELECT COUNT(*) FROM churches WHERE email != '' AND email IS NOT NULL")
emails = cur.fetchone()[0]
print(f'Total records: {total}')
print(f'Unique ZIP codes: {zips}')
print(f'With websites: {websites}')
print(f'With emails: {emails}')
print('Sources:')
for s, n in srcs:
    print(f'  {s}: {n}')
