#!/usr/bin/env python3
"""
Manual entry-by-entry correction for WPA OCR.
Process in small batches for review/correction.
"""
import json, re
from pathlib import Path

WPA_DIR = Path("E:/grid/data/wpa")

# Load entries
entries = json.loads((WPA_DIR / "wpa_cleaned_final.json").read_text())

def clean_name(name):
    """Apply comprehensive OCR fixes to a single name."""
    # Remove header artifacts
    name = re.sub(r'^CHURCH\s*N[ZA]*ME\s*', '', name, flags=re.IGNORECASE)
    name = re.sub(r'\s{3,}.*$', '', name)
    
    # Fix OCR
    name = name.replace('#', 't').replace('vv', 'w')
    name = re.sub(r'\bthurch\b', 'Church', name, flags=re.IGNORECASE)
    name = re.sub(r'\bAssembly\s+of\s+\-God\b', 'Assembly of God', name)
    name = re.sub(r'\bAssembly\s+ef\s+God\b', 'Assembly of God', name)
    name = re.sub(r'\bCedar\s+Glede\b', 'Cedar Grove', name)
    name = re.sub(r'\bCppelo\b', 'Cedar Plantation', name)
    name = re.sub(r'\bChapol\b', 'Chapel', name)
    name = re.sub(r'\b(N|e)W+Hope\b', 'New Hope', name, flags=re.IGNORECASE)
    name = re.sub(r'\bH(a)?rmen?y\b', 'Harmony', name, flags=re.IGNORECASE)
    name = re.sub(r'\bD(a)?mas(c)?us\b', 'Damascus', name, flags=re.IGNORECASE)
    
    return name.strip('. ,;-_')

# Apply corrections
corrected = 0
for e in entries:
    original = e['church_name']
    cleaned = clean_name(original)
    if cleaned != original and len(cleaned) > 5:
        e['church_name'] = cleaned
        corrected += 1

print(f"Corrected {corrected} entries")

# Save
(WPA_DIR / "wpa_manually_corrected.json").write_text(json.dumps(entries, indent=2), encoding='utf-8')
print("Saved to wpa_manually_corrected.json")