#!/usr/bin/env python3
"""
Comprehensive OCR cleanup for WPA directories using laguna-m.1.
Processes each state individually and extracts clean entries.
"""
import re, json
from pathlib import Path

WPA_DIR = Path("E:/grid/data/wpa")

def join_fragments(text):
    """Join fragmented OCR where each word is on separate line."""
    lines = text.split('\n')
    joined = []
    buf = []
    
    for line in lines:
        s = line.strip()
        if not s:
            if buf:
                joined.append(' '.join(buf))
                buf = []
            continue
        # If line starts with capital and contains continuation words, join
        if re.match(r'^[A-Z]', s) or (buf and len(s) < 30):
            buf.append(s)
        else:
            if buf:
                joined.append(' '.join(buf))
            buf = [s]
    
    if buf:
        joined.append(' '.join(buf))
    
    return '\n'.join(joined)

def fix_ocr(text):
    """Fix OCR character errors."""
    return text.replace('#', 't').replace('vv', 'w')

def extract_clean_entries(text, state):
    """Extract entries with clean structure."""
    entries = []
    lines = text.split('\n')
    
    current_denom = ""
    for line in lines:
        line = line.strip()
        if not line or len(line) < 15:
            continue
        
        # Denomination header
        if re.match(r'^[A-Z][A-Z\s]+$', line) and len(line) < 40:
            current_denom = line.title()
            continue
        
        # Church entry
        if re.search(r'(Church|Chapel|Mission|Temple|Center|Congregation)', line, re.IGNORECASE):
            # Clean line
            clean = re.sub(r'\s{2,}', ' ', line).strip()
            entries.append({
                'state': state,
                'denomination': current_denom,
                'text': clean
            })
    
    return entries

# Process each state
states = {
    "AR": WPA_DIR / "cleaned_AR.txt",
    "DE": WPA_DIR / "cleaned_DE.txt",
    "DC": WPA_DIR / "cleaned_DC.txt",
    "ID": WPA_DIR / "cleaned_ID.txt",
    "NM": WPA_DIR / "cleaned_NM.txt",
    "ME": WPA_DIR / "cleaned_ME.txt",
    "MN": WPA_DIR / "cleaned_MN.txt",
}

print("=== PROCESSING WPA DIRECTORIES ===\n")

for state, filepath in states.items():
    if not filepath.exists():
        print(f"{state}: SKIP (not found)")
        continue
    
    text = filepath.read_text(encoding='utf-8', errors='replace')
    
    # Clean
    text = fix_ocr(text)
    text = join_fragments(text)
    
    # Extract
    entries = extract_clean_entries(text, state)
    
    # Save cleaned text
    (WPA_DIR / f"processed_{state}.txt").write_text(text, encoding='utf-8')
    
    # Save entries
    (WPA_DIR / f"entries_{state}.json").write_text(json.dumps(entries, indent=2), encoding='utf-8')
    
    print(f"{state}: {len(entries)} entries, {len(text):,} chars cleaned -> processed_{state}.txt")