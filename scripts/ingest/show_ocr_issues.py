#!/usr/bin/env python3
"""
Show OCR issues in formatted files, line by line.
Identifies lines that need manual correction.

Usage:
    python scripts/ingest/show_ocr_issues.py --year 1872
    python scripts/ingest/show_ocr_issues.py --all --max-lines 100
"""

import re
from pathlib import Path

RAW_DIR = Path("E:/grid/data/directories")

# OCR issue patterns
ISSUE_PATTERNS = [
    (r'\bcon[-\s]{1,3}crat', 'consecrated (split word)'),
    (r'[A-Z]{2,}[-\s][A-Z]{2,}', 'broken capitalization'),
    (r'[\w\']{1,3}\s[\w\']{1,3}\s[\w\']{1,3}\s[\w\']{1,3}\s[\w\']{1,3}', 'over-spaced words'),
    (r'[\|\-—–]{3,}', 'artifact line'),
    (r'\.{2,}', 'multiple dots (word break)'),
    (r'[A-Z][a-z]{1,2}\s[A-Z][a-z]{1,2}\s[A-Z][a-z]{1,2}', 'odd spacing pattern'),
]

def check_line(line):
    """Return issues found in line, or None."""
    issues = []
    for pattern, desc in ISSUE_PATTERNS:
        if re.search(pattern, line):
            issues.append(desc)
    return issues if issues else None

def process_file(fp, year, max_lines=1000):
    lines = fp.read_text(encoding='utf-8', errors='replace').splitlines()
    
    issues = []
    for i, line in enumerate(lines):
        line_issues = check_line(line)
        if line_issues:
            issues.append((i+1, line[:100], line_issues))
            if len(issues) >= max_lines:
                break
    
    return issues

def main():
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument('--year', type=int)
    p.add_argument('--all', action='store_true')
    p.add_argument('--max-lines', type=int, default=100)
    args = p.parse_args()
    
    if args.year:
        for pattern in [f"{args.year}_formatted.txt", f"catholic_dir_{args.year}_formatted.txt"]:
            fp = RAW_DIR / pattern
            if fp.exists():
                break
        else:
            print(f"No file found for {args.year}")
            return
        
        issues = process_file(fp, args.year, args.max_lines)
        print(f"Year {args.year}: {len(issues)} lines with OCR issues found\n")
        
        for line_num, line, issue_list in issues[:args.max_lines]:
            print(f"Line {line_num}: {line}")
            print(f"  Issues: {', '.join(issue_list)}\n")
    
    elif args.all:
        print("File - Total lines - Lines with OCR issues")
        for y in [1865, 1866, 1867, 1868, 1872, 1873][args.max_lines:]:  # Test few years
            for pattern in [f"{y}_formatted.txt", f"catholic_dir_{y}_formatted.txt"]:
                fp = RAW_DIR / pattern
                if fp.exists():
                    break
            else:
                continue
            
            issues = process_file(fp, y, 100)
            lines = len(fp.read_text(encoding='utf-8', errors='replace').splitlines())
            print(f"{y}: {lines} lines - {len(issues)} issues")

if __name__ == '__main__':
    main()