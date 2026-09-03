"""Temp script: check current faith distribution and minority faith patterns"""
import sqlite3
conn = sqlite3.connect('E:\\grid\\churches.db')
c = conn.cursor()

print('=== CURRENT FAITH DISTRIBUTION ===')
rows = c.execute('SELECT COALESCE(faith,"NULL"), COUNT(*) FROM churches GROUP BY faith ORDER BY COUNT(*) DESC LIMIT 20').fetchall()
for r in rows:
    print(f'  {str(r[0]):20s} {r[1]:>8,}')

print()
print('=== FAITH_TRADITION DISTRIBUTION ===')
rows = c.execute('SELECT COALESCE(faith_tradition,"NULL"), COUNT(*) FROM churches GROUP BY faith_tradition ORDER BY COUNT(*) DESC LIMIT 20').fetchall()
for r in rows:
    print(f'  {str(r[0]):25s} {r[1]:>8,}')

print()
print('=== SUBTRADITION ===')
rows = c.execute('SELECT COALESCE(subtradition,"NULL"), COUNT(*) FROM churches WHERE subtradition IS NOT NULL AND subtradition != "" GROUP BY subtradition ORDER BY COUNT(*) DESC LIMIT 20').fetchall()
for r in rows:
    print(f'  {str(r[0]):30s} {r[1]:>8,}')

print()
# Check minority faith counts
MINORITY_KEYWORDS = {
    'Shinto': ['shinto'],
    'Jain': ['jain'],
    'Sikh': ['sikh', 'gurdwara'],
    'Baha\'i': ['bahai', 'bahaullah', 'baha\'i'],
    'Taoist': ['taoist', 'taoism', 'daoist'],
    'Zoroastrian': ['zoroastrian', 'parsi', 'zarathushtra'],
    'Confucian': ['confucian', 'confucius'],
    'Animist': ['animist'],
    'Pagan': ['pagan', 'wicca', 'wiccan', 'druid', 'neopagan', 'asatru'],
}

print('=== NAME-BASED MINORITY FAITH CANDIDATES (by keyword match) ===')
for faith_name, keywords in MINORITY_KEYWORDS.items():
    like_clauses = ' OR '.join([f'name LIKE ?' for k in keywords])
    params = [f'%{k}%' for k in keywords]
    rows = c.execute(f'SELECT faith, faith_tradition, COUNT(*) FROM churches WHERE ({like_clauses}) GROUP BY faith ORDER BY COUNT(*) DESC', params).fetchall()
    total = sum(r[2] for r in rows)
    print(f'\n  {faith_name:15s} (total candidate matches: {total:>6,})')
    for r in rows[:5]:
        print(f'    faith={str(r[0]):12s} trad={str(r[1]):20s} count={r[2]:>6,}')

# Check all faith=Other records
print()
print('=== FAITH=OTHER BREAKDOWN ===')
rows = c.execute('SELECT faith_tradition, COUNT(*) FROM churches WHERE faith="Other" GROUP BY faith_tradition ORDER BY COUNT(*) DESC').fetchall()
for r in rows:
    print(f'  trad={str(r[0]):25s} {r[1]:>6,}')
