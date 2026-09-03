#!/usr/bin/env python3
"""
Final WPA extraction - all states processed, cleaned, and imported.
"""
import re, json, sqlite3
from pathlib import Path

WPA_DIR = Path("E:/grid/data/wpa")
DB_PATH = Path("E:/grid/wpa.db")

def clean_name(name):
    """Clean church name."""
    name = name.strip('. ,;-_')
    name = name.replace('#', 't').replace('vv', 'w')
    name = re.sub(r'\bthurch\b', 'Church', name, flags=re.IGNORECASE)
    name = re.sub(r'\bCak\s+Grove\b', 'Cedar Grove', name)
    name = re.sub(r'\bChapol\b', 'Chapel', name)
    return name.strip()

def parse_state(text):
    """Extract all churches from text, splitting concatenated lines."""
    entries = []
    
    for line in text.split('\n'):
        matches = re.findall(r'([A-Z][A-Za-z][A-Za-z\s\-\']{3,})\s*\((?:Rt\.|R\. F\. D\.)\s*([\d\-–]+[^)]*)\)', line)
        for name, route in matches:
            clean = clean_name(name)
            if len(clean) > 5:
                entries.append(clean)
    
    return entries

# Process all states
states = ['AR', 'DE', 'DC', 'ID', 'NM', 'ME', 'MN']
all_entries = {}

for state in states:
    filepath = WPA_DIR / f"final_{state}.txt"
    if filepath.exists():
        text = filepath.read_text(encoding='utf-8', errors='replace')
        entries = parse_state(text)
        all_entries[state] = list(dict.fromkeys(entries))  # Dedup preserving order
        print(f"{state}: {len(all_entries[state])} unique entries")

# Combine
all_clean = []
for state, entries in all_entries.items():
    for name in entries:
        all_clean.append({'state': state, 'church_name': name})

print(f"\nTotal: {len(all_clean)} entries")

# Save
(WPA_DIR / "all_wpa_clean.json").write_text(json.dumps(all_clean, indent=2), encoding='utf-8')

# Import to DB
conn = sqlite3.connect(str(DB_PATH))
cur = conn.cursor()
cur.execute("CREATE TABLE IF NOT EXISTS wpa_churches (id INTEGER PRIMARY KEY, state TEXT, church_name TEXT)")
conn.execute("DELETE FROM wpa_churches")

for e in all_clean:
    cur.execute("INSERT INTO wpa_churches (state, church_name) VALUES (?, ?)", (e['state'], e['church_name']))

conn.commit()
conn.close()
print("Saved to all_wpa_clean.json and imported to wpa.db")