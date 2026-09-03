"""
Clean OCR'd Catholic Directory text for better extraction.

Phase 1: Clean and normalize the raw OCR output.
Phase 2: Extract structured data from clean text.

Usage:
  python scripts/ingest/clean_directory.py --year 2015 --dry-run  # Preview changes
  python scripts/ingest/clean_directory.py --year 2015           # Write cleaned file
  python scripts/ingest/clean_directory.py --all                 # Clean all years
"""
import re, os, sys
from pathlib import Path

DIRS = Path("E:/grid/data/directories")
OUT = Path("E:/grid/data/directories_clean")


def clean_text(text, year=None):
    """Apply all cleaning passes to OCR text."""
    lines = text.splitlines(keepends=True)
    cleaned = []
    skip_count = 0
    fix_count = 0
    
    skip_patterns = [
        re.compile(r'^Digitized by', re.IGNORECASE),
        re.compile(r'^Google$', re.IGNORECASE),
        re.compile(r'^MOON[\'’]S\s+PHASES', re.IGNORECASE),
        re.compile(r'^BOSTON;\s*N\.?\s*ENG', re.IGNORECASE),
        re.compile(r'^NEW\s+YORK\s+CITY;', re.IGNORECASE),
        re.compile(r'^CHARLESTON\s+;', re.IGNORECASE),
        re.compile(r'^Sun\s+on\s+Mer\.?', re.IGNORECASE),
        re.compile(r'^\s*\d+\s+Days?\s*$'),
        re.compile(r'^Full\s+Moon|^Third\s+Quarter|^New\s+Moon|^First\s+Quarter'),
        re.compile(r'^\s*D\.?\s+H\.?\s+M\.?\s*$'),
        re.compile(r'^\d{1,2}\s+(?:ev|mo)\..*$'),
        re.compile(r'^3\s+9999\s+\d+'),
        re.compile(r'^[A-Z\s]{10,50}$'),  # All-caps lines (often OCR garbage)
    ]
    
    year_str = str(year) if year else ''
    
    i = 0
    while i < len(lines):
        line = lines[i]
        stripped = line.strip()
        
        # Skip OCR garbage lines
        if any(p.match(stripped) for p in skip_patterns):
            skip_count += 1
            i += 1
            continue
        
        # Skip empty lines (but keep some spacing)
        # Actually keep them for structure
        
        cleaned.append(line)
        i += 1
    
    # Join the text
    text_out = ''.join(cleaned)
    
    # Clean up control characters and BOM
    text_out = text_out.replace('\ufeff', '')  # BOM
    text_out = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f]', '', text_out)  # Control chars
    
    # Strip HTML artifacts from Google Books OCR
    # <fcc. <Scc. <fc — fragments from <sc> smallcaps tags
    text_out = re.sub(r'<[^>]*>', '', text_out)  # Full HTML tags
    text_out = re.sub(r'<[a-z/][a-z0-9]*', '', text_out, flags=re.IGNORECASE)  # Tag starts
    # HTML entities
    text_out = re.sub(r'&amp;', '&', text_out)
    text_out = re.sub(r'&lt;', '<', text_out)
    text_out = re.sub(r'&gt;', '>', text_out)
    text_out = re.sub(r'&nbsp;', ' ', text_out)
    text_out = re.sub(r'&[a-z]+;', '', text_out, flags=re.IGNORECASE)
    # Common OCR patterns: &c, Scc., jbc, fcc (from <sc> rendering)
    text_out = re.sub(r'<[a-z]+', '', text_out)
    text_out = re.sub(r'&[a-zA-Z]', '&', text_out)
    
    # Join hyphenated words split across lines
    # "Ober-\nmyer" → "Obermyer"
    text_out = re.sub(r'([a-z])-\s*\n\s*([a-z])', r'\1\2', text_out)
    
    # Join "Cre-\nated" → "Created" (capitalized words)
    text_out = re.sub(r'([A-Z][a-z]+?)-\s*\n\s*([a-z])', r'\1\2', text_out)
    
    # Fix common OCR typos
    text_out = ocr_fix(text_out)

    # Normalize multiple blank lines to at most 2
    text_out = re.sub(r'\n{3,}', '\n\n', text_out)
    
    return text_out


