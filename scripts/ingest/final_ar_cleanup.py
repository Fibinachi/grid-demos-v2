#!/usr/bin/env python3
"""
Final cleanup for Arkansas WPA directory using laguna-m.1.
"""
import re
from pathlib import Path

WPA_DIR = Path("E:/grid/data/wpa")
INPUT = WPA_DIR / "cleaned_AR.txt"
OUTPUT = WPA_DIR / "final_AR_clean.txt"

def clean_arkansas_ocr(text):
    """Clean Arkansas-specific OCR patterns."""
    # Character fixes
    text = text.replace('#', 'M')  # M OCR
    
    # Word fixes
    fixes = [
        ('Ouachita', 'Ouachita'), ('Craighcad', 'Craighead'), ('Craignead', 'Craighead'),
        ('Carthaze', 'Carthage'), ('Dallas', 'Dallas'), ('England', 'England'),
        ('Howard', 'Howard'), ('Hempstead', 'Hempstead'),
        ('Lunceford', 'Lunceford'), ('Prairic', 'Prairie'),
        ('Trumann', 'Trumann'), ('Phillins', 'Phillips'),
        ('Edfinburg', 'Edinburgh'), ('Edinburz', 'Edinburgh'),
        ('Hazlette', 'Hazel'), ('Bearden', 'Bearden'), ('Providenes', 'Providence'),
        ('Hopewli', 'Hopewell'), ('Friendship', 'Friendship'),
        ('Antiocl', 'Antioch'), ('Canaan', 'Canaan'),
        ('Graves', 'Graves'), ('Cleveland', 'Cleveland'),
        ('Macedonia', 'Macedonia'), ('New Sdshurg', 'New Edinburg'),
        ('Bethesda', 'Bethesda'), ('Thorntzon', 'Thornton'),
        ('Pipercy', 'Piper'), ('Round Hill', 'Round Hill'),
    ]
    
    for wrong, right in fixes:
        text = text.replace(wrong, right)
    
    # Fix fragmented words where spaces/breaks occurred
    text = re.sub(r'\b([A-Z][a-z]{2,})\s+([a-z]{2,})\b', r'\1\2', text)
    
    # Remove stray artifacts
    text = re.sub(r'[|\x00-\x1f]+', '', text)
    
    return text

def extract_entries(text):
    """Extract structured entries from cleaned text."""
    entries = []
    lines = text.split('\n')
    
    for line in lines:
        line = line.strip()
        if not line or len(line) < 10:
            continue
        
        # Look for lines that appear to be church entries
        if re.search(r'[A-Z][a-z]+ (?:Chapel|Church|Mission|Baptist|Congregation|Center)', line, re.IGNORECASE):
            entries.append(line)
    
    return entries

text = INPUT.read_text(encoding='utf-8', errors='replace')
cleaned = clean_arkansas_ocr(text)
OUTPUT.write_text(cleaned, encoding='utf-8')

print(f"Cleaned: {len(cleaned):,} chars")

entries = extract_entries(cleaned)
print(f"Entries found: {len(entries)}")

# Show some
print("\n=== Sample entries ===")
for e in entries[:20]:
    print(f"  {e[:100]}")