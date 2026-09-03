#!/usr/bin/env python3
"""
Extract lines needing OCR correction to separate files.
Creates YYYY_issues.txt with only problematic lines.

This lets you review just the ~10-20% of lines that need fixing.
"""

import re
from pathlib import Path
import json

RAW_DIR = Path("E:/grid/data/directories")
OUTPUT_DIR = Path("E:/grid/data/directories/cleaned")

def has_ocr_issue(line):
    """Check if line has common OCR patterns."""
    patterns = [
        r'con[-\s]{1,3}crat',  # consecrated (split)
        r'trans[-\s]{1,3}lat', # translated (split)
        r'[A-Z]{2,}[-\s]{2,}[A-Z]{2,}', # broken caps
        r'[|\-—–_]{3,}', # artifact lines
        r'\s{3,}', # excessive space (should be normalized)
        r'[a-z]{2,}[-\s]{2,}[a-z]{2,}', # split words
    ]
    for p in patterns:
        if re.search(p, line):
            return True
    return False

def extract_issues(fp, year):
    """Extract problematic lines from file."""
    text = fp.read_text(encoding='utf-8', errors='replace')
    lines = text.splitlines()
    
    clean_lines = []
    issue_lines = []
    
    for i, line in enumerate(lines):
        if has_ocr_issue(line):
            issue_lines.append((i+1, line))
        else:
            clean_lines.append(line)
    
    # Save clean version
    clean_out = OUTPUT_DIR / f"{year}_clean_no_issues.txt"
    clean_out.write_text('\n'.join(clean_lines), encoding='utf-8')
    
    # Save issues to review
    issues_out = OUTPUT_DIR / f"{year}_issues_to_fix.txt"
    issues_out.write_text('\n'.join(f"{i}: {line}" for i, line in issue_lines), encoding='utf-8')
    
    return len(clean_lines), len(issue_lines)

def main():
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument('--year', type=int, help='Process single year')
    p.add_argument('--all', action='store_true', help='Process all formatted files')
    args = p.parse_args()
    
    OUTPUT_DIR.mkdir(exist_ok=True)
    
    if args.year:
        for pattern in [f"{args.year}_formatted.txt", f"catholic_dir_{args.year}_formatted.txt"]:
            fp = RAW_DIR / pattern
            if fp.exists():
                break
        else:
            print(f"No file for {args.year}")
            return
        
        clean, issues = extract_issues(fp, args.year)
        print(f"{args.year}: {clean} clean, {issues} lines needing review")
        print(f"  Clean saved to: {OUTPUT_DIR / f'{args.year}_clean_no_issues.txt'}")
        print(f"  Issues saved to: {OUTPUT_DIR / f'{args.year}_issues_to_fix.txt'}")
    
    elif args.all:
        years = set()
        for f in RAW_DIR.glob('*_formatted.txt'):
            try:
                name = f.stem
                if name.startswith('catholic_dir_'):
                    name = name.replace('catholic_dir_', '')
                years.add(int(name.split('_')[0]))
            except:
                pass
        
        total_clean = 0
        total_issues = 0
        for y in sorted(years):
            for pattern in [f"{y}_formatted.txt", f"catholic_dir_{y}_formatted.txt"]:
                fp = RAW_DIR / pattern
                if fp.exists():
                    break
            else:
                continue
            
            clean, issues = extract_issues(fp, y)
            total_clean += clean
            total_issues += issues
            print(f"{y}: {clean} clean, {issues} issues")
        
        print(f"\nTotal: {total_clean} clean, {total_issues} issues across {len(years)} years")
        print(f"Issues are in cleaned/YYYY_issues_to_fix.txt")

if __name__ == '__main__':
    main()