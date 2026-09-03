#!/usr/bin/env python3
"""
Clean Catholic Directory 1872 for laguna processing.
"""
import re
from pathlib import Path

INPUT = Path("E:/grid/data/directories/catholic_dir_1872_formatted.txt")
OUTPUT = Path("E:/grid/data/directories/catholic_dir_1872_cleaned.txt")

text = INPUT.read_text(encoding='utf-8', errors='replace')
print(f"Input: {len(text):,} chars, {len(text.splitlines()):,} lines")

# Pass 1: Remove boilerplate
lines = text.split('\n')
cleaned = []
for line in lines:
    s = line.strip()
    if not s:
        cleaned.append('')
        continue
    if re.match(r'^Digitized\s+by\s+Google', s, re.I):
        continue
    if re.match(r'^[ivxlcdmIVXLCDM]{1,4}$', s) or re.match(r'^\d{1,4}$', s):
        continue
    if re.match(r'^[\.\s\-\_\=\*]+$', s):
        continue
    cleaned.append(s)

text = '\n'.join(cleaned)
print(f"After boilerplate: {len(text.splitlines()):,} lines")

# Pass 2: Fix OCR patterns
fixes = [
    ('Thb ', 'The '), ('Diooeee', 'Diocese'), ('Diooese', 'Diocese'),
    ('retoms', 'items'), ('publishera', 'publishers'), ('prge', 'urge'),
    ('Brook-hljn', 'Brooklyn'), ('TABIOUt DXOCBSBS', 'TABLE OF CONTENTS'),
    ('MTIVU A TUIX RKPORT', 'MINIMUM AND INDEX REPORT'),
]

for old, new in fixes:
    text = text.replace(old, new)

# Pass 3: Join fragmented lines
lines = text.split('\n')
merged = []
buf = []

for line in lines:
    s = line.strip()
    if not s:
        if buf:
            merged.append(' '.join(buf))
            buf = []
        merged.append('')
        continue
    
    if buf and not buf[-1].rstrip().endswith(('.', ':', ';', '?', '!')):
        buf.append(s)
    else:
        if buf:
            merged.append(' '.join(buf))
        buf = [s]

if buf:
    merged.append(' '.join(buf))

text = '\n'.join(merged)
print(f"After joining: {len(text):,} chars")

OUTPUT.write_text(text, encoding='utf-8')
print(f"Saved to: {OUTPUT}")

# Show sample church entries
print("\n=== Sample entries ===")
for line in text.split('\n'):
    if 'Diocese' in line or 'Church' in line or 'Pastor' in line:
        print(f"  {line[:100]}")
        if len(line) > 50:
            break