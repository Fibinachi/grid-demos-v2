#!/usr/bin/env python3
"""
Final WPA extraction - process each cleaned file individually with proper parsing.
"""
import re, json, sqlite3
from pathlib import Path

WPA_DIR = Path("E:/grid/data/wpa")
DB_PATH = Path("E:/grid/wpa.db")

def parse_route_format(text):
    """Parse Arkansas format: Church Name (Rt. X--Town)."""
    entries = []
    # Find all patterns: word followed by (Rt. or R. F. D.)
    pattern = re.compile(r'([A-Z][a-zA-Z\s\-\'\.]{4,})\s*\((?:Rt\.|Rt|R\. F\. D\.)\s*([\d\-–]+[^)]*)\)')
    
    for match in pattern.finditer(text):
        name = match.group(1).strip('. ,;')
        route = match.group(2).strip()
        
        # Skip if looks like header/metadata
        if len(name) > 5 and not any(x in name.upper() for x in ['CHURCH NAME', 'CHURCH NAM', 'TOWN', 'COUNTY']):
            entries.append(name)
    
    return entries

def parse_street_format(text):
    """Parse Delaware format: Church Name at Street."""
    entries = []
    lines = text.split('\n')
    
    for line in lines:
        s = line.strip()
        # Must have both church term AND street address
        if re.search(r'(church|chapel|baptist|methodist)', s, re.IGNORECASE):
            if re.search(r'(street|ave\.?|avenue|road|p\. o\.)', s, re.IGNORECASE):
                # Extract first part as name
                parts = re.split(r'street|ave\.?|avenue|road', s, flags=re.IGNORECASE)
                if parts:
                    name = parts[0].strip()
                    if len(name) > 10:
                        entries.append(name)
    
    return entries

# Process all cleaned states
states = ['AR', 'DE', 'DC', 'ID', 'NM', 'ME', 'MN']
all_entries = []

for state in states:
    filepath = WPA_DIR / f"final_{state}.txt"
    if not filepath.exists():
        continue
    
    text = filepath.read_text(encoding='utf-8', errors='replace')
    
    if state == 'DE':
        entries = parse_street_format(text)
    else:
        entries = parse_route_format(text)
    
    all_entries.extend(entries)
    print(f"{state}: {len(entries)} entries")

# Deduplicate
seen = set()
clean = []
for e in all_entries:
    if e not in seen:
        seen.add(e)
        clean.append(e)

print(f"\nDeduplicated: {len(clean)} entries")

# Save
(WPA_DIR / "final_extracted.json").write_text(json.dumps(clean, indent=2), encoding='utf-8')
print(f"Saved to final_extracted.json")

# Import to DB
conn = sqlite3.connect(str(DB_PATH))
cur = conn.cursor()
cur.execute("CREATE TABLE IF NOT EXISTS wpa_churches (id INTEGER PRIMARY KEY, church_name TEXT)")
conn.execute("DELETE FROM wpa_churches")

for name in clean[:5000]:
    cur.execute("INSERT INTO wpa_churches (church_name) VALUES (?)", (name,))

conn.commit()
conn.close()
print(f"Imported to {DB_PATH}")