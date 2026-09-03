"""Additional Salvation Army analysis."""
import sqlite3

db = sqlite3.connect('E:\\grid\\churches.db')

# French/Canadian names
print('=== French names ===')
cur = db.execute("SELECT name, city, country, COUNT(*) FROM churches WHERE name LIKE '%Arm\u00e9e%' AND name LIKE '%Salut%' GROUP BY name, city, country ORDER BY COUNT(*) DESC LIMIT 30")
for r in cur:
    print(f'  {r[3]:>3} | {r[0]:70s} | {str(r[1] or ""):25s} | {r[2]}')

# Non-English translations
print('\n=== Translations / other languages ===')
for lang, label in [('%Heilsarmee%', 'German'), ('%Frelsesarmeen%', 'Norwegian'), 
                    ('%Frälsningsarmén%', 'Swedish'), ('%Pelastusarmeija%', 'Finnish'),
                    ('%Ejército de Salvación%', 'Spanish'), ('%Exército de Salvação%', 'Portuguese'),
                    ('%Armia Zbawienia%', 'Polish'), ('%Spasitelj%', 'Croatian'),
                    ('%Pelastava Armeija%', 'Finnish2')]:
    cur = db.execute("SELECT COUNT(*) FROM churches WHERE name LIKE ?", (lang,))
    c = cur.fetchone()[0]
    if c > 0:
        cur2 = db.execute("SELECT name, city, country FROM churches WHERE name LIKE ? LIMIT 3", (lang,))
        samples = list(cur2)
        for r in samples:
            print(f'  {label:12s} | {c:>3}x | {r[0]:65s} | {str(r[1] or ""):20s} | {r[2]}')

# Thrift stores
print('\n=== Thrift/charity shop entries ===')
cur = db.execute("SELECT name, city, country FROM churches WHERE name LIKE '%Thrift%' AND name LIKE '%Salvation Army%' LIMIT 20")
for r in cur:
    print(f'  {r[0]:70s} | {str(r[1] or ""):25s} | {r[2]}')

# Band/Songster entries
print('\n=== Band/Songster entries ===')
cur = db.execute("SELECT name, city, country FROM churches WHERE (name LIKE '%Band%' OR name LIKE '%Songster%') AND name LIKE '%Salvation Army%' LIMIT 10")
for r in cur:
    print(f'  {r[0]:70s} | {str(r[1] or ""):25s} | {r[2]}')

# DHQ/THQ entries
print('\n=== DHQ/THQ entries ===')
cur = db.execute("SELECT name, city, state, country FROM churches WHERE (name LIKE '%DHQ%' OR name LIKE '%THQ%' OR name LIKE '% HQ%') AND name LIKE '%Salvation Army%' GROUP BY name, city, state, country")
for r in cur:
    print(f'  {r[0]:60s} | {str(r[1] or ""):20s} | {str(r[2] or ""):10s} | {r[3]}')

# Source breakdown
print('\n=== Source breakdown ===')
cur = db.execute("SELECT source, COUNT(*) FROM churches WHERE name LIKE '%Salvation Army%' GROUP BY source ORDER BY COUNT(*) DESC")
for r in cur:
    print(f'  {r[1]:>6} | {r[0]}')

# City populated vs not
print('\n=== City populated vs not ===')
cur = db.execute("SELECT COUNT(*) FROM churches WHERE name LIKE '%Salvation Army%' AND city IS NOT NULL AND city != \'\'")
print(f'  With city: {cur.fetchone()[0]}')
cur = db.execute("SELECT COUNT(*) FROM churches WHERE name LIKE '%Salvation Army%' AND (city IS NULL OR city = \'\')")
print(f'  Without city: {cur.fetchone()[0]}')

# Social services vs corps
print('\n=== Social service type entries ===')
for kw, label in [('%Thrift%', 'Thrift'), ('%Social%', 'Social'), ('%Employment%', 'Employment'),
                  ('%ARC%', 'ARC'), ('%Red Shield%', 'Red Shield'), ('%Shelter%', 'Shelter'),
                  ('%Men%', 'Men'), ('%Women%', 'Women'), ('%Family%', 'Family'),
                  ('%Youth%', 'Youth'), ('%Senior%', 'Senior'), ('%School%', 'School'),
                  ('%Home%', 'Home'), ('%Lodge%', 'Lodge'), ('%Nursing%', 'Nursing'),
                  ('%Manor%', 'Manor'), ('%Court%', 'Court'), ('%Hostel%', 'Hostel')]:
    cur = db.execute("SELECT COUNT(*) FROM churches WHERE name LIKE ? AND name LIKE '%Salvation Army%'", (kw,))
    print(f'  {label:10s}: {cur.fetchone()[0]}')

# Check for unique "The Salvation Army" entries
print('\n=== Type classification by keyword ===')
# Kingdom Hall of Jehovah... pattern - check for similar SA patterns
cur = db.execute("SELECT name, COUNT(*) FROM churches WHERE name LIKE '%Salvation Army%' AND name NOT IN ('Salvation Army', 'SALVATION ARMY', 'salvation army', 'Salvation army') AND name NOT LIKE 'GOVERNING COUNCIL%' AND city IS NOT NULL AND city != \'\' GROUP BY name ORDER BY COUNT(*) DESC LIMIMT 40")
# Actually let me just do a frequency query on first word after 'Salvation Army'
print('\n=== Post-SA first word patterns (in names > 25 chars) ===')
cur = db.execute("SELECT name FROM churches WHERE name LIKE '%Salvation Army%' AND LENGTH(name) > 25 AND name NOT LIKE 'GOVERNING COUNCIL%' LIMIT 100")
words = {}
for r in cur:
    name = r[0]
    # Extract the word/phrase after "Salvation Army"
    parts = name.upper().split('SALVATION ARMY')
    if len(parts) > 1:
        suffix = parts[1].strip().strip('-').strip()
        first_word = suffix.split()[0] if suffix else '(empty)'
        words[first_word] = words.get(first_word, 0) + 1
for w in sorted(words.items(), key=lambda x: -x[1])[:30]:
    print(f'  {w[1]:>4} | {w[0]}')

db.close()
