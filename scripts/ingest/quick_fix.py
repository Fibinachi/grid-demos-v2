import sqlite3, re

conn = sqlite3.connect('E:/grid/wpa.db')
cur = conn.cursor()

entries = cur.execute("SELECT id, church_name FROM wpa_churches").fetchall()

fixed = 0
removed = 0

for id, name in entries:
    original = name
    
    # Remove concatenated "Assembly of God Assembly of God"
    name = re.sub(r'Assembly\s+of\s+God\s+Assembly\s+of\s+God', 'Assembly of God', name, flags=re.IGNORECASE)
    
    # Fix "North NWew Hope" -> "North New Hope"
    name = re.sub(r'\b(N|e)W(e)?w\s+Hope\b', 'New Hope', name, flags=re.IGNORECASE)
    
    # Remove fragmented names starting with "g " or similar
    name = re.sub(r'\bg\s+Cotton\s+Belt', '', name)
    name = re.sub(r'\s{3,}.*$', '', name)
    
    # Remove if starts with "Craighead" (line noise)
    if name.startswith('Craighead Lake'):
        removed += 1
        continue
    
    if name != original:
        cur.execute("UPDATE wpa_churches SET church_name = ? WHERE id = ?", (name, id))
        fixed += 1

conn.commit()
print(f"Fixed: {fixed}, Removed: {removed}")
print(f"Total: {conn.execute('SELECT COUNT(*) FROM wpa_churches').fetchone()[0]}")

conn.close()