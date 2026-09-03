#!/usr/bin/env python3
"""
Clean and standardize Catholic Directory OCR text.
- Remove Google digitization boilerplate
- Join broken line-wrapped paragraphs
- Fix common OCR character errors
- Normalize diocese section headers
- Output machine-readable standardized text

Usage:
  python scripts/enrichment/clean_directory_ocr.py 1872
  python scripts/enrichment/clean_directory_ocr.py 1872 --output cleaned_1872.txt
"""
import re, sys
from pathlib import Path

YEAR = sys.argv[1] if len(sys.argv) > 1 else "1872"
INPUT = Path(f"E:/grid/data/directories/catholic_dir_{YEAR}.txt")
OUTPUT = Path(sys.argv[2]) if len(sys.argv) > 2 else Path(f"E:/grid/data/directories/catholic_dir_{YEAR}_clean.txt")

text = INPUT.read_text(encoding="utf-8", errors="ignore")
print(f"Input: {len(text):,} chars, {len(text.splitlines()):,} lines")

# ── Pass 1: Remove boilerplate lines ──
lines = text.split('\n')
cleaned = []
for line in lines:
    s = line.strip()
    # Skip empty
    if not s: 
        cleaned.append('')
        continue
    # Skip Google digitization markers
    if re.match(r'^Digitized\s+by\s+Google', s, re.I):
        continue
    # Skip page number fragments (isolated 1-3 digit numbers or Roman numerals)
    if re.match(r'^[ivxlcdmIVXLCDM]{1,4}$', s) or re.match(r'^\d{1,4}$', s):
        continue
    # Skip pure punctuation/artifact lines
    if re.match(r'^[\.\s\-\_\=\*]+$', s):
        continue
    cleaned.append(s)

text = '\n'.join(cleaned)
print(f"  After boilerplate removal: {len(text.splitlines()):,} lines")

# ── Pass 2: Join broken paragraphs ──
# A line that doesn't end with sentence-ending punctuation is likely a continuation
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
    
    # Section headers: all-caps short lines, or lines ending with a period followed by nothing
    # Don't merge if: all caps + short, or starts with a known header pattern
    is_header = (
        (s.isupper() and len(s) < 80) or
        bool(re.match(r'^(ARCHDIOCESE|DIOCESE)\s+OF\s+', s, re.I)) or
        bool(re.match(r'^(ECCLESIASTICAL\s+PROVINCE|PROVINCE\s+OF)', s, re.I)) or
        bool(re.match(r'^[A-Z\s]{10,60}$', s) and len(s) > 20)  # all-caps title
    )
    
    if is_header:
        if buf:
            merged.append(' '.join(buf))
            buf = []
        merged.append(s)
        continue
    
    # Check if line ends mid-sentence (no period, no colon, not a list item)
    ends_clean = s.rstrip().endswith(('.', ':', ';', '?', '!', ')', ']'))
    # Also check: if next line would be a new sentence (starts with capital and this ends with period-ish)
    starts_continuation = bool(buf) and not buf[-1].rstrip().endswith(('.', ':', ';', '?', '!'))
    
    if buf and not buf[-1].rstrip().endswith(('.', ':', '?', '!')):
        # Previous line didn't end with sentence punctuation - merge
        buf.append(s)
    elif not ends_clean and len(s) < 60:
        # Short line without ending punctuation - probably a continuation
        buf.append(s)
    else:
        if buf:
            merged.append(' '.join(buf))
        buf = [s]

if buf:
    merged.append(' '.join(buf))

text = '\n'.join(merged)
print(f"  After paragraph merging: {len(text.splitlines()):,} lines")

