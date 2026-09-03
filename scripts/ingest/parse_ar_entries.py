#!/usr/bin/env python3
"""
Extract and clean Arkansas WPA church entries.
"""
import re, json
from pathlib import Path

WPA_DIR = Path("E:/grid/data/wpa")

def parse_entry_line(line):
    """Parse one line that may contain multiple church entries."""
    # Fix OCR issues
    line = line.replace('#', 't').replace('vv', 'w')
    line = re.sub(r'\bStrest\b', 'Street', line)
    line = re.sub(r'\bPulaski\b', 'Pulaski', line)
    
    # Split on common separators
    parts = re.split(r'[;:,]+', line)
    entries = []
    
    for part in parts:
        part = part.strip()
        if not part:
            continue
        
        # Extract church name and location
        # Format: "Church Name (Rt. X)" or "Name, Address, Town"
        m = re.match(r'^([A-Z][a-zA-Z\s]+)(?:\s*\((?:Rt\.|R\. F\. D\.)\s*[\d\-–]+[^)]*\))?', part)
        if m:
            name = m.group(1).strip()
            if len(name) > 2:
                entries.append(name)
    
    return entries

def extract_all_entries(filepath):
    """Extract all entries from Arkansas file."""
    text = filepath.read_text(encoding='utf-8', errors='replace')
    lines = text.split('\n')
    
    all_entries = []
    current_denom = ""
    current_section = ""
    
    for line in lines:
        s = line.strip()
        
        # Denomination header
        if re.match(r'^[A-Z]{4,}[A-Z\s]*$', s) and len(s) < 30:
            current_denom = s
            continue
        
        # Section header
        if re.search(r'(ASSOCIATION|COUNTY)', s, re.IGNORECASE):
            current_section = s
            continue
        
        # Entry line
        if re.search(r'(Church|Chapel|Mission|Baptist|Assembly|Congregation)', s, re.IGNORECASE):
            parsed = parse_entry_line(s)
            for entry in parsed:
                all_entries.append({
                    'denomination': current_denom,
                    'section': current_section,
                    'church_name': entry
                })
    
    return all_entries

entries = extract_all_entries(WPA_DIR / "final_AR.txt")
print(f"Extracted {len(entries)} entries from Arkansas")

# Save as JSON
output = WPA_DIR / "clean_entries_AR.json"
output.write_text(json.dumps(entries, indent=2), encoding='utf-8')
print(f"Saved to {output}")

# Show samples
print("\n=== Sample entries ===")
for e in entries[:20]:
    print(f"  [{e['denomination'][:20]:20}] {e['church_name']}")