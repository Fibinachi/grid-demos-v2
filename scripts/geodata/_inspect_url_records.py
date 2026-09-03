import sqlite3
db = sqlite3.connect('churches.db')
c = db.cursor()

c.execute("SELECT name,source FROM churches WHERE country='US' AND (name LIKE '%http://%' OR name LIKE '%https://%') GROUP BY name ORDER BY COUNT(*) DESC LIMIT 20")
print('=== URL-in-name records ===')
for r in c.fetchall():
    print(f'  {str(r[0])[:80]:80s} src={r[1]:25s}')

c.execute("SELECT c.rowid,c.name,c.source,c.city,c.state,c.denomination,cc.website,cc.youtube_url FROM churches c LEFT JOIN church_contacts cc ON c.id=cc.church_id WHERE c.name LIKE '%YFMC%'")
print('\n=== YFMC ===')
for r in c.fetchall():
    print(f'  rowid={r[0]} name={str(r[1])[:70]:70s} src={r[2]} city={r[3]} st={r[4]} denom={r[5]} web={r[6]} yt={r[7]}')

c.execute("SELECT rowid,name,source FROM churches WHERE rowid=131148")
print('\n=== SAINT JOHN PAUL IIS ===')
for r in c.fetchall():
    print(f'  rowid={r[0]} name={str(r[1])[:90]} src={r[2]}')

c.execute("SELECT rowid,name,source FROM churches WHERE rowid=173051")
print('\n=== UNITEDHEARTS ===')
for r in c.fetchall():
    print(f'  rowid={r[0]} name={r[1]} src={r[2]}')

c.execute("SELECT rowid,name,source FROM churches WHERE rowid=134911")
print('\n=== SAINT PATRICK FACEBOOK ===')
for r in c.fetchall():
    print(f'  rowid={r[0]} name={r[1]} src={r[2]}')

# Count URL-as-name records total
c.execute("SELECT COUNT(*) FROM churches WHERE country='US' AND (name LIKE '%http://%' OR name LIKE '%https://%')")
print(f'\nTotal US records with URL in name: {c.fetchone()[0]:,}')

db.close()
