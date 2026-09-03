#!/usr/bin/env python3
"""
Final clean WPA extraction - properly filters and cleans all entries.
"""
import re, json, sqlite3
from pathlib import Path

WPA_DIR = Path("E:/grid/data/wpa")
DB_PATH = Path("E:/grid/wpa.db")

def clean_name(name):
    """Clean church name thoroughly."""
    name = name.strip('. ,;-_()')
    
    # Fix OCR
    name = name.replace('#', 't').replace('vv', 'w')
    name = re.sub(r'\bthurch\b', 'Church', name, flags=re.IGNORECASE)
    name = re.sub(r'\bassembly of -God\b', 'Assembly of God', name, flags=re.IGNORECASE)
    
    # Remove newlines within names
    name = name.replace('\n', ' ')
    
    # Fix common OCR errors
    fixes = {
        'Assombly': 'Assembly', 'Chapol': 'Chapel', 'Glede': 'Grove',
        'tission': 'tission', 'Cole': 'Cole',
    }
    for wrong, right in fixes.items():
        name = name.replace(wrong, right)
    
    return name.strip()

def is_valid_entry(name):
    """Check if entry looks valid."""
    name = name.lower()
    
    # Must have church-related term
    if not any(x in name for x in ['church', 'chapel', 'assembly', 'gospel', 'union', 'mission', 'grove', 'hill', 'ridge', 'bethel', 'bethany', 'bethlehem']):
        return False
    
    # Skip obvious junk
    if any(x in name for x in ['god only', 'god god', 'rt. ']):
        return False
    
    if len(name) < 5:
        return False
    
    return True

def parse_state(filepath, state):
    """Parse state file for clean entries."""
    text = filepath.read_text(encoding='utf-8', errors='replace')
    
    entries = []
    for match in re.finditer(r'([A-Z][A-Za-z][A-Za-z\s\-\']{4,})\s*\((?:Rt\.|R\. F\. D\.)\s*([\d\-–]+[^)]*)\)', text):
        name = clean_name(match.group(1))
        if is_valid_entry(name):
            entries.append({'state': state, 'church_name': name})
    
    return entries

# Process all states
states = ['AR', 'DE', 'DC', 'ID', 'NM', 'ME', 'MN']
all_entries = []

for state in states:
    filepath = WPA_DIR / f"final_{state}.txt"
    if filepath.exists():
        entries = parse_state(filepath, state)
        all_entries.extend(entries)
        print(f"{state}: {len(entries)} valid entries")

# Dedup
seen = set()
clean = []
for e in all_entries:
    name = e['church_name']
    if name not in seen:
        seen.add(name)
        clean.append(e)

print(f"\nTotal unique valid entries: {len(clean)}")

# Save
(WPA_DIR / "wpa_final_clean.json").write_text(json.dumps(clean, indent=2), encoding='utf-8')

# Import to DB
conn = sqlite3.connect(str(DB_PATH))
cur = conn.cursor()
cur.execute("CREATE TABLE IF NOT EXISTS wpa_churches (id INTEGER PRIMARY KEY, state TEXT, church_name TEXT)")
conn.execute("DELETE FROM wpa_churches")

for e in clean:
    cur.execute("INSERT INTO wpa_churches (state, church_name) VALUES (?, ?)", (e['state'], e['church_name']))

conn.commit()
conn.close()
print("Saved to wpa_final_clean.json and imported to wpa.db")