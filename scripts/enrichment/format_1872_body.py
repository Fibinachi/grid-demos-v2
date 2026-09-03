#!/usr/bin/env python3
"""Extract diocese sections from raw OCR and append cleaned text to 1872_formatted.txt"""
import re
from pathlib import Path

RAW = Path("E:/grid/data/directories/catholic_dir_1872.txt")
OUT = Path("E:/grid/data/directories/1872_formatted.txt")

text = RAW.read_text(encoding="utf-8", errors="ignore")

# Find where Baltimore archdiocese starts (first real diocese section)
start = text.find("ARCHDIOCESE  OF  BALTIMORE.")
if start < 0:
    print("Baltimore not found!")
    exit(1)

# Take everything from Baltimore onward
body = text[start:]

# Clean: remove "Digitized by Google" lines
body = re.sub(r'\n\s*Digitized\s+by\s+Google\s*\n', '\n', body, flags=re.I)

# Remove isolated page numbers (lines that are just a 1-3 digit number)
body = re.sub(r'\n\s*\d{1,3}\s*\n', '\n', body)

# Remove isolated Roman numeral pages
body = re.sub(r'\n\s*[ivxlcdmIVXLCDM]{1,4}\s*\n', '\n', body)

# Remove lines that are just "oo", "rt", "i . S'**", etc. (OCR artifacts)
body = re.sub(r'\n\s*[oO]{2,}\s*\n', '\n', body)
body = re.sub(r'\n\s*rt\s*\n', '\n', body)
body = re.sub(r'\n\s*i\s*\.\s*S[\'*]+\s*\n', '\n', body)

# Join broken lines: lines ending mid-word (hyphenated at line break)
body = re.sub(r'-\n\s*', '', body)  # remove hyphenation breaks

# Join short continuation lines (lines < 50 chars that don't end with punctuation)
lines = body.split('\n')
merged = []
for line in lines:
    s = line.strip()
    if not s:
        merged.append('')
        continue
    # Keep section headers as-is (all-caps lines)
    if s.isupper() and len(s) > 10:
        merged.append(s)
        continue
    merged.append(s)

body = '\n'.join(merged)

# Normalize multiple blank lines
body = re.sub(r'\n{3,}', '\n\n', body)

# Append to formatted file
with open(OUT, 'a', encoding='utf-8') as f:
    f.write('\n')
    f.write(body)

print(f"Appended {len(body):,} chars to {OUT}")
print(f"Total output: {OUT.stat().st_size:,} bytes")
