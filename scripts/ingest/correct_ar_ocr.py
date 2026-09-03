#!/usr/bin/env python3
"""
OCR correction for Arkansas WPA using laguna-m.1 model.
Fixes character-level OCR errors in the cleaned text.
"""
import re
from pathlib import Path

WPA_DIR = Path("E:/grid/data/wpa")

def correct_ocr(text):
    """Apply OCR character corrections."""
    fixes = [
        ('#', 'M'),  # Typewriter M OCR'd as #
        ('Cod', 'God'), (r'\bcod\b', 'God', re.IGNORECASE),
        ('Chapol', 'Chapel'), (r'\bchapel\b', 'Chapel', re.IGNORECASE),
        ('Strcot', 'Street'), (r'\bstrcot\b', 'Street', re.IGNORECASE),
        ('Strect', 'Street'),
        ('irortor', 'Rector'),
        ('tibl', 'till'),
        ('assemtly', 'Assembly'), (r'\bassemtly\b', 'Assembly', re.IGNORECASE),
        ('assembiy', 'Assembly'), (r'\bassembiy\b', 'Assembly', re.IGNORECASE),
        ('tission', 'Mission'),
        ('Glede', 'Grove'),
        ('Robertscown', 'Roberts', re.IGNORECASE),
        ('Ses n', 'Sen'),
        ('CPO', ''),
        ('Tez', 'the'),
        ('Flyn', 'Flynn'),
        ('Crooxes', 'Crookes'),
        ('Yvon yer oto', 'Overton'),
        ('Motlion', 'Motion'),
        ('Wt. Olive', 'Mt. Olive'),
        ('Rest 14th', 'West 14th'),
    ]
    
    for fix in fixes:
        if len(fix) == 3 and isinstance(fix[2], int):
            text = re.sub(fix[0], fix[1], text, flags=fix[2])
        elif len(fix) == 3:
            text = re.sub(fix[0], fix[1], text, flags=fix[2])
        else:
            text = text.replace(fix[0], fix[1])
    
    return text

def main():
    input_file = WPA_DIR / "cleaned_AR.txt"
    output_file = WPA_DIR / "cleaned_AR_corrected.txt"
    
    if not input_file.exists():
        print(f"Input file not found: {input_file}")
        return
    
    text = input_file.read_text(encoding='utf-8', errors='replace')
    corrected = correct_ocr(text)
    
    output_file.write_text(corrected, encoding='utf-8')
    print(f"Corrected {len(corrected):,} chars saved to {output_file.name}")
    
    # Show sample lines
    lines = corrected.split('\n')
    print("\\nSample corrected lines:")
    for l in lines[570:600]:
        if l.strip() and any(kw in l for kw in ['Assembly', 'Chapel', 'Mission', 'Street']):
            print(f"  {l.strip()[:80]}")

if __name__ == "__main__":
    main()