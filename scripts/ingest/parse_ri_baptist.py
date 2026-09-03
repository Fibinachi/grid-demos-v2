#!/usr/bin/env python3
"""
WPA Rhode Island Baptist Inventory Parser - Direct from raw text.
Format: "73 First Baptist Church, 1805--, Pawtucket . . . 74..."
"""
import re, sqlite3
from pathlib import Path

WPA_DIR = Path("E:/grid/data/wpa")
DB_PATH = Path("E:/grid/wpa.db")

def load_clean_text(filepath):
    text = filepath.read_text(encoding='utf-8', errors='replace')
    clean = re.sub(r'<script[^>]*>.*?</script>', '', text, flags=re.DOTALL|re.IGNORECASE)
    clean = re.sub(r'<style[^>]*>.*?</style>', '', clean, flags=re.DOTALL|re.IGNORECASE)
    clean = re.sub(r'<[^>]+>', ' ', clean)
    clean = re.sub(r'\s+', ' ', clean).strip()
    return clean

text = load_clean_text(WPA_DIR / "inventoryofchurc00unse_0.txt")

# Find inventory section
idx = text.find("73 First Baptist Church, 1805")
content = text[idx:]

# Split by ". ." - these are entry separators
# But ". ." appears as ".. ." and "...", so we need to handle that
segments = re.split(r'\.\s+\.\s*', content)

entries = []
for seg in segments:
    seg = seg.strip()
    if not seg:
        continue
    
    # Each segment: "73 First Baptist Church, 1805--, Pawtucket" or "74..."
    m = re.match(r'^(\d{1,3})\s+(.+)', seg)
    if not m:
        continue
    
    num = int(m.group(1))
    entry = m.group(2).strip()
    
    # Remove trailing page refs like "30", "31 30"
    entry = re.sub(r'\s+\d{1,3}\s*$', '', entry)
    
    # Skip if no church
    if 'Church' not in entry and 'Congregation' not in entry and 'Mission' not in entry:
        continue
    
    # Split on comma
    parts = [p.strip() for p in entry.split(',')]
    
    if not parts:
        continue
    
    name = parts[0]
    
    # Find dates - look for years or year patterns
    dates = None
    location = None
    
    for p in parts[1:]:
        p = p.strip()
        if re.search(r'\d{4}', p) or re.match(r'^[\d\-–\?]+$', p.replace(' ', '')):
            if dates is None:
                dates = p.replace('—', '-').replace('...', '-')
        elif p and len(p) > 2 and not re.match(r'^\d+$', p):
            location = p
    
    entries.append({
        'num': num,
        'name': name,
        'dates': dates,
        'location': location
    })

print(f"Parsed {len(entries)} entries")

# Deduplicate by name+dates
unique = {}
for e in entries:
    key = (e['name'].lower(), e['dates'] or '')
    if key not in unique:
        unique[key] = e

entries = list(unique.values())
print(f"Unique: {len(entries)}")

# Save
conn = sqlite3.connect(str(DB_PATH))
conn.execute("DROP TABLE IF EXISTS wpa_baptist_ri")
conn.execute("""CREATE TABLE wpa_baptist_ri (
    id INTEGER PRIMARY KEY,
    entry_num INTEGER,
    church_name TEXT,
    dates TEXT,
    location TEXT,
    founding_year INTEGER,
    closing_year INTEGER,
    state TEXT DEFAULT 'RI'
)""")

for e in entries:
    years = re.findall(r'(\d{4})', e['dates'] or '')
    founding = int(years[0]) if years else None
    closing = int(years[-1]) if len(years) > 1 else None
    
    conn.execute("INSERT INTO wpa_baptist_ri (entry_num, church_name, dates, location, founding_year, closing_year) VALUES (?,?,?,?,?,?)",
        (e['num'], e['name'], e['dates'] or '', e['location'] or '', founding, closing))
conn.commit()

print(f"Saved to wpa_baptist_ri")

c = conn.execute("SELECT COUNT(*) FROM wpa_baptist_ri WHERE founding_year IS NOT NULL")
print(f"With founding years: {c.fetchone()[0]}")

print("\n=== Sample ===")
for r in conn.execute("SELECT * FROM wpa_baptist_ri ORDER BY entry_num LIMIT 15").fetchall():
    print(f"  {r[1]}: {r[2][:40]} [{r[3]}] - {r[4]}")

conn.close()