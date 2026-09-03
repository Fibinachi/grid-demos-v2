#!/usr/bin/env python3
"""
Individual state cleanup with targeted OCR fixes.
"""
import re
from pathlib import Path

WPA_DIR = Path("E:/grid/data/wpa")

def clean_state_file(state, input_path, output_path):
    """Clean one state's file with targeted fixes."""
    text = input_path.read_text(encoding='utf-8', errors='replace')
    
    # Universal fixes
    text = text.replace('#', 't')
    text = text.replace('vv', 'w')
    text = re.sub(r'\bwethodist\b', 'Methodist', text, flags=re.IGNORECASE)
    text = re.sub(r'\bMmethodist\b', 'Methodist', text, flags=re.IGNORECASE)
    text = re.sub(r'\bthurch\b', 'Church', text, flags=re.IGNORECASE)
    text = re.sub(r'\bVhurch\b', 'Church', text)
    
    # State-specific fixes
    if state == "AR":
        text = text.replace('Craighcad', 'Craighead')
        text = text.replace('Ounchita', 'Ouachita')
        text = text.replace('Carthaze', 'Carthage')
        text = text.replace('Faulknor', 'Faulkner')
        text = text.replace('Independenc', 'Independence')
        text = text.replace('Washington vashington', 'Washington')
        text = text.replace('Feyetteville', 'Fayetteville')
        text = text.replace('Wae', 'Way')
    elif state == "DE":
        text = re.sub(r'Delaware', 'Delaware', text)
        text = re.sub(r'Wil\.?', 'Wilmington', text)
    elif state == "MN":
        text = text.replace('Minneapolis', 'Minneapolis')
    
    # Remove artifacts
    text = re.sub(r'[|\x00-\x1f]{2,}', '', text)
    text = re.sub(r'\s{3,}', '\n', text)  # Collapse multiple spaces to newlines
    
    output_path.write_text(text, encoding='utf-8')
    return len(text)

# Process each state
state_files = {
    "AR": WPA_DIR / "cleaned_AR.txt",
    "DE": WPA_DIR / "cleaned_DE.txt",
    "DC": WPA_DIR / "cleaned_DC.txt",
    "ID": WPA_DIR / "cleaned_ID.txt",
    "NM": WPA_DIR / "cleaned_NM.txt",
    "ME": WPA_DIR / "cleaned_ME.txt",
    "MN": WPA_DIR / "cleaned_MN.txt",
}

for state, input_path in state_files.items():
    if input_path.exists():
        output_path = WPA_DIR / f"final_{state}.txt"
        chars = clean_state_file(state, input_path, output_path)
        print(f"{state}: {chars:,} chars cleaned -> final_{state}.txt")

print("\nDone. Check final_{state}.txt files.")