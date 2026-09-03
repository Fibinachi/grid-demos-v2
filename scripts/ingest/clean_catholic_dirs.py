#!/usr/bin/env python3
"""
Comprehensive OCR cleanup for Catholic Directory files.
Outputs clean JSON by diocese for machine readability.

Usage:
    python scripts/ingest/clean_catholic_dirs.py --year 1865      # Clean one year
    python scripts/ingest/clean_catholic_dirs.py --all           # Clean all raw files
    python scripts/ingest/clean_catholic_dirs.py --stats         # Show stats
"""

import re
import json
from pathlib import Path
from collections import defaultdict

RAW_DIR = Path("E:/grid/data/directories")
OUTPUT_DIR = Path("E:/grid/data/directories/cleaned")

# Common OCR character fixes
OCR_CHAR_FIXES = """
s|ſ→s    |ﬁ→fi   |ﬂ→fl
—→-      |–→-     |'=
'"→"     |"'→'    
…→...

OCR Word fixes:
Sadli?ers? → Sadlier
CATHORIC → CATHOLIC
cathol?c → catholic
DIOCESAN → DIOCESAN
ARCHDIOCES → ARCHDIOCESE
"""

def clean_text(text):
    """Main cleaning pipeline - remove HTML and noise."""
    # Remove HTML tags and entities
    text = re.sub(r'<[^>]+>', ' ', text)
    text = re.sub(r'&[a-z]+;', ' ', text)
    
    # Fix hyphenated line breaks
    text = re.sub(r'([a-z])-\s*\n\s*([a-z])', r'\1\2', text)
    
    lines = text.splitlines()
    cleaned = []
    
    for line in lines:
        line = line.strip()
        if not line:
            continue
        
        # Skip pure noise/advertising lines
        if re.match(r'^[|=\-—–~`_]{3,}

def find_diocese_sections(text):
    """Extract diocese sections with boundaries."""
    sections = []
    matches = []
    
    for pattern in DIOCESE_PATTERNS:
        for m in re.finditer(pattern, text):
            matches.append((m.group(1).strip().rstrip('.'), m.start()))
    
    # Sort and dedupe
    matches = sorted(matches, key=lambda x: x[1])
    seen = set()
    unique = []
    for name, pos in matches:
        key = name.upper()
        if key not in seen and len(name) > 2:
            seen.add(key)
            unique.append((name, pos))
    
    for i, (name, start) in enumerate(unique):
        end = unique[i+1][1] if i+1 < len(unique) else min(start + 50000, len(text))
        sections.append({
            'name': name,
            'start': start,
            'end': end,
            'text': text[start:end]
        })
    
    return sections

def extract_entries(section_text, diocese_name):
    """Parse a diocese section for parish entries."""
    entries = []
    
    # Parse "City — St. Name. Rev. Name, Role" format
    # Many variations due to OCR errors
    lines = section_text.splitlines()
    
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        
        # Look for church entries (dash separator pattern)
        if re.search(r'—|—|-', line) and re.search(r'(?:St\.|Sts\.|Church|Cathedral|Immaculate|Holy|Our\s+Lady|Sacred|Santa|San)\s+', line, re.IGNORECASE):
            parts = re.split(r'—|-|—', line, maxsplit=1)
            if len(parts) == 2:
                church_part = parts[0].strip()
                clergy_part = parts[1].strip()
                
                # Extract city and church name
                church_match = re.search(r'(St\.?\s*\w+(?:[\'’]\s*\w+)?(?:\s+\w+)*)', church_part)
                church_name = church_match.group(1) if church_match else church_part
                
                entries.append({
                    'diocese': diocese_name,
                    'church_name': church_name,
                    'raw_line': line,
                    'clergy': clergy_part
                })
        
        i += 1
    
    return entries

def main():
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument('--year', type=int)
    p.add_argument('--all', action='store_true')
    p.add_argument('--chunk', action='store_true')
    p.add_argument('--dry-run', action='store_true')
    args = p.parse_args()
    
    OUTPUT_DIR.mkdir(exist_ok=True)
    
    if args.year:
        fp = RAW_DIR / f"catholic_dir_{args.year}.txt"
        if not fp.exists():
            print(f"Not found: {fp}")
            return
        
        print(f"Cleaning {fp.name}...")
        text = fp.read_text(encoding='utf-8', errors='replace')
        cleaned = clean_text(text)
        sections = find_diocese_sections(cleaned)
        
        print(f"  Found {len(sections)} diocese sections")
        
        if args.chunk:
            for s in sections[:5]:
                print(f"  {s['name']}: {len(s['text'])} chars")
        
        if not args.dry_run:
            out_json = OUTPUT_DIR / f"{args.year}_cleaned.json"
            data = []
            for s in sections:
                entries = extract_entries(s['text'], s['name'])
                data.extend(entries)
            
            out_json.write_text(json.dumps(data, ensure_ascii=False, indent=2))
            print(f"  Saved {len(data)} entries to {out_json}")

if __name__ == '__main__':
    main(), line):
            continue
        if re.match(r'^(?:Digitized|Google|Archive|Page|Directory|Published|Printed|Manufacturers?)', line, re.I):
            continue
        if re.match(r'.*\.com|.*\.org|.*\.net', line):
            continue
        if re.match(r'^[A-Z]{2,}\s*[0-9]+\s*

def find_diocese_sections(text):
    """Extract diocese sections with boundaries."""
    sections = []
    matches = []
    
    for pattern in DIOCESE_PATTERNS:
        for m in re.finditer(pattern, text):
            matches.append((m.group(1).strip().rstrip('.'), m.start()))
    
    # Sort and dedupe
    matches = sorted(matches, key=lambda x: x[1])
    seen = set()
    unique = []
    for name, pos in matches:
        key = name.upper()
        if key not in seen and len(name) > 2:
            seen.add(key)
            unique.append((name, pos))
    
    for i, (name, start) in enumerate(unique):
        end = unique[i+1][1] if i+1 < len(unique) else min(start + 50000, len(text))
        sections.append({
            'name': name,
            'start': start,
            'end': end,
            'text': text[start:end]
        })
    
    return sections

def extract_entries(section_text, diocese_name):
    """Parse a diocese section for parish entries."""
    entries = []
    
    # Parse "City — St. Name. Rev. Name, Role" format
    # Many variations due to OCR errors
    lines = section_text.splitlines()
    
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        
        # Look for church entries (dash separator pattern)
        if re.search(r'—|—|-', line) and re.search(r'(?:St\.|Sts\.|Church|Cathedral|Immaculate|Holy|Our\s+Lady|Sacred|Santa|San)\s+', line, re.IGNORECASE):
            parts = re.split(r'—|-|—', line, maxsplit=1)
            if len(parts) == 2:
                church_part = parts[0].strip()
                clergy_part = parts[1].strip()
                
                # Extract city and church name
                church_match = re.search(r'(St\.?\s*\w+(?:[\'’]\s*\w+)?(?:\s+\w+)*)', church_part)
                church_name = church_match.group(1) if church_match else church_part
                
                entries.append({
                    'diocese': diocese_name,
                    'church_name': church_name,
                    'raw_line': line,
                    'clergy': clergy_part
                })
        
        i += 1
    
    return entries

def main():
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument('--year', type=int)
    p.add_argument('--all', action='store_true')
    p.add_argument('--chunk', action='store_true')
    p.add_argument('--dry-run', action='store_true')
    args = p.parse_args()
    
    OUTPUT_DIR.mkdir(exist_ok=True)
    
    if args.year:
        fp = RAW_DIR / f"catholic_dir_{args.year}.txt"
        if not fp.exists():
            print(f"Not found: {fp}")
            return
        
        print(f"Cleaning {fp.name}...")
        text = fp.read_text(encoding='utf-8', errors='replace')
        cleaned = clean_text(text)
        sections = find_diocese_sections(cleaned)
        
        print(f"  Found {len(sections)} diocese sections")
        
        if args.chunk:
            for s in sections[:5]:
                print(f"  {s['name']}: {len(s['text'])} chars")
        
        if not args.dry_run:
            out_json = OUTPUT_DIR / f"{args.year}_cleaned.json"
            data = []
            for s in sections:
                entries = extract_entries(s['text'], s['name'])
                data.extend(entries)
            
            out_json.write_text(json.dumps(data, ensure_ascii=False, indent=2))
            print(f"  Saved {len(data)} entries to {out_json}")

if __name__ == '__main__':
    main(), line):  # Ad codes like "KA 123"
            continue
        
        cleaned.append(line)
    
    return '\n'.join(cleaned)

