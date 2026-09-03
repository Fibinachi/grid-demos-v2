#!/usr/bin/env python3
"""
Process all 96 WPA volumes - proper OCR cleanup and extraction.
"""
import re, json, sqlite3
from pathlib import Path

WPA_DIR = Path("E:/grid/data/wpa")

# Map cleaned files to the original full files
FILE_MAPPING = {
    "AR": ("directoryofchurc00hist_0.txt", "AR"),
    "DE": ("directoryofchurc00dela.txt", "DE"),
    "DC": ("directoryofchurc00dist.txt", "DC"),
    "ID": ("directoryofchurc00idah.txt", "ID"),
    "NM": ("directoryofchurc00newm.txt", "NM"),
    "ME": ("directoryofchurc00main.txt", "ME"),
    "MN": ("directoryofchurc00mich.txt", "MN"),
}

def fix_ocr(text):
    """Fix OCR errors."""
    text = text.replace('#', 't')
    text = text.replace('vv', 'w')
    return text

def extract_churches(text, state):
    """Extract churches matching the route format."""
    entries = []
    for line in text.split('\n'):
        s = line.strip()
        # Arkansas style: "Name (Rt. X)"
        m = re.search(r'([A-Z][A-Za-z][A-Za-z\s\-\'\.]{4,})\s*\((?:Rt\.|Rt|R\. F\. D\.)\s*[\d\-–]+[^)]*\)', s)
        if m:
            name = m.group(1).strip('. ,;')
            if len(name) > 5:
                entries.append({'state': state, 'church_name': name})
    return entries

# Process each state
all_entries = []
for state, (filename, st) in FILE_MAPPING.items():
    filepath = WPA_DIR / filename
    if not filepath.exists():
        print(f"{state}: File not found: {filename}")
        continue
    
    text = filepath.read_text(encoding='utf-8', errors='replace')
    text = fix_ocr(text)
    
    entries = extract_churches(text, st)
    all_entries.extend(entries)
    print(f"{state}: {len(entries)} entries from {len(text):,} chars")

print(f"\nTotal: {len(all_entries)} entries")

# Save
(WPA_DIR / "wpa_all_states.json").write_text(json.dumps(all_entries, indent=2), encoding='utf-8')
print("Saved to wpa_all_states.json")