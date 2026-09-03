#!/usr/bin/env python3
"""
Manual OCR correction workflow.

1. Shows lines with OCR issues
2. Saves clean lines separately
3. You can edit YYYY_issues_to_fix.txt then run --merge to recombine

Usage:
    python scripts/ingest/manual_fix.py --year 1872 --extract
    # Edit YYYY_issues_to_fix.txt
    python scripts/ingest/manual_fix.py --year 1872 --merge
"""

import re
from pathlib import Path

RAW_DIR = Path("E:/grid/data/directories")
OUTPUT_DIR = Path("E:/grid/data/directories/cleaned")

def get_issues(fp):
    text = fp.read_text(encoding='utf-8', errors='replace')
    lines = text.splitlines()
    
    clean = []
    issues = []
    
    for i, line in enumerate(lines):
        # Check for OCR issues
        if (re.search(r'con[-\s]{1,3}crat|trans[-\s]{1,3}lat', line, re.I) or
            re.search(r'[|\-—–]{3,}', line) or
            re.search(r'\s{4,}', line)):
            issues.append((i, line))
        else:
            clean.append(line)
    
    return clean, issues

def extract(year):
    fp = RAW_DIR / f"{year}_formatted.txt"
    if not fp.exists():
        fp = RAW_DIR / f"catholic_dir_{year}_formatted.txt"
    if not fp.exists():
        print(f"No file for {year}")
        return
    
    clean, issues = get_issues(fp)
    
    # Save clean
    (OUTPUT_DIR / f"{year}_clean.txt").write_text('\n'.join(clean), encoding='utf-8')
    
    # Save issues with line numbers
    issue_text = '\n'.join(f"LINE_{i}: {line}" for i, line in issues)
    (OUTPUT_DIR / f"{year}_issues.txt").write_text(issue_text, encoding='utf-8')
    
    print(f"{year}: {len(clean)} clean, {len(issues)} issues")
    print(f"Review: {OUTPUT_DIR / f'{year}_issues.txt'}")

def merge(year):
    clean_file = OUTPUT_DIR / f"{year}_clean.txt"
    issues_file = OUTPUT_DIR / f"{year}_issues.txt"
    out_file = OUTPUT_DIR / f"{year}_final.txt"
    
    clean = clean_file.read_text(encoding='utf-8').splitlines()
    
    # Load fixed issues
    issues = {}
    if issues_file.exists():
        for line in issues_file.read_text(encoding='utf-8').splitlines():
            m = re.match(r'^LINE_(\d+): (.*)$', line)
            if m:
                issues[int(m.group(1))] = m.group(2)
    
    # Merge: use fixed issue if exists, else original clean
    lines = []
    for i, line in enumerate(clean):
        key = i + 1  # Original line number
        if key in issues:
            lines.append(issues[key])
        else:
            lines.append(line)
    
    out_file.write_text('\n'.join(lines), encoding='utf-8')
    print(f"Merged into {out_file}")

def main():
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument('--year', type=int, required=True)
    p.add_argument('--extract', action='store_true')
    p.add_argument('--merge', action='store_true')
    args = p.parse_args()
    
    if args.extract:
        extract(args.year)
    elif args.merge:
        merge(args.year)

if __name__ == '__main__':
    main()