#!/usr/bin/env python3
"""
Final OCR cleanup and extraction for WPA directories.
Processes cleaned files and extracts structured church data.
"""
import re, json
from pathlib import Path

WPA_DIR = Path("E:/grid/data/wpa")

def final_ocr_cleanup(text):
    """Apply comprehensive OCR character fixes."""
    # Character confusions
    char_fixes = [
        (r'#', 't'),  # # often = t in typewriter OCR
        (r'\bwethodist\b', 'Methodist', re.IGNORECASE),
        (r'\bchurchh\b', 'church', re.IGNORECASE),
        (r'\bchuren\b', 'church', re.IGNORECASE),
        (r'thurch', 'church'),
        (r'\bVhurch\b', 'Church'),
        (r'\bMethcdist\b', 'Methodist'),
        (r'\bMethcdist\b', 'Methodist'),
    ]
    
    for fix in char_fixes:
        if len(fix) == 3:
            text = re.sub(fix[0], fix[1], text, flags=fix[2])
        else:
            text = text.replace(fix[0], fix[1])
    
    # Remove stray artifacts
    text = re.sub(r'[|\\\{\}<>]{2,}', '', text)
    
    return text

def extract_church_entries(text, state_code):
    """Extract church entries from cleaned text."""
    entries = []
    lines = text.split('\n')
    
    current_denom = None
    
    for line in lines:
        line = line.strip()
        if not line or len(line) < 10:
            continue
        
        # Detect denomination header
        if re.match(r'^(ADVENTIST|AFRICAN|BAPTIST|BUDDHIST|CATHOLIC|CHRISTIAN|CHURCH|CONGREGATIONAL|EP[IC]*SCOPAL|JEWISH|LUTHERAN|MENNONITE|METHODIST|NAZARENE|ORTHODOX|PENTECOSTAL|PRESBYTERIAN|PROTESTANT|ROMAN|SAINT|SANCTUARY|SALVATION|SEVENTH|SOCIETY|SPIRITUALIST|UNITARIANS?|ZION)', line, re.IGNORECASE):
            current_denom = line.rstrip('.').strip()
            continue
        
        # Look for church entries: contains church name + location
        if re.search(r'(Church|Chapel|Mission|Temple|Center|Congregation|church)', line, re.IGNORECASE):
            # Pattern: "Name, Address, City, County"
            # Or: "Name (address info) - City"
            entries.append({
                'state': state_code,
                'denomination': current_denom,
                'raw_line': line
            })
    
    return entries

def process_state(state_code, input_file, output_file):
    """Process one state directory."""
    if not input_file.exists():
        print(f"SKIP {state_code}: file not found")
        return []
    
    text = input_file.read_text(encoding='utf-8', errors='replace')
    cleaned = final_ocr_cleanup(text)
    
    # Save cleaned version
    cleaned_file = WPA_DIR / f"final_cleaned_{state_code}.txt"
    cleaned_file.write_text(cleaned, encoding='utf-8')
    
    entries = extract_church_entries(cleaned, state_code)
    
    # Save entries JSON
    entries_file = WPA_DIR / f"entries_{state_code}.json"
    entries_file.write_text(json.dumps(entries[:500], indent=2), encoding='utf-8')  # Limit for demo
    
    print(f"{state_code}: {len(cleaned):,} chars cleaned -> {len(entries)} entries extracted")
    return entries

def main():
    states = ['AR', 'DE', 'DC', 'ID', 'NM', 'ME', 'MN']
    
    print("=== FINAL OCR CLEANUP AND EXTRACTION ===\n")
    
    for state in states:
        input_file = WPA_DIR / f"cleaned_{state}.txt"
        process_state(state, input_file, None)
    
    print("\n=== READY FOR DATABASE IMPORT ===")
    print("Run: python scripts/ingest/import_wpa_to_db.py")

if __name__ == "__main__":
    main()