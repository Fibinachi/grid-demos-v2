import sqlite3
conn = sqlite3.connect('churches.db')
cur = conn.cursor()

# Total churches with websites in the DB
cur.execute("SELECT COUNT(*) FROM churches WHERE website != '' AND website IS NOT NULL")
total_websites = cur.fetchone()[0]

# How many of those have EINs
cur.execute("SELECT COUNT(*) FROM churches WHERE website != '' AND website IS NOT NULL AND ein != '' AND ein IS NOT NULL")
with_ein = cur.fetchone()[0]

print(f"Total churches with websites: {total_websites}")
print(f"With EIN: {with_ein} ({with_ein/total_websites*100:.1f}%)")

# Sample
cur.execute("SELECT website, ein, name FROM churches WHERE website != '' AND ein != '' AND ein IS NOT NULL LIMIT 5")
for r in cur.fetchall():
    print(f"  {r[0]}: EIN={r[1]}  {r[2][:50]}")

conn.close()