def find_diocese_sections(text):
    """Extract diocese sections with boundaries."""
    sections = []
    matches = []
    
    for pattern in DIOCESE_PATTERNS:
        for m in re.finditer(pattern, text):
            matches.append((m.group(1).strip().rstrip('.'), m.start()))
    
    # Sort and dedupe
    matches = sorted(matches, key=lambda x: x[1])
    seen = set()
    unique = []
    for name, pos in matches:
        key = name.upper()
        if key not in seen and len(name) > 2:
            seen.add(key)
            unique.append((name, pos))
    
    for i, (name, start) in enumerate(unique):
        end = unique[i+1][1] if i+1 < len(unique) else min(start + 50000, len(text))
        sections.append({
            'name': name,
            'start': start,
            'end': end,
            'text': text[start:end]
        })
    
    return sections

def extract_entries(section_text, diocese_name):
    """Parse a diocese section for parish entries."""
    entries = []
    
    # Parse "City — St. Name. Rev. Name, Role" format
    # Many variations due to OCR errors
    lines = section_text.splitlines()
    
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        
        # Look for church entries (dash separator pattern)
        if re.search(r'—|—|-', line) and re.search(r'(?:St\.|Sts\.|Church|Cathedral|Immaculate|Holy|Our\s+Lady|Sacred|Santa|San)\s+', line, re.IGNORECASE):
            parts = re.split(r'—|-|—', line, maxsplit=1)
            if len(parts) == 2:
                church_part = parts[0].strip()
                clergy_part = parts[1].strip()
                
                # Extract city and church name
                church_match = re.search(r'(St\.?\s*\w+(?:[\'’]\s*\w+)?(?:\s+\w+)*)', church_part)
                church_name = church_match.group(1) if church_match else church_part
                
                entries.append({
                    'diocese': diocese_name,
                    'church_name': church_name,
                    'raw_line': line,
                    'clergy': clergy_part
                })
        
        i += 1
    
    return entries

def main():
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument('--year', type=int)
    p.add_argument('--all', action='store_true')
    p.add_argument('--chunk', action='store_true')
    p.add_argument('--dry-run', action='store_true')
    args = p.parse_args()
    
    OUTPUT_DIR.mkdir(exist_ok=True)
    
    if args.year:
        fp = RAW_DIR / f"catholic_dir_{args.year}.txt"
        if not fp.exists():
            print(f"Not found: {fp}")
            return
        
        print(f"Cleaning {fp.name}...")
        text = fp.read_text(encoding='utf-8', errors='replace')
        cleaned = clean_text(text)
        sections = find_diocese_sections(cleaned)
        
        print(f"  Found {len(sections)} diocese sections")
        
        if args.chunk:
            for s in sections[:5]:
                print(f"  {s['name']}: {len(s['text'])} chars")
        
        if not args.dry_run:
            out_json = OUTPUT_DIR / f"{args.year}_cleaned.json"
            data = []
            for s in sections:
                entries = extract_entries(s['text'], s['name'])
                data.extend(entries)
            
            out_json.write_text(json.dumps(data, ensure_ascii=False, indent=2))
            print(f"  Saved {len(data)} entries to {out_json}")

if __name__ == '__main__':
    main()