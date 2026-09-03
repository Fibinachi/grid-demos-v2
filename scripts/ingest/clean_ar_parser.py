#!/usr/bin/env python3
"""
Clean Arkansas WPA parser - extracts church entries from the actual format.
"""
import re, json
from pathlib import Path

WPA_DIR = Path("E:/grid/data/wpa")

def fix_ocr_name(name):
    """Fix OCR in church names."""
    fixes = [
        (r'Rt\.\s*([0-9])', r'Rt. \1'),
        (r'R\.\s*F\.\s*D\.', 'R. F. D.'),
        (r'\bst\.\s*\.', 'St.'),
        (r'\bst\s*\.', 'St.'),
        (r'Strest', 'Street'),
        (r'Pulaski', 'Pulaski'),
    ]
    for pat, repl in fixes:
        name = re.sub(pat, repl, name)
    return name.strip(' .;,"\'')

def extract_churches(filepath):
    """Extract clean church entries."""
    text = filepath.read_text(encoding='utf-8', errors='replace')
    
    # Fix common OCR
    text = text.replace('#', 't').replace('vv', 'w')
    
    lines = text.split('\n')
    entries = []
    current_denom = ""
    
    # Pattern for church entries: "Name (Rt. X)" or "Name (R. F. D.)"
    church_pattern = re.compile(r'([A-Z][a-zA-Z\'\-\s]+)\s*\((?:Rt\.|Rt|R\. F\. D\.)\s*([\d\-–]+[^)]*)\)')
    
    for line in lines:
        s = line.strip()
        if not s:
            continue
        
        # Denomination header
        if re.match(r'^[A-Z]{4,}', s) and len(s) < 35 and 'ASSOCIATION' not in s.upper():
            if any(x in s.upper() for x in ['BAPTIST', 'METHODIST', 'CHRISTIAN', 'GOSPEL', 'ASSEMBLY', 'CHURCH OF CHRIST', 'DISCIPLES']):
                current_denom = s.replace('CONTINUED', '').replace('PAPTIST', 'Baptist').strip()
                continue
        
        # Association/section header
        if 'ASSOCIATION' in s.upper():
            continue
        
        # Extract churches from line
        churches = church_pattern.findall(s)
        for name, route in churches:
            clean_name = fix_ocr_name(name)
            if len(clean_name) > 2 and 'CHURCH NAME' not in clean_name.upper():
                entries.append({
                    'denomination': current_denom,
                    'church_name': clean_name,
                    'route': route.strip()
                })
    
    return entries

# Process Arkansas
entries = extract_churches(WPA_DIR / "final_AR.txt")
print(f"Extracted {len(entries)} clean entries from Arkansas")

# Show distribution
from collections import Counter
denom_count = Counter(e['denomination'] for e in entries)
print("\n=== Denomination distribution ===")
for denom, count in denom_count.most_common(10):
    print(f"  {denom[:30]:30} {count}")

# Save
output = WPA_DIR / "clean_ar_entries.json"
output.write_text(json.dumps(entries, indent=2), encoding='utf-8')
print(f"\nSaved to {output}")