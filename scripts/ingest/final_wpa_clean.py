#!/usr/bin/env python3
"""
Final clean WPA parser - extracts only actual church entries.
"""
import re, json
from pathlib import Path

WPA_DIR = Path("E:/grid/data/wpa")

def is_church_entry(text):
    """Check if text looks like a real church entry."""
    if not text or len(text) < 10:
        return False
    
    # Must have church-related term
    if not re.search(r'(church|chapel|mission|temple|assembly|congregation)', text, re.IGNORECASE):
        return False
    
    # Exclude obvious headers/metadata
    exclude = ['Directory of churches', 'This Directory', 'Table of Contents', 
               'Historical Records Survey', 'Work Projects', 'Prepared by',
               'Digitized by', 'Internet Archive', 'PREFACE', 'NOTE', 
               'EXPLANATORY', 'DENOMINATION', 'NUMERICAL CHART']
    for exc in exclude:
        if exc.lower() in text.lower():
            return False
    
    return True

def parse_arkansas(filepath):
    """Parse Arkansas route format."""
    entries = []
    text = filepath.read_text(encoding='utf-8', errors='replace')
    
    for line in text.split('\n'):
        s = line.strip()
        # Pattern: "Name (Rt. X--Town)" or similar
        m = re.search(r'([A-Z][A-Za-z][A-Za-z\s\-\'\.]{3,})\s*\((?:Rt\.|Rt|R\. F\. D\.)\s*[\d\-–]+[^)]*\)', s)
        if m:
            name = m.group(1).strip('. ,;')
            if is_church_entry(name):
                entries.append({'state': 'AR', 'church_name': name})
    
    return entries

def parse_delaware(filepath):
    """Parse Delaware with street addresses."""
    entries = []
    text = filepath.read_text(encoding='utf-8', errors='replace')
    
    for line in text.split('\n'):
        s = line.strip()
        if is_church_entry(s):
            # Clean up the line
            s = re.sub(r'^[A-Z]{2,}\s*', '', s)  # Remove denomination header
            s = re.sub(r'\s{2,}.*$', '', s)  # Remove extra
            entries.append({'state': 'DE', 'church_name': s})
    
    return entries

def parse_generic(filepath, state):
    """Parse other states."""
    entries = []
    text = filepath.read_text(encoding='utf-8', errors='replace')
    
    for line in text.split('\n'):
        s = line.strip()
        # Look for lines with route/address AND church terms
        if is_church_entry(s) and re.search(r'(Rt\.|Street|Avenue|R\. F\.|P\. O\.)', s):
            entries.append({'state': state, 'church_name': s})
    
    return entries

# Process all states
results = {
    "AR": parse_arkansas(WPA_DIR / "final_AR.txt"),
    "DE": parse_delaware(WPA_DIR / "final_DE.txt"),
    "DC": parse_generic(WPA_DIR / "final_DC.txt", "DC"),
    "ID": parse_generic(WPA_DIR / "final_ID.txt", "ID"),
    "NM": parse_generic(WPA_DIR / "final_NM.txt", "NM"),
    "ME": parse_generic(WPA_DIR / "final_ME.txt", "ME"),
    "MN": parse_generic(WPA_DIR / "final_MN.txt", "MN"),
}

for state, entries in results.items():
    print(f"{state}: {len(entries)} entries")

all_entries = []
for entries in results.values():
    all_entries.extend(entries)

print(f"\nTotal: {len(all_entries)} clean entries")
(WPA_DIR / "clean_wpa_entries.json").write_text(json.dumps(all_entries, indent=2), encoding='utf-8')
print("Saved to clean_wpa_entries.json")