#!/usr/bin/env python3
"""
Process all WPA states and extract clean entries.
"""
import re, json
from pathlib import Path

WPA_DIR = Path("E:/grid/data/wpa")

def fix_ocr_name(name):
    """Fix OCR in church names."""
    fixes = [
        (r'Rt\.\s*([0-9])', r'Rt. \1'),
        (r'R\.\s*F\.\s*D\.', 'R. F. D.'),
        (r'Strest', 'Street'),
        (r'Pulaski', 'Pulaski'),
        (r'PAPTIST', 'Baptist'),
        (r'Bapvist', 'Baptist'),
        (r'Bantist', 'Baptist'),
    ]
    for pat, repl in fixes:
        name = re.sub(pat, repl, name)
    return name.strip(' .;,"\'-')

def extract_churches(filepath, state):
    """Extract clean church entries from one file."""
    if not filepath.exists():
        return []
    
    text = filepath.read_text(encoding='utf-8', errors='replace')
    text = text.replace('#', 't').replace('vv', 'w')
    
    lines = text.split('\n')
    entries = []
    current_denom = ""
    
    church_pattern = re.compile(r'([A-Z][a-zA-Z\'\-\s]+)\s*\((?:Rt\.|Rt|R\. F\. D\.)\s*([\d\-–]+[^)]*)\)')
    
    for line in lines:
        s = line.strip()
        if not s:
            continue
        
        # Denomination header
        if re.match(r'^[A-Z]{4,}', s) and len(s) < 40:
            if any(x in s.upper() for x in ['BAPTIST', 'METHODIST', 'CHRISTIAN', 'GOSPEL', 'ASSEMBLY', 'CHURCH OF CHRIST', 'DISCIPLES', 'PRESBYTERIAN', 'EPISCOPAL', 'MENNONITE', 'LUTHERAN']):
                current_denom = s.replace('CONTINUED', '').strip()
                continue
        
        # Extract churches
        churches = church_pattern.findall(s)
        for name, route in churches:
            clean_name = fix_ocr_name(name)
            if len(clean_name) > 2:
                entries.append({
                    'state': state,
                    'denomination': current_denom,
                    'church_name': clean_name,
                    'route': route.strip()
                })
    
    return entries

states = {
    "AR": WPA_DIR / "final_AR.txt",
    "DE": WPA_DIR / "final_DE.txt", 
    "DC": WPA_DIR / "final_DC.txt",
    "ID": WPA_DIR / "final_ID.txt",
    "NM": WPA_DIR / "final_NM.txt",
    "ME": WPA_DIR / "final_ME.txt",
    "MN": WPA_DIR / "final_MN.txt",
}

all_entries = []
for state, filepath in states.items():
    entries = extract_churches(filepath, state)
    all_entries.extend(entries)
    print(f"{state}: {len(entries)} entries")

print(f"\nTotal: {len(all_entries)} entries")

# Save combined
(WPA_DIR / "all_wpa_entries.json").write_text(json.dumps(all_entries, indent=2), encoding='utf-8')
print("Saved to all_wpa_entries.json")