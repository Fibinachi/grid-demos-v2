"""Fix any denominational churches wrongly tagged as non-denom."""
import sqlite3
conn = sqlite3.connect('churches.db', timeout=30)
c = conn.cursor()
total = 0

# Check for denominational keywords in non-denom tagged records
checks = ['lutheran','baptist','methodist','catholic','presbyterian',
          'episcopal','adventist','nazarene','pentecostal','orthodox',
          'anglican','mennonite','reformed','congregational','holiness',
          'cogic','assembly of god','church of god','united methodist',
          'evangelical free','wesleyan','salvation army']

for kw in checks:
    c.execute(f"SELECT COUNT(*) FROM churches WHERE denomination='Non-Denominational' AND LOWER(name) LIKE '%{kw}%'")
    cnt = c.fetchone()[0]
    if cnt > 0:
        c.execute(f"UPDATE churches SET denomination=NULL WHERE denomination='Non-Denominational' AND LOWER(name) LIKE '%{kw}%'")
        print(f"  Reverted {kw}: {c.rowcount}")
        total += c.rowcount

# Also check for "church" in name (non-denom churches usually don't use "church" either)
# But this is debatable - many DO say "Oasis Church" etc. Let's just fix the clear denominational ones.

conn.commit()
print(f"\nTotal reverted: {total}")
conn.close()
