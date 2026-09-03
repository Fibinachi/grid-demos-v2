#!/usr/bin/env python3
"""
Comprehensive WPA parser - extracts clean entries from all cleaned state files.
"""
import re, json, sqlite3
from pathlib import Path

WPA_DIR = Path("E:/grid/data/wpa")
DB_PATH = Path("E:/grid/wpa.db")

def clean_name(name):
    """Clean church name."""
    # Remove header artifacts
    name = re.sub(r'^CHURCH\s*N[ZA]*ME\s*', '', name, flags=re.IGNORECASE)
    name = re.sub(r'^[A-Z]{2,}\s*', '', name)
    name = re.sub(r'\s{3,}.+$', '', name)
    name = re.sub(r'[|`\\\'<>]{2,}', '', name)
    return name.strip('. ,;-')

def parse_state(filepath, state):
    """Parse one state file."""
    text = filepath.read_text(encoding='utf-8', errors='replace')
    entries = []
    
    for line in text.split('\n'):
        s = line.strip()
        
        # Method 1: Route format "Name (Rt. X)"
        m = re.search(r'([A-Z][A-Za-z].{3,})\s*\((?:Rt\.|R\. F\. D\.)\s*[\d\-–]+[^)]*\)', s)
        if m:
            name = clean_name(m.group(1))
            if len(name) > 4:
                entries.append({'state': state, 'church_name': name})
            continue
        
        # Method 2: Street address format
        if re.search(r'(street|ave\.?|avenue|road|p\. o\.)', s, re.IGNORECASE):
            if re.search(r'(church|chapel|baptist|methodist|assembly)', s, re.IGNORECASE):
                name = clean_name(s)
                if len(name) > 4 and 'directory' not in name.lower():
                    entries.append({'state': state, 'church_name': name})
    
    return entries

# Process all cleaned states
states = ['AR', 'DE', 'DC', 'ID', 'NM', 'ME', 'MN']
all_entries = []

for state in states:
    filepath = WPA_DIR / f"final_{state}.txt"
    if filepath.exists():
        entries = parse_state(filepath, state)
        all_entries.extend(entries)
        print(f"{state}: {len(entries)} entries")

# Dedup
seen = set()
clean = []
for e in all_entries:
    name = e['church_name']
    if name and name not in seen:
        seen.add(name)
        clean.append(e)

print(f"\nDeduplicated: {len(clean)} entries")

# Save
output = WPA_DIR / "final_wpa_entries.json"
output.write_text(json.dumps(clean, indent=2), encoding='utf-8')
print(f"Saved to {output}")

# Import to DB
conn = sqlite3.connect(str(DB_PATH))
cur = conn.cursor()
cur.execute("""CREATE TABLE IF NOT EXISTS wpa_churches (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    state TEXT,
    church_name TEXT,
    source TEXT
)""")

conn.execute("DELETE FROM wpa_churches")
for e in clean[:5000]:
    cur.execute("INSERT INTO wpa_churches (state, church_name, source) VALUES (?, ?, ?)",
               (e['state'], e['church_name'], 'WPA'))

conn.commit()
conn.close()
print(f"Imported to {DB_PATH}")