#!/usr/bin/env python3
"""
Final WPA - extract all church entries from all formats.
"""
import re, json, sqlite3
from pathlib import Path

WPA_DIR = Path("E:/grid/data/wpa")
DB_PATH = Path("E:/grid/wpa.db")

def clean_name(name):
    """Clean OCR errors."""
    name = re.sub(r'[|`\\]{2,}', '', name)
    name = name.replace('#', 't').replace('vv', 'w')
    name = re.sub(r'\bthurch\b', 'Church', name, flags=re.IGNORECASE)
    name = re.sub(r'\bCak\s+Grove\b', 'Cedar Grove', name)
    name = re.sub(r'\bChapol\b', 'Chapel', name)
    return name.strip('. ,;-\n')

def parse_route_format(text):
    """Arkansas format: Name (Rt. X)."""
    entries = []
    for line in text.split('\n'):
        for m in re.finditer(r'([A-Z][A-Za-z][A-Za-z\s\-\']{3,})\s*\((?:Rt\.|R\. F\. D\.)\s*([\d\-–]+[^)]*)\)', line):
            name = clean_name(m.group(1))
            if len(name) > 5:
                entries.append(name)
    return entries

def parse_street_format(text):
    """MN/ME/NM format: Name Street Address."""
    entries = []
    for line in text.split('\n'):
        # Look for lines with church terms AND street addresses
        if not re.search(r'(church|chapel|baptist|methodist|assembly|adventist)', line, re.IGNORECASE):
            continue
        
        # Extract first part before street
        m = re.search(r'^([A-Z][A-Za-z].{5,}?)\s+(?:street|ave\.?|avenue|p\. o\.)', line, re.IGNORECASE)
        if m:
            name = clean_name(m.group(1))
            if len(name) > 5 and len(name) < 100:
                entries.append(name)
    return entries

# Process all states
states = {
    'AR': (WPA_DIR / "final_AR.txt", parse_route_format),
    'DE': (WPA_DIR / "final_DE.txt", parse_street_format),
    'DC': (WPA_DIR / "final_DC.txt", parse_street_format),
    'ID': (WPA_DIR / "final_ID.txt", parse_street_format),
    'NM': (WPA_DIR / "final_NM.txt", parse_street_format),
    'ME': (WPA_DIR / "final_ME.txt", parse_street_format),
    'MN': (WPA_DIR / "final_MN.txt", parse_street_format),
}

all_entries = []
for state, (filepath, parser) in states.items():
    if filepath.exists():
        text = filepath.read_text(encoding='utf-8', errors='replace')
        entries = parser(text)
        # Dedup
        entries = list(dict.fromkeys(entries))
        all_entries.extend([{'state': state, 'church_name': e} for e in entries])
        print(f"{state}: {len(entries)} entries")

print(f"\nTotal: {len(all_entries)} entries")

# Save
(WPA_DIR / "wpa_all_final.json").write_text(json.dumps(all_entries, indent=2), encoding='utf-8')

# Import
conn = sqlite3.connect(str(DB_PATH))
cur = conn.cursor()
cur.execute("CREATE TABLE IF NOT EXISTS wpa_churches (id INTEGER PRIMARY KEY, state TEXT, church_name TEXT)")
conn.execute("DELETE FROM wpa_churches")

for e in all_entries[:5000]:
    cur.execute("INSERT INTO wpa_churches (state, church_name) VALUES (?, ?)", (e['state'], e['church_name']))

conn.commit()
conn.close()
print("Saved and imported to wpa.db")