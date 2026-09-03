"""Deep audit of minority faith misclassifications"""
import sqlite3, sys

def s(val):
    return str(val) if val is not None else ""

conn = sqlite3.connect('E:\\grid\\churches.db')
c = conn.cursor()

def show(title, query, params=None, limit=15, cols=5):
    print(f'\n=== {title} ===')
    if params:
        rows = c.execute(query, params).fetchall()
    else:
        rows = c.execute(query).fetchall()
    print(f'  ({len(rows)} rows)')
    for r in rows[:limit]:
        parts = []
        for i in range(cols):
            if i < len(r):
                parts.append(s(r[i]))
        print('  ' + ' | '.join(parts))

# 1. JAIN
show('JAIN faith breakdown',
     "SELECT COALESCE(faith,'NULL'), COUNT(*) FROM churches WHERE name COLLATE NOCASE LIKE '%jain%' GROUP BY faith ORDER BY COUNT(*) DESC",
     limit=10, cols=2)

show('JAIN (faith=Hindu) samples',
     "SELECT id, name, faith_tradition, denomination FROM churches WHERE faith='Hindu' AND name COLLATE NOCASE LIKE '%jain%' LIMIT 20",
     cols=4)

# 2. ZOROASTRIAN
show('ZOROASTRIAN faith breakdown',
     "SELECT faith, COUNT(*) FROM churches WHERE (name COLLATE NOCASE LIKE '%zoroastrian%' OR name COLLATE NOCASE LIKE '%parsi%' OR name COLLATE NOCASE LIKE '%zarathushtra%') GROUP BY faith ORDER BY COUNT(*) DESC",
     limit=10, cols=2)

show('ZOROASTRIAN (faith=Christian) samples',
     "SELECT id, name, faith_tradition FROM churches WHERE faith='Christian' AND (name COLLATE NOCASE LIKE '%zoroastrian%' OR name COLLATE NOCASE LIKE '%parsi%') LIMIT 10",
     cols=3)

# 3. CONFUCIAN
show('CONFUCIAN faith breakdown',
     "SELECT faith, COUNT(*) FROM churches WHERE (name COLLATE NOCASE LIKE '%confucian%' OR name COLLATE NOCASE LIKE '%confucius%') GROUP BY faith ORDER BY COUNT(*) DESC",
     limit=10, cols=2)

show('CONFUCIAN name samples',
     "SELECT id, name, faith FROM churches WHERE (name COLLATE NOCASE LIKE '%confucian%' OR name COLLATE NOCASE LIKE '%confucius%') LIMIT 15",
     cols=3)

# 4. TAOIST
show('TAOIST faith breakdown',
     "SELECT faith, COUNT(*) FROM churches WHERE (name COLLATE NOCASE LIKE '%taoist%' OR name COLLATE NOCASE LIKE '%taoism%' OR name COLLATE NOCASE LIKE '%daoist%') GROUP BY faith ORDER BY COUNT(*) DESC",
     limit=10, cols=2)

show('TAOIST misclassified (not Taoist)',
     "SELECT id, name, faith, faith_tradition FROM churches WHERE (name COLLATE NOCASE LIKE '%taoist%' OR name COLLATE NOCASE LIKE '%taoism%') AND COALESCE(faith,'') != 'Taoist' LIMIT 10",
     cols=4)

# 5. SHINTO
show('SHINTO faith breakdown',
     "SELECT faith, COUNT(*) FROM churches WHERE name COLLATE NOCASE LIKE '%shinto%' GROUP BY faith ORDER BY COUNT(*) DESC",
     limit=10, cols=2)

show('SHINTO misclassified (not Shinto)',
     "SELECT id, name, faith, faith_tradition FROM churches WHERE name COLLATE NOCASE LIKE '%shinto%' AND COALESCE(faith,'') != 'Shinto' LIMIT 10",
     cols=4)

# 6. BAHAI
show('BAHAI faith breakdown',
     "SELECT faith, COUNT(*) FROM churches WHERE (name COLLATE NOCASE LIKE '%bahai%' OR name COLLATE NOCASE LIKE '%bahaullah%') GROUP BY faith ORDER BY COUNT(*) DESC",
     limit=10, cols=2)

show('BAHAI (faith=Christian) samples',
     "SELECT id, name, faith_tradition FROM churches WHERE faith='Christian' AND (name COLLATE NOCASE LIKE '%bahai%' OR name COLLATE NOCASE LIKE '%bahaullah%') LIMIT 10",
     cols=3)

# 7. PAGAN / WICCA / DRUID
show('PAGAN/WICCA/DRUID faith breakdown',
     "SELECT faith, COUNT(*) FROM churches WHERE (name COLLATE NOCASE LIKE '%pagan%' OR name COLLATE NOCASE LIKE '%wicca%' OR name COLLATE NOCASE LIKE '%druid%') GROUP BY faith ORDER BY COUNT(*) DESC",
     limit=10, cols=2)

show('PAGAN (faith=Christian) samples',
     "SELECT id, name, faith_tradition, country FROM churches WHERE faith='Christian' AND name COLLATE NOCASE LIKE '%pagan%' LIMIT 10",
     cols=4)

# 8. SIKH misclassified
show('SIKH (faith=Hindu) samples',
     "SELECT id, name, faith_tradition FROM churches WHERE faith='Hindu' AND (name COLLATE NOCASE LIKE '%sikh%' OR name COLLATE NOCASE LIKE '%gurdwara%') LIMIT 10",
     cols=3)

show('SIKH (faith=Christian) samples',
     "SELECT id, name, faith_tradition FROM churches WHERE faith='Christian' AND (name COLLATE NOCASE LIKE '%sikh%' OR name COLLATE NOCASE LIKE '%gurdwara%') LIMIT 10",
     cols=3)

conn.close()
