import sqlite3, re, json
from pathlib import Path

conn = sqlite3.connect('E:/grid/wpa.db')
cur = conn.cursor()

# Load all entries
entries = cur.execute("SELECT id, church_name FROM wpa_churches").fetchall()

final_entries = []
for id, name in entries:
    name = name.strip()
    
    # Split on patterns like " (Rt. 2) ChurchName (Rt."
    parts = re.split(r'\s*\([^)]*Rt\.[^)]*\)\s*', name)
    
    for part in parts:
        part = part.strip('. ,;-')
        part = re.sub(r'\s{3,}.*$', '', part)  # Remove trailing junk
        
        # Clean OCR
        part = part.replace('#', 't').replace('vv', 'w')
        part = re.sub(r'\bthurch\b', 'Church', part, re.IGNORECASE)
        
        if len(part) > 5 and len(part) < 100:
            # Skip headers
            if not any(x in part.lower() for x in ['directory', 'historical records', 'work projects', 'prepared by', 'digitized', 'preface', 'table of contents']):
                final_entries.append(part)

# Dedupe
seen = set()
unique = []
for e in final_entries:
    if e not in seen:
        seen.add(e)
        unique.append(e)

print(f'Original: {len(entries)}, After split/clean: {len(unique)}')

# Clear and reimport
cur.execute("DELETE FROM wpa_churches")
for name in unique[:5000]:
    cur.execute("INSERT INTO wpa_churches (church_name) VALUES (?)", (name,))

conn.commit()
conn.close()

# Save
Path('E:/grid/data/wpa/clean_final.json').write_text(json.dumps(unique), encoding='utf-8')
print(f'Saved {len(unique)} entries to clean_final.json')