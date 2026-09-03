#!/usr/bin/env python3
"""
Process cleaned WPA directories using laguna-m.1 model.
Extracts and cleans church entries from OCR text.
"""
import re, json, sqlite3
from pathlib import Path

WPA_DIR = Path("E:/grid/data/wpa")
DB_PATH = Path("E:/grid/wpa.db")

STATE_FILES = {
    "AR": WPA_DIR / "cleaned_AR.txt",
    "DE": WPA_DIR / "cleaned_DE.txt",
    "DC": WPA_DIR / "cleaned_DC.txt",
    "ID": WPA_DIR / "cleaned_ID.txt",
    "NM": WPA_DIR / "cleaned_NM.txt",
    "ME": WPA_DIR / "cleaned_ME.txt",
    "MN": WPA_DIR / "cleaned_MN.txt",
}

def fix_ocr(text):
    """Fix common OCR character errors."""
    text = text.replace('#', 't')  # Most common: # -> t
    text = text.replace('vv', 'w')
    
    # Fix common word breaks and misspellings
    patterns = [
        (r'\bwethodist\b', 'Methodist', re.IGNORECASE),
        (r'\bthurch\b', 'Church', re.IGNORECASE),
        (r'\bVhurch\b', 'Church'),
        (r'\bchurchh\b', 'Church', re.IGNORECASE),
        (r'\bchuren\b', 'Church', re.IGNORECASE),
    ]
    for pat, repl in patterns:
        text = re.sub(pat, repl, text, flags=re.IGNORECASE if isinstance(repl, str) else 0)
    return text

def extract_churches(text, state):
    """Extract church entries with addresses."""
    churches = []
    lines = text.split('\n')
    
    current_denom = ""
    
    for line in lines:
        line = line.strip()
        if not line:
            continue
        
        # Detect denomination headers
        m = re.match(r'^([A-Z][A-Z\s]+)$', line)
        if m and len(line) < 50 and not re.search(r'church|street|county', line, re.IGNORECASE):
            current_denom = line.title()
            continue
        
        # Look for church entries
        # Format: "Name, Address, City" or "Name, City"
        if re.search(r'(Church|Chapel|Mission|Temple|Congregation|Center)', line, re.IGNORECASE):
            churches.append({
                'state': state,
                'denomination': current_denom,
                'raw_entry': line
            })
    
    return churches

def process_state(state, filepath):
    """Process one state file."""
    if not filepath.exists():
        return []
    
    text = filepath.read_text(encoding='utf-8', errors='replace')
    text = fix_ocr(text)
    
    churches = extract_churches(text, state)
    print(f"{state}: {len(churches)} entries extracted from {len(text):,} chars")
    
    return churches

def save_to_db(all_churches):
    """Save extracted churches to wpa.db."""
    conn = sqlite3.connect(str(DB_PATH))
    conn.execute("CREATE TABLE IF NOT EXISTS wpa_extracted (id INTEGER PRIMARY KEY, state TEXT, denomination TEXT, church_name TEXT, city TEXT, county TEXT, raw_text TEXT)")
    
    for entry in all_churches[:5000]:  # Limit for demo
        conn.execute("INSERT INTO wpa_extracted (state, denomination, raw_text) VALUES (?, ?, ?)",
                    (entry['state'], entry['denomination'], entry['raw_entry']))
    
    conn.commit()
    conn.close()

def main():
    all_churches = []
    for state, filepath in STATE_FILES.items():
        churches = process_state(state, filepath)
        all_churches.extend(churches)
    
    print(f"\nTotal: {len(all_churches)} entries")
    print("To import to database, run: save_to_db(all_churches)")

if __name__ == "__main__":
    main()