# ── Pass 3: Fix common OCR errors ──
OCR_FIXES = [
    # Common character confusions
    ('Thb ', 'The '), ('thb ', 'the '),
    (' aBd ', ' and '), ('Ate ', ' the '),
    ('tbe ', 'the '), ('tbeir', 'their'),
    ('wbieh', 'which'), ('wbicb', 'which'),
    ('wben', 'when'), ('wbom', 'whom'),
    ('Diooeee', 'Diocese'), ('Diooese', 'Diocese'),
    ('contaiiis', 'contains'), ('compriaea', 'comprises'),
    ('establisbed', 'established'), ('publisbed', 'published'),
    ('Cburcb', 'Church'), ('cbapel', 'chapel'),
    ('Bisbop', 'Bishop'), ('Arcbbisbop', 'Archbishop'),
    ('Rev\\.', 'Rev.'), ('Rey\\.', 'Rev.'),
    ('Very Rev\\.', 'Very Rev.'), ('Rt\\. Rev\\.', 'Rt. Rev.'),
    ('consecrated', 'consecrated'), ('appoiuted', 'appointed'),
    ('Catbedral', 'Cathedral'), ('Cathedral', 'Cathedral'),
    ('Seminary', 'Seminary'), ('seminary', 'seminary'),
    ('College', 'College'), ('college', 'college'),
    ('Academy', 'Academy'), ('academy', 'academy'),
    ('Convent', 'Convent'), ('convent', 'convent'),
    ('Orpban', 'Orphan'), ('orpban', 'orphan'),
    ('Asylnm', 'Asylum'), ('asylnm', 'asylum'),
    ('HospitaJ', 'Hospital'), ('bospitaJ', 'hospital'),
    ('Montreal', 'Montreal'), ('Quebec', 'Quebec'),
    ('Pbila', 'Phila'), ('Pbiladelpbia', 'Philadelphia'),
    ('Baltimorc', 'Baltimore'), ('Cincinnati', 'Cincinnati'),
    ('Cbicago', 'Chicago'), ('Detioit', 'Detroit'),
    ('Milwankee', 'Milwaukee'), ('Cleveland', 'Cleveland'),
    ('Pittsbnrg', 'Pittsburgh'), ('Pittsburgb', 'Pittsburgh'),
    ('Bnffalo', 'Buffalo'), ('Bnrialo', 'Buffalo'),
    ('Albauy', 'Albany'), ('Brooklyn', 'Brooklyn'),
    ('B rook lyn', 'Brooklyn'), ('Brook-hljn', 'Brooklyn'),
    ('Ricbmond', 'Richmond'), ('Cbarleston', 'Charleston'),
    ('Savannab', 'Savannah'), ('Mobile', 'Mobile'),
    ('N atchez', 'Natchez'), ('Natcbez', 'Natchez'),
    ('Galveston', 'Galveston'), ('S an Antonio', 'San Antonio'),
    ('Santa Fe', 'Santa Fe'), ('8 an Francisco', 'San Francisco'),
    # Number confusions
    ('I8', '18'), ('1$', '18'), ('i8', '18'),
    # Punctuation fixes
    (' ,', ','), (' .', '.'), (' ;', ';'), (' :', ':'),
    ('“', '"'), ('”', '"'), ('‘', "'"), ('’', "'"),
    ('--', '—'), (' — ', ' — '),
    # Multiple spaces
]

for old, new in OCR_FIXES:
    text = text.replace(old, new)

# Normalize whitespace
text = re.sub(r' {2,}', ' ', text)
text = re.sub(r'\n{3,}', '\n\n', text)

print(f"  After OCR fixes")

# ── Pass 4: Normalize diocese headers ──
def norm_diocese_header(line):
    """Standardize diocese section headers."""
    m = re.match(r'^(ARCHDIOCESE|DIOCESE)\s+OF\s+(.+)$', line, re.I)
    if m:
        rank = m.group(1).upper()
        name = m.group(2).strip().rstrip('.')
        # Clean OCR junk
        name = re.sub(r'\s+\d+$', '', name)
        name = re.sub(r'[\.\:\;\|\}\~\{\*\-]+$', '', name)
        return f"{rank} OF {name}"
    return line

lines = text.split('\n')
for i, line in enumerate(lines):
    lines[i] = norm_diocese_header(line)
text = '\n'.join(lines)

# ── Save ──
OUTPUT.write_text(text, encoding="utf-8")
print(f"\nOutput: {len(text):,} chars, {len(text.splitlines()):,} lines")
print(f"Saved to: {OUTPUT}")

# Show a sample
sample = '\n'.join(text.split('\n')[:60])
print(f"\nFirst 60 lines:\n{sample}")
