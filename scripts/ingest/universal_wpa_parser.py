#!/usr/bin/env python3
"""
Universal WPA parser - handles different state formats.
"""
import re, json
from pathlib import Path

WPA_DIR = Path("E:/grid/data/wpa")

def clean_text(text):
    """Basic OCR cleanup."""
    return text.replace('#', 't').replace('vv', 'w')

def parse_arkansas(text):
    """Parse Arkansas format: Name (Rt. X)."""
    entries = []
    lines = text.split('\n')
    
    for line in lines:
        s = line.strip()
        if not s:
            continue
        
        # Pattern: "Church Name (Rt. X)" or "(R. F. D.--Town)"
        m = re.search(r'([A-Z][A-Za-z][A-Za-z\s\-\'\.]+)\s*\((?:Rt\.|Rt|R\. F\. D\.)\s*[\d\-–]+[^)]*\)', s)
        if m:
            name = m.group(1).strip('. ,;')
            if len(name) > 3:
                entries.append({'denomination': '', 'church_name': name, 'city': '', 'county': ''})
    return entries

def parse_delaware(text):
    """Parse Delaware format: churches with street addresses."""
    entries = []
    lines = text.split('\n')
    
    for line in lines:
        s = line.strip()
        if not s or len(s) < 15:
            continue
        
        if re.search(r'(Church|Baptist|Methodist|Assembly|Gospel|Congregation)', s, re.IGNORECASE):
            entries.append({'denomination': '', 'church_name': s, 'city': '', 'county': ''})
    return entries

def parse_dc_id_nm(text):
    """Parse simple format states."""
    entries = []
    lines = text.split('\n')
    
    for line in lines:
        s = line.strip()
        if re.search(r'(Church|Chapel|Baptist|Presbyterian|Methodist|Congregation)', s, re.IGNORECASE):
            entries.append({'denomination': '', 'church_name': s, 'city': '', 'county': ''})
    return entries

states = {
    "AR": (WPA_DIR / "final_AR.txt", parse_arkansas),
    "DE": (WPA_DIR / "final_DE.txt", parse_delaware),
    "DC": (WPA_DIR / "final_DC.txt", parse_dc_id_nm),
    "ID": (WPA_DIR / "final_ID.txt", parse_dc_id_nm),
    "NM": (WPA_DIR / "final_NM.txt", parse_dc_id_nm),
    "ME": (WPA_DIR / "final_ME.txt", parse_dc_id_nm),
    "MN": (WPA_DIR / "final_MN.txt", parse_dc_id_nm),
}

all_entries = []
for state, (filepath, parser) in states.items():
    if filepath.exists():
        text = clean_text(filepath.read_text(encoding='utf-8', errors='replace'))
        entries = parser(text)
        for e in entries:
            e['state'] = state
        all_entries.extend(entries)
        print(f"{state}: {len(entries)} entries")

print(f"\nTotal: {len(all_entries)} entries")

(WPA_DIR / "all_wpa_final.json").write_text(json.dumps(all_entries, indent=2), encoding='utf-8')
print("Saved to all_wpa_final.json")