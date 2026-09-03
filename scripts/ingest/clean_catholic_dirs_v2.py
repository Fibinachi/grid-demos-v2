#!/usr/bin/env python3
"""
Final OCR cleanup for Catholic Directory files.
Produces clean JSON by diocese, ready for database import.

Usage:
    python scripts/ingest/clean_catholic_dirs_v2.py --year 1865
    python scripts/ingest/clean_catholic_dirs_v2.py --all
"""

import re
import json
from pathlib import Path

RAW_DIR = Path("E:/grid/data/directories")
OUTPUT_DIR = Path("E:/grid/data/directories/cleaned")

def clean_text(text):
    """Remove all HTML and OCR noise."""
    # Remove HTML tags completely
    text = re.sub(r'<[^>]+>', ' ', text)
    # Remove HTML entities
    text = re.sub(r'&[a-z]+;', ' ', text)
    # Remove script/style content
    text = re.sub(r'<script[^>]*>.*?</script>', ' ', text, flags=re.DOTALL|re.IGNORECASE)
    text = re.sub(r'<style[^>]*>.*?</style>', ' ', text, flags=re.DOTALL|re.IGNORECASE)
    
    # Fix hyphenated line breaks (word split across lines)
    text = re.sub(r'([a-z])-\s*\n\s*([a-z])', r'\1\2', text)
    
    # Normalize dashes
    text = re.sub(r'[—–]', '-', text)
    
    # Fix common OCR character errors
    ocr_fixes = {
        "'": "'", '"': '"', '"': '"',
        'ſ': 's', 'ﬁ': 'fi', 'ﬂ': 'fl',
    }
    for bad, good in ocr_fixes.items():
        text = text.replace(bad, good)
    
    lines = []
    for line in text.splitlines():
        line = ' '.join(line.split())  # Normalize whitespace
        line = line.strip()
        
        # Skip empty or pure noise lines
        if not line:
            continue
        if re.match(r'^[|=\-—–~_`]+$', line):
            continue
        if re.match(r'^(?:Digitized|Google|Archive|Page|Directory|Published|Printed|Manufactured|Warranted)', line, re.I):
            continue
        if re.match(r'.*\.com|.*\.org', line):
            continue
        if re.match(r'^[A-Z]{2,}\s*\d', line):
            continue
        if re.match(r'^[0-9\s\$\.,]+:', line):
            continue
            
        lines.append(line)
    
    return lines

def find_diocese_positions(lines):
    """Find all diocese/vicariate section starts."""
    positions = []
    for i, line in enumerate(lines):
        m = re.match(r'^(?:ARCH)?DIOCESE\s+OF\s+([A-Z][A-Z\s\-\']+)\.?$', line, re.I)
        if m:
            positions.append((m.group(1).strip().upper(), i))
            continue
        m = re.match(r'^(?:VICARIATE\s+APOSTOLIC\s+OF\s+)([A-Z][A-Z\s\-\']+)\.?$', line, re.I)
        if m:
            positions.append((m.group(1).strip().upper(), i))
    return positions

def extract_church_entries(lines, diocese_name, start_idx, end_idx):
    """Extract parish/institution entries from a diocese section."""
    entries = []
    section = lines[start_idx:end_idx]
    
    for line in section:
        # Match patterns like "City — St. Name. Rev. Name" or "St. Name, Address. Rev. Name"
        if re.search(r'St\.|Cathedral|Church|Holy|Immaculate|Our\s+Lady|Sacred', line, re.I):
            # Try to extract the entry
            entries.append({
                'diocese': diocese_name,
                'raw_text': line
            })
    
    return entries

def process_year(year):
    """Process a single year's directory file."""
    input_file = RAW_DIR / f"catholic_dir_{year}.txt"
    
    if not input_file.exists():
        print(f"Not found: {input_file}")
        return None
    
    print(f"Processing {year}...")
    raw_text = input_file.read_text(encoding='utf-8', errors='replace')
    clean_lines = clean_text(raw_text)
    
    print(f"  {len(raw_text.splitlines()):,} raw -> {len(clean_lines)} clean lines")
    
    # Find diocese sections
    positions = find_diocese_positions(clean_lines)
    print(f"  Found {len(positions)} diocese sections")
    
    # Extract entries per diocese
    all_entries = {}
    for i, (name, pos) in enumerate(positions):
        end = positions[i+1][1] if i+1 < len(positions) else len(clean_lines)
        entries = extract_church_entries(clean_lines, name, pos, end)
        all_entries[name] = entries
    
    return all_entries

def main():
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument('--year', type=int)
    p.add_argument('--all', action='store_true')
    p.add_argument('--dry-run', action='store_true')
    args = p.parse_args()
    
    OUTPUT_DIR.mkdir(exist_ok=True)
    
    if args.year:
        result = process_year(args.year)
        if result and not args.dry_run:
            out_file = OUTPUT_DIR / f"{args.year}_cleaned.json"
            out_file.write_text(json.dumps(result, ensure_ascii=False, indent=2))
            print(f"  Saved to {out_file}")

if __name__ == '__main__':
    main()