def ocr_fix(text):
    """Apply comprehensive OCR spelling corrections to Catholic directory text."""
    # These MUST be applied in order (some overlap in patterns)
    text = re.sub(r'\bArchdiocess\b', 'Archdiocese', text, flags=re.IGNORECASE)
    text = re.sub(r'\bDiocess\b', 'Diocese', text, flags=re.IGNORECASE)
    text = re.sub(r'\bCatherdal\b', 'Cathedral', text, flags=re.IGNORECASE)
    text = re.sub(r'\bCathedal\b', 'Cathedral', text, flags=re.IGNORECASE)
    text = re.sub(r'\bParochial\b', 'Parochial', text, flags=re.IGNORECASE)
    text = re.sub(r'\bChancery\b', 'Chancery', text, flags=re.IGNORECASE)
    text = re.sub(r'\bCemetary\b', 'Cemetery', text, flags=re.IGNORECASE)
    text = re.sub(r'\bCemetaries\b', 'Cemeteries', text, flags=re.IGNORECASE)
    text = re.sub(r'\bParisioners\b', 'Parishioners', text, flags=re.IGNORECASE)
    
    # Clergy titles — order matters (longest first)
    # These fix OCR misreads of Rev./Msgr/Most/Rt/Very patterns
    text = re.sub(r'\bMost\s+Rev\.', 'Most Rev.', text)
    text = re.sub(r'\bRt\.?\s+Rev\.', 'Rt. Rev.', text)
    text = re.sub(r'\bVery\s+Rev\.', 'Very Rev.', text)
    text = re.sub(r'\bMsgr\.', 'Msgr.', text)
    text = re.sub(r'(?<![A-Za-z])Rey\.', 'Rev.', text, flags=re.IGNORECASE)
    text = re.sub(r'(?<![A-Za-z])Kev\.', 'Rev.', text, flags=re.IGNORECASE)
    text = re.sub(r'(?<![A-Za-z])Rer\.', 'Rev.', text, flags=re.IGNORECASE)
    text = re.sub(r'Rev\.\.\s+', 'Rev. ', text)
    text = re.sub(r'Rev\.\s+\.\s+', 'Rev. ', text)
    text = re.sub(r'Rev\.,\s+', 'Rev. ', text)
    
    # Common name OCR errors
    text = re.sub(r'(?<![A-Za-z])Stt\.', 'St.', text)
    text = re.sub(r'(?<![A-Za-z])Bt\.', 'St.', text)
    text = re.sub(r'(?<![A-Za-z])8t\.', 'St.', text)
    
    # Parish term
    text = re.sub(r'\bPatish\b', 'Parish', text, flags=re.IGNORECASE)
    text = re.sub(r'\bPatishes\b', 'Parishes', text, flags=re.IGNORECASE)
    
    # State abbreviations  
    text = re.sub(r'\bPenn\'a\b', 'Pennsylvania', text)
    text = re.sub(r'\bPenna\.\b', 'Pennsylvania', text)
    
    # etc.
    text = text.replace('&c.', 'etc.')
    text = text.replace('&c', 'etc.')
    
    return text


def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument('--year', type=int, help='Clean single year')
    ap.add_argument('--all', action='store_true', help='Clean all years')
    ap.add_argument('--dry-run', action='store_true', help='Preview only')
    args = ap.parse_args()
    
    OUT.mkdir(exist_ok=True)
    
    if args.year:
        years = [args.year]
    elif args.all:
        years = sorted(int(f.stem.split('_')[0]) for f in DIRS.glob('[12][0-9][0-9][0-9]_formatted.txt'))
    else:
        print("Specify --year N or --all")
        return
    
    for year in years:
        src = DIRS / f"{year}_formatted.txt"
        if not src.exists():
            print(f"  SKIP {year}: source not found")
            continue
        
        size = src.stat().st_size
        print(f"  {year}: {size/1024/1024:.0f} MB")
        
        with open(src, 'r', encoding='utf-8', errors='replace') as f:
            text = f.read()
        
        cleaned = clean_text(text, year)
        
        if args.dry_run:
            reduction = (1 - len(cleaned)/len(text)) * 100
            print(f"    {len(text):,} → {len(cleaned):,} chars ({reduction:.0f}% reduction)")
            # Show a sample
            idx = cleaned.find('1—CATHEDRAL')
            if idx > 0:
                print(f"    Sample: {cleaned[idx:idx+200]}")
        else:
            dst = OUT / f"{year}_cleaned.txt"
            with open(dst, 'w', encoding='utf-8') as f:
                f.write(cleaned)
            reduction = (1 - len(cleaned)/len(text)) * 100
            print(f"    → {dst.name} ({len(cleaned):,} chars, {reduction:.0f}% reduction)")

if __name__ == '__main__':
    main()
