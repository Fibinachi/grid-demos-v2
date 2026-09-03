#!/usr/bin/env python3
"""
Extract church entries from cleaned WPA files - handles both formats.
"""
import re, json
from pathlib import Path

WPA_DIR = Path("E:/grid/data/wpa")

def clean_ocr(text):
    """Fix OCR issues in text."""
    text = text.replace('#', 't').replace('vv', 'w')
    text = text.replace('Strest', 'Street')
    text = text.replace('Pulaski', 'Pulaski')
    return text

def extract_route_entries(text, state):
    """Extract Arkansas-style entries: Name (Rt. X)."""
    entries = []
    for line in text.split('\n'):
        s = line.strip()
        m = re.search(r'([A-Z][A-Za-z].{5,})\s*\((?:Rt\.|R\. F\. D\.)\s*([\d\-–]+[^)]*)\)', s)
        if m:
            name = m.group(1).strip('. ,;')
            route = m.group(2).strip()
            entries.append({'state': state, 'church_name': name, 'route': route, 'format': 'route'})
    return entries

def extract_street_entries(text, state):
    """Extract Delaware-style entries: Name at Address."""
    entries = []
    for line in text.split('\n'):
        s = line.strip()
        # Must have church term AND address
        if 'church' in s.lower() or 'chapel' in s.lower():
            if re.search(r'(street|ave\.?|avenue|road|delaware|wilmington|dover)', s, re.IGNORECASE):
                entries.append({'state': state, 'church_name': s, 'format': 'street'})
    return entries

states = {
    "AR": WPA_DIR / "cleaned_AR.txt",
    "DE": WPA_DIR / "cleaned_DE.txt",
    "DC": WPA_DIR / "cleaned_DC.txt",
    "ID": WPA_DIR / "cleaned_ID.txt",
    "NM": WPA_DIR / "cleaned_NM.txt",
    "ME": WPA_DIR / "cleaned_ME.txt",
    "MN": WPA_DIR / "cleaned_MN.txt",
}

all_entries = []
for state, filepath in states.items():
    if not filepath.exists():
        continue
    
    text = clean_ocr(filepath.read_text(encoding='utf-8', errors='replace'))
    
    if state == "DE":
        entries = extract_street_entries(text, state)
    else:
        entries = extract_route_entries(text, state)
    
    all_entries.extend(entries)
    print(f"{state}: {len(entries)} entries")

print(f"\nTotal: {len(all_entries)} entries")

(WPA_DIR / "extracted_wpa.json").write_text(json.dumps(all_entries, indent=2), encoding='utf-8')
print("Saved to extracted_wpa.json")