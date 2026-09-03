"""Assess NULL faith records for classification difficulty."""
import sqlite3
conn = sqlite3.connect('churches.db', timeout=30)
c = conn.cursor()

# Overall NULL faith
c.execute('SELECT COUNT(*) FROM churches WHERE faith IS NULL')
total_null = c.fetchone()[0]
print(f'Total NULL faith: {total_null:,}')

# By source
c.execute("""SELECT source, COUNT(*) cnt FROM churches WHERE faith IS NULL 
GROUP BY source ORDER BY cnt DESC LIMIT 20""")
print('\nNULL faith by source:')
for src, cnt in c.fetchall():
    print(f'  {str(src)[:25]:<25} {cnt:>8,}')

# Sample names (top 3 sources)
for src in ['overture_full', 'irs', 'churchunion_scraper']:
    c.execute("""SELECT name, country, city, state FROM churches 
    WHERE faith IS NULL AND source=? ORDER BY RANDOM() LIMIT 15""", (src,))
    rows = c.fetchall()
    print(f'\n--- {src} ({len(rows)} samples) ---')
    for name, ctr, city, st in rows:
        n = (name or '')[:90]
        print(f'  {n:<90} | {str(city or ""):<18} | {str(st or ""):<4} | {str(ctr or "")}')

# Also: check NULL faith with known denomination
c.execute("""SELECT COUNT(*) FROM churches WHERE faith IS NULL AND denomination IS NOT NULL""")
has_denom = c.fetchone()[0]
print(f'\nNULL faith WITH denomination: {has_denom:,}')

# NULL faith with denomination samples
c.execute("""SELECT name, denomination, country FROM churches 
WHERE faith IS NULL AND denomination IS NOT NULL ORDER BY RANDOM() LIMIT 15""")
print('\nNULL faith + HAS denomination (samples):')
for name, denom, ctr in c.fetchall():
    print(f'  {(name or "")[:70]:<70} | denom={str(denom)[:30]:<30} | {ctr or ""}')

# What are the 8 faith categories?
c.execute("""SELECT faith, COUNT(*) cnt FROM churches WHERE faith IS NOT NULL 
GROUP BY faith ORDER BY cnt DESC""")
print('\nExisting faith categories:')
for f, cnt in c.fetchall():
    print(f'  {f:<25} {cnt:>10,}')

conn.close()
