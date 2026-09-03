"""Write all distinct sources to a text file."""
import sqlite3

db = sqlite3.connect('E:\\grid\\churches.db')
c = db.cursor()
c.execute('SELECT DISTINCT source FROM churches ORDER BY source')
sources = [r[0] for r in c.fetchall()]

with open('e:\\grid\\_all_sources.txt', 'w', encoding='utf-8') as f:
    f.write(f'Total distinct source values: {len(sources)}\n\n')
    for s in sources:
        c2 = db.cursor()
        c2.execute('SELECT COUNT(*) FROM churches WHERE source = ?', (s,))
        cnt = c2.fetchone()[0]
        f.write(f'{str(s):75s} {cnt:>10,}\n')

print(f'Wrote {len(sources)} sources to e:\\grid\\_all_sources.txt')
db.close()
