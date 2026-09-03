#!/usr/bin/env python3
"""
Manual OCR cleanup - process entries in chunks and apply fixes.
"""
import re, json, sqlite3
from pathlib import Path
from collections import Counter

WPA_DIR = Path("E:/grid/data/wpa")
DB_PATH = Path("E:/grid/wpa.db")

# Load current entries
entries = json.loads((WPA_DIR / "wpa_all_final.json").read_text())

# Analyze OCR errors
names = [e['church_name'] for e in entries if e.get('state') == 'AR']
print(f"Analyzing {len(names)} Arkansas entries...")

# Find common OCR error patterns
errors = []
for name in names:
    # Check for known patterns
    fixes_needed = []
    if re.search(r'\bAssombly\b', name):
        fixes_needed.append('Assombly')
    if re.search(r'\bCedar\s+Glede\b', name):
        fixes_needed.append('Cedar Glede')
    if re.search(r'\bCppelo\b', name):
        fixes_needed.append('Cppelo')
    if re.search(r'\bCole\s+tission\b', name):
        fixes_needed.append('Cole tission')
    if re.search(r'\bAssembly\s+ef\s+God\b', name):
        fixes_needed.append('Assembly ef God')
    
    if fixes_needed:
        errors.append((name, fixes_needed))

print(f"\nEntries needing OCR fixes: {len(errors)}")
for name, fixes in errors[:20]:
    print(f"  {name[:60]} - fixes: {fixes}")

# Apply fixes
ocr_fixes = [
    (r'\bAssombly\b', 'Assembly'),
    (r'\bCedar\s+Glede\b', 'Cedar Grove'),
    (r'\bCppelo\b', 'Cedar Plantation'),
    (r'\bCole\s+tission\b', 'Cole Mission'),
    (r'\bAssembly\s+ef\s+God\b', 'Assembly of God'),
    (r'\bMmethodist\b', 'Methodist'),
    (r'\bPleasant\s+Eome\b', 'Pleasant Home'),
    (r'\bChapol\b', 'Chapel'),
]

fixed = 0
for e in entries:
    original = e['church_name']
    for pat, repl in ocr_fixes:
        if re.search(pat, original):
            e['church_name'] = re.sub(pat, repl, original)
            fixed += 1

print(f"\nFixed {fixed} OCR errors")