#!/usr/bin/env python3
"""
Parse Arkansas WPA - split concatenated churches on single lines.
"""
import re, json, sqlite3
from pathlib import Path

WPA_DIR = Path("E:/grid/data/wpa")
DB_PATH = Path("E:/grid/wpa.db")

def clean_name(name):
    """Clean OCR errors in church name."""
    name = name.strip('. ,;-_()\n')
    name = name.replace('#', 't').replace('vv', 'w')
    name = re.sub(r'\bthurch\b', 'Church', name, flags=re.IGNORECASE)
    name = re.sub(r'\bCak\s+Grove\b', 'Cedar Grove', name)
    name = re.sub(r'\bChapol\b', 'Chapel', name)
    name = re.sub(r'\bTo eo\b', 'Toe', name)
    return name.strip()

def extract_all_churches(text):
    """Extract all individual churches, splitting concatenated lines."""
    entries = []
    
    for line in text.split('\n'):
        # Find all "ChurchName (Rt. X)" patterns in the line
        matches = re.findall(r'([A-Z][A-Za-z][A-Za-z\s\-\']{3,})\s*\((?:Rt\.|R\. F\. D\.)\s*([\d\-–]+[^)]*)\)', line)
        
        for name, route in matches:
            clean = clean_name(name)
            if len(clean) > 5:
                entries.append(clean)
    
    return entries

# Process Arkansas
text = (WPA_DIR / "final_AR.txt").read_text(encoding='utf-8', errors='replace')
entries = extract_all_churches(text)

print(f"Extracted {len(entries)} entries from Arkansas")

# Deduplicate preserving order
seen = set()
unique = []
for e in entries:
    if e not in seen:
        seen.add(e)
        unique.append(e)

print(f"Unique entries: {len(unique)}")

# Save
(WPA_DIR / "ar_churches.json").write_text(json.dumps(unique, indent=2), encoding='utf-8')

# Show sample
print("\n=== Sample ===")
for e in unique[:20]:
    print(f"  {e}")