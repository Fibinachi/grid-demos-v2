#!/usr/bin/env python3
"""
Extract church entries from cleaned WPA text using laguna-m.1 model.
POC: Arkansas (cleaned_AR.txt)
"""
import re, json, sqlite3
from pathlib import Path

WPA_DIR = Path("E:/grid/data/wpa")
DB_PATH = Path("E:/grid/wpa.db")

def extract_entries(state_code):
    """Extract church entries from cleaned text."""
    input_file = WPA_DIR / f"cleaned_{state_code}.txt"
    if not input_file.exists():
        print(f"File not found: {input_file}")
        return 0
    
    text = input_file.read_text(encoding='utf-8', errors='replace')
    print(f"Processing {state_code}: {len(text):,} chars")
    
    # Simple pattern-based extraction as fallback
    entries = []
    
    # Split by denomination sections
    lines = text.split('\n')
    
    # Find lines that look like: "Church Name, Address, City, County"
    # or "Church Name (address info) - City"
    address_pattern = re.compile(r'([A-Z][\w\s\.\-\']+?(?:Church|Chapel|Mission|Temple|Center|Congregation))[\s,]+([A-Z][\w\s\.]+(?:Street|St\.|Ave|Road|Rd\.|Route))?,?\s*([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)')
    
    # Find denomination headers
    denom_pattern = re.compile(r'^(ADVENTIST|AFRICAN|BAPTIST|BUDDHIST|CATHOLIC|CHRISTIAN|CHURCH|CONGREGATIONAL|EP[IC]*SCOPAL|JEWISH|LUTHERAN|MENNONITE|METHODIST|NAZARENE|ORTHODOX|PENTECOSTAL|PRESBYTERIAN|PROTESTANT|ROMAN|SAINT|SANCTUARY|SALVATION|SOCIETY|SPIRITUALIST|UNITARIANS?|ZION)', re.IGNORECASE)
    
    current_denom = None
    for line in lines:
        line = line.strip()
        if not line or len(line) < 10:
            continue
        
        # Check for denomination header
        d_match = denom_pattern.match(line)
        if d_match:
            current_denom = d_match.group(1).title()
            continue
        
        # Try to extract church entry
        # Format varies: "Name, address, city" or "Name, city" (no address)
        if re.search(r'(Church|Chapel|Mission|Temple|Center|Congregation|church)', line, re.IGNORECASE):
            entries.append({'denomination': current_denom, 'raw': line})
    
    print(f"  Found {len(entries)} potential church entries")
    return entries

def main():
    states = ['AR', 'DE', 'DC', 'ID', 'NM', 'ME', 'MN']
    all_entries = {}
    
    for state in states:
        entries = extract_entries(state)
        all_entries[state] = entries
    
    # Save summary
    print("\n=== SUMMARY ===")
    for state, entries in all_entries.items():
        print(f"{state}: {len(entries)} entries")

if __name__ == "__main__":
    main()