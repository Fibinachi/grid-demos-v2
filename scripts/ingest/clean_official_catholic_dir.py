"""
Clean and re-format The Official Catholic Directory files (1948+).
Removes advertisement blocks and normalizes church/cleri entries.
"""
import re
import os
from pathlib import Path

DIRECTORIES = Path("E:/grid/data/directories")

# Patterns to remove (advertising, page refs, etc.)
REMOVE_PATTERNS = [
    r'Page\s+\d+',
    r'\[.*?\]',
    r'\.\.\.\.\.\.\.\.\.\.\.\.\.\.\.+',
    r'Copyright.*$',
    r'All\s+rights\s+reserved',
    r'\d{3,4}\s+Barclay\s+Street',
    r'KENEDY.*SONS',
    r'Advertisers?',
    r'Index.*Advertisers?',
    r'BUSINESS\s+SERVICES',
]

# Church listing patterns to keep and clean
CHURCH_PATTERNS = [
    r'^\d+\s+[A-Z]',  # Numbered parish entries
    r'(St\.|Sts\.|Cathedral|Church|Mission|Shrine)\s+[A-Z].*?(?:Rev\.|Pastor)',
    r'(Rev\.|Fr\.|Very\s+Rev\.|Most\s+Rev\.)\s+[A-Z].*?(?:Pastor|Rector|Administrator)',
]


def clean_line(line):
    """Clean a single line of OCR artifacts."""
    line = line.strip()
    if not line:
        return ''
    
    # Skip obvious ad/page content
    line_lower = line.lower()
    if any(skip in line_lower for skip in ['advertis', 'index of', 'classified', 'buyers guide', 'telephone:', 'fax:', 'www.']):
        return ''
    
    # Clean common OCR errors
    line = re.sub(r'[^\x00-\x7F]+', ' ', line)  # Non-ASCII
    line = re.sub(r'\s{3,}', ' ', line)  # Multiple spaces
    line = re.sub(r'^\s*[-=]{3,}\s*$', '', line)  # Separator lines alone
    
    return line


def extract_parish_blocks(text):
    """Extract parish listing blocks from the directory."""
    blocks = []
    lines = text.split('\n')
    
    current_block = []
    in_parish_section = False
    
    for line in lines:
        cleaned = clean_line(line)
        if not cleaned:
            continue
        
        # Detect parish sections
        if re.search(r'(ARCHDIOCESE|DIOCESE)\s+OF\s+[A-Z]', cleaned, re.IGNORECASE):
            in_parish_section = True
        
        if in_parish_section:
            current_block.append(cleaned)
    
    return current_block


def main():
    for year in range(1948, 2022, 1):
        fp = DIRECTORIES / f"catholic_dir_{year}_formatted.txt"
        if not fp.exists():
            continue
        
        print(f"{year}...", end=' ', flush=True)
        
        with open(fp, 'r', encoding='utf-8', errors='ignore') as f:
            text = f.read()
        
        # Extract cleaner version
        cleaned_lines = extract_parish_blocks(text)
        
        if cleaned_lines:
            out_path = DIRECTORIES / f"{year}_clean_cleaned.txt"
            with open(out_path, 'w', encoding='utf-8') as f:
                f.write('\n'.join(cleaned_lines[:10000]))  # Limit
            print(f"saved {len(cleaned_lines)} lines")
        else:
            print("no blocks")


if __name__ == '__main__':
    main()