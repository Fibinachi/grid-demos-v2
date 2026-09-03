#!/usr/bin/env python3
"""
Final WPA processing - clean all states.
"""
import re, json, sqlite3
from pathlib import Path

WPA_DIR = Path("E:/grid/data/wpa")
DB_PATH = Path("E:/grid/wpa.db")

def fix_ocr(name):
    """Fix OCR errors in name."""
    name = name.replace('#', 't').replace('vv', 'w')
    name = re.sub(r'\bthurch\b', 'Church', name, flags=re.IGNORECASE)
    name = re.sub(r'\bMmethodist\b', 'Methodist', name)
    name = re.sub(r'\bPleasant\s+Eome\b', 'Pleasant Home', name)
    name = re.sub(r'\bCak\s+Grove\b', 'Cedar Grove', name)
    return name.strip('. ,;-')

def parse_state(filepath, state):
    """Parse one state file returning clean church names."""
    text = filepath.read_text(encoding='utf-8', errors='replace')
    
    entries = []
    # Route format
    for match in re.finditer(r'([A-Z][A-Za-z][A-Za-z\s\-\']{4,})\s*\((?:Rt\.|R\. F\. D\.)\s*([\d\-–]+[^)]*)\)', text):
        name = fix_ocr(match.group(1))
        if len(name) > 5:
            entries.append({'state': state, 'church_name': name})
    
    return entries

states = ['AR', 'DE', 'DC', 'ID', 'NM', 'ME', 'MN']
all_entries = []

for state in states:
    filepath = WPA_DIR / f"final_{state}.txt"
    if filepath.exists():
        entries = parse_state(filepath, state)
        all_entries.extend(entries)
        print(f"{state}: {len(entries)} entries")

# Dedup (by name, keeping first occurrence)
seen = {}
for e in all_entries:
    name = e['church_name']
    if name not in seen:
        seen[name] = e

clean = list(seen.values())
print(f"\nTotal unique entries: {len(clean)}")

# Save
(WPA_DIR / "wpa_deduped.json").write_text(json.dumps(clean, indent=2), encoding='utf-8')

# Import
conn = sqlite3.connect(str(DB_PATH))
cur = conn.cursor()
cur.execute("CREATE TABLE IF NOT EXISTS wpa_churches (id INTEGER PRIMARY KEY, state TEXT, church_name TEXT)")
conn.execute("DELETE FROM wpa_churches")

for e in clean[:5000]:
    cur.execute("INSERT INTO wpa_churches (state, church_name) VALUES (?, ?)", (e['state'], e['church_name']))

conn.commit()
conn.close()
print("Imported to wpa.db")