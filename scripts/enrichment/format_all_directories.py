#!/usr/bin/env python3
"""Batch-format all Catholic Directory OCR files. Conservative: strips only
mechanical artifacts, preserves every original word. No content changes."""
import re, os
from pathlib import Path
from datetime import datetime

SRC = Path("E:/grid/data/directories")
# Find all catholic_dir_*.txt files
files = sorted(SRC.glob("catholic_dir_*.txt"))
print(f"Found {len(files)} directory files")

for f in files:
    year = re.search(r'catholic_dir_(\d{4})\.txt', f.name)
    if not year:
        continue
    year = year.group(1)
    out_path = SRC / f"catholic_dir_{year}_formatted.txt"
    
    # Skip if already formatted
    if out_path.exists():
        continue
    
    print(f"  {year} ...", end=" ", flush=True)
    t0 = datetime.now()
    
    raw = f.read_text(encoding="utf-8", errors="ignore")
    orig_size = len(raw)
    
    # Conservative cleanup - mechanical artifacts only
    raw = re.sub(r'\n\s*Digitized\s+by\s+Google\s*\n', '\n', raw, flags=re.I)
    raw = re.sub(r'\n\s*\d{1,3}\s*\n', '\n', raw)
    raw = re.sub(r'\n\s*[ivxlcdmIVXLCDM]{1,4}\s*\n', '\n', raw)
    raw = re.sub(r'-\n\s*', '', raw)
    raw = re.sub(r'\n{3,}', '\n\n', raw)
    
    # Add diocese banners
    def add_banner(m):
        return f'\n\n{"="*70}\n{m.group(0).strip()}\n{"="*70}\n'
    raw = re.sub(r'^(ARCHDIOCESE\s+OF\s+.+?)(?:\.\s*)?$', add_banner, raw, flags=re.MULTILINE)
    raw = re.sub(r'^(DIOCESE\s+OF\s+.+?)(?:\.\s*)?$', add_banner, raw, flags=re.MULTILINE)
    
    out_path.write_text(raw, encoding="utf-8")
    elapsed = (datetime.now() - t0).total_seconds()
    new_size = len(raw)
    print(f"OK  {orig_size/1024:.0f}KB -> {new_size/1024:.0f}KB  ({elapsed:.1f}s)")

print(f"\nDone. Formatted files in {SRC}")
