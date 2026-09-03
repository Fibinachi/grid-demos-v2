import sqlite3, re

conn = sqlite3.connect('E:/grid/wpa.db')
cur = conn.cursor()

# Load all entries
entries = cur.execute("SELECT id, church_name FROM wpa_churches").fetchall()

# Clean and split concatenated entries
final = []
for id, name in entries:
    name = re.sub(r'\s{5,}.*$', '', name).strip()
    
    # Split on known separators for concatenated entries
    # Pattern: "Church A (Rt. 1) Church B (Rt. 2)"
    parts = re.split(r'\s+(?:Assembly|First|Second|Third|Mt\.|Social|Union|Oak|Pleasant|Bethel|New|Old)\s+', name)
    
    for part in parts:
        part = part.strip()
        if len(part) > 5 and not any(x in part.lower() for x in ['directory', 'historical', 'work projects', 'prepared by', 'digitized', 'preface', 'table of contents']):
            final.append(part)

# Clear and re-import
cur.execute("DELETE FROM wpa_churches")
for name in final[:5000]:
    cur.execute("INSERT INTO wpa_churches (church_name, source) VALUES (?, 'WPA')", (name,))

conn.commit()
conn.close()

print(f"Final entries: {len(final)}")