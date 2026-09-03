import sqlite3
c = sqlite3.connect('/home/ec2-user/grantwizard/churches.db')
# Check zip format
cur = c.execute('SELECT zip, COUNT(*) as cnt FROM churches WHERE zip != "" AND zip IS NOT NULL GROUP BY zip ORDER BY cnt DESC LIMIT 10')
print('Top 10 ZIPs:')
for r in cur.fetchall():
    print(f'  "{r[0]}" x {r[1]}')
# Count 5-digit vs other formats
cur = c.execute("SELECT CASE WHEN length(substr(zip,1,5))=5 THEN '5digit' WHEN length(zip)>5 THEN 'longer' ELSE 'other' END as fmt, COUNT(DISTINCT substr(zip,1,5)) FROM churches WHERE zip != '' AND zip IS NOT NULL GROUP BY fmt")
print('ZIP format breakdown:')
for r in cur.fetchall():
    print(f'  {r[0]}: {r[1]}')
# Count unique 5-digit zips
cur = c.execute("SELECT COUNT(DISTINCT substr(zip,1,5)) FROM churches WHERE zip != '' AND zip IS NOT NULL AND substr(zip,1,5) GLOB '[0-9][0-9][0-9][0-9][0-9]'")
unique = cur.fetchone()[0]
print(f'Unique 5-digit numeric ZIPs: {unique}')
