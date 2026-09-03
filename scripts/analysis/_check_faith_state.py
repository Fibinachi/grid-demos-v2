import sqlite3
conn = sqlite3.connect('E:/grid/churches.db')
c = conn.cursor()
print('=== Faith breakdown ===')
c.execute('SELECT faith, COUNT(*) FROM churches GROUP BY faith ORDER BY COUNT(*) DESC')
for r in c.fetchall():
    print(f'  {r[0]:15s} {r[1]:>8,}')
print()
print('=== Tradition coverage per faith ===')
c.execute("SELECT faith, COUNT(*) as total, COUNT(CASE WHEN tradition!='' AND tradition IS NOT NULL THEN 1 END) as with_trad FROM churches GROUP BY faith ORDER BY COUNT(*) DESC")
for r in c.fetchall():
    pct = r[2]/r[1]*100 if r[1] > 0 else 0
    print(f'  {r[0]:15s} {r[1]:>8,} total, {r[2]:>8,} with tradition ({pct:.1f}%)')

print()
print('=== Problematic landmark_types per faith ===')
c.execute("""SELECT faith, landmark_type, COUNT(*) as cnt FROM churches 
    WHERE landmark_type IN ('church','temple','mosque','shrine','synagogue','center','other','unknown')
    AND faith NOT IN ('Christian','Islam')
    GROUP BY faith, landmark_type ORDER BY faith, cnt DESC LIMIT 30""")
for r in c.fetchall():
    print(f'  {r[0]:15s} {r[1]:20s} {r[2]:>8,}')
conn.close()
