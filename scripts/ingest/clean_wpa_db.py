import sqlite3, re

conn = sqlite3.connect('E:/grid/wpa.db')
cur = conn.cursor()

# Load all entries
entries = cur.execute("SELECT id, church_name FROM wpa_churches").fetchall()

# Clean and filter
good = []
for id, name in entries:
    # Remove header artifacts
    name = re.sub(r'\s{5,}.*$', '', name).strip()
    name = re.sub(r'[|`\\\'<>]{2,}', '', name)
    
    # Skip headers
    if any(x in name.lower() for x in ['directory', 'historical records', 'work projects', 'prepared by', 'digitized', 'preface', 'table of contents']):
        continue
    if len(name) < 5:
        continue
    
    good.append((name, id))

# Update
for name, id in good:
    cur.execute("UPDATE wpa_churches SET church_name = ? WHERE id = ?", (name, id))

conn.commit()

# Count
for row in cur.execute('SELECT state, COUNT(*) as c FROM wpa_churches GROUP BY state ORDER BY c DESC').fetchall():
    print(f"{row[0]}: {row[1]}")

print(f"\nTotal clean entries: {len(good)}")
conn.close()