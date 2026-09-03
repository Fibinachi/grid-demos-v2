#!/usr/bin/env python3
"""
Final WPA extraction - properly handles fragmented OCR lines.
"""
import re, json, sqlite3
from pathlib import Path

WPA_DIR = Path("E:/grid/data/wpa")
DB_PATH = Path("E:/grid/wpa.db")

def join_fragments(text):
    """Join OCR fragments where each word is on separate lines."""
    lines = text.split('\n')
    joined = []
    buf = []
    
    for line in lines:
        s = line.strip()
        if not s:
            if buf:
                joined.append(' '.join(buf))
                buf = []
        else:
            buf.append(s)
    
    if buf:
        joined.append(' '.join(buf))
    
    return '\n'.join(joined)

def fix_ocr(text):
    """Fix common OCR errors."""
    text = text.replace('#', 't')
    text = text.replace('vv', 'w')
    text = text.replace('Strest', 'Street')
    text = text.replace('Pulaski', 'Pulaski')
    text = re.sub(r'\bthurch\b', 'Church', text, flags=re.IGNORECASE)
    text = re.sub(r'\bMmethodist\b', 'Methodist', text, flags=re.IGNORECASE)
    return text

def extract_churches(text, state):
    """Extract church entries from cleaned text."""
    entries = []
    
    # Method 1: Route format "Name (Rt. X--Town)"
    route_pattern = re.compile(r'([A-Z][A-Za-z][A-Za-z\s\-\']{3,})\s*\((?:Rt\.|Rt|R\. F\. D\.)\s*([\d\-–]+[^)]*)\)')
    for m in route_pattern.finditer(text):
        name = m.group(1).strip('. ,;-')
        if len(name) > 5:
            entries.append({'state': state, 'church_name': name})
    
    return entries

# Process all cleaned states
states = ['AR', 'DE', 'DC', 'ID', 'NM', 'ME', 'MN']
all_entries = {}

for state in states:
    filepath = WPA_DIR / f"final_{state}.txt"
    if not filepath.exists():
        continue
    
    text = filepath.read_text(encoding='utf-8', errors='replace')
    text = join_fragments(text)
    text = fix_ocr(text)
    
    entries = extract_churches(text, state)
    all_entries[state] = entries
    print(f"{state}: {len(entries)} route entries from {len(text):,} chars")

# Combine all
total = []
for entries in all_entries.values():
    total.extend(entries)

print(f"\nTotal route entries: {len(total)}")

# Save
(WPA_DIR / "wpa_clean.json").write_text(json.dumps(total, indent=2), encoding='utf-8')

# Import to DB
conn = sqlite3.connect(str(DB_PATH))
cur = conn.cursor()
cur.execute("CREATE TABLE IF NOT EXISTS wpa_churches (id INTEGER PRIMARY KEY, state TEXT, church_name TEXT)")
conn.execute("DELETE FROM wpa_churches")

for e in total:
    cur.execute("INSERT INTO wpa_churches (state, church_name) VALUES (?, ?)", (e['state'], e['church_name']))

conn.commit()
conn.close()
print("Imported to wpa.db")