"""Rewrite the IA city directory scraper with a robust, block-based parser."""
import re, sys

text = open('E:/grid/data/directories/sample_gastonia_1976.txt', encoding='utf-8', errors='ignore').read()

# ── Extract churches section ──────────────────────────────────────────
m = re.search(r'CHURCHES\s+AND\s+SYNAGOGUES', text, re.IGNORECASE)
if not m:
    print('No section found')
    sys.exit()

raw = text[m.start():m.start() + 50000]

# ── Block-based parser ────────────────────────────────────────────────
# Split into blocks (separated by blank lines), then join each block
blocks = []
current = []
for line in raw.split('\n'):
    s = line.strip()
    if not s:
        if current:
            blocks.append(' '.join(current))
            current = []
        continue
    # Skip headers, page numbers, artifacts
    if re.match(r'^CHURCHES?\s+(AND\s+)?(SYNAGOGUES|CONTD|CIVIC)', s, re.IGNORECASE):
        continue
    if re.match(r'^\d{1,4}$', s):  # Page numbers
        continue
    if re.match(r'^[IVX]+$', s):  # Roman numerals
        continue
    if s in ('INTRODUCTION', 'GASTONIA', 'CITY DIRECTORY', 'INDEX TO ADVERTISERS'):
        continue
    current.append(s)

if current:
    blocks.append(' '.join(current))

# ── Filter blocks: keep only those that look like church entries ─────
CHURCH_WORDS = re.compile(
    r'\b(?:church|chapel|temple|synagogue|mosque|tabernacle|ministry|'
    r'fellowship|worship|assembly|congregation|cathedral|parish|'
    r'mission|sanctuary|presbyterian|methodist|baptist|lutheran|'
    r'episcopal|catholic|pentecostal|holiness|nazarene|adventist|'
    r'apostolic|gospel|calvary|bethel|bethlehem|zion|shiloh|'
    r'ebenezer|emmanuel|trinity|grace|faith|hope|love|peace|'
    r'first|redeemer|savior|christian|jesu|jesus|god\b|'
    r'mormon|latter.day|jehovah|house of|hbcu|interdenominational|'
    r'wesleyan|freewill|foursquare|covenant|full gospel)\b',
    re.IGNORECASE
)

church_blocks = []
for block in blocks:
    # Skip blocks that are too short or look like ads
    if len(block) < 10:
        continue
    if re.search(r'\b(?:DRUG|WRECKER|AUTO|REPAIR|WELL|BORING|PUMP|SALES|RENTAL|'
                 r'DELIVER|TELS?\.|INSURANCE|PLUMBING|ELECTRIC|HEATING|'
                 r'CLEANER|TAVERN|RESTAURANT|MOTEL|HOTEL|FLORIST)\b',
                 block, re.IGNORECASE):
        continue
    if CHURCH_WORDS.search(block):
        church_blocks.append(block)

print(f'{len(church_blocks)} church blocks out of {len(blocks)} total\n')

# ── Parse each block into name + address ──────────────────────────────
ADDR_PAT = re.compile(
    r'(.*?)(\d+\s+(?:[NSEW]\s+)?[A-Z][a-z]+(?:\s+(?:St|Av|Ave|Rd|Dr|Blvd|Ln|Way|'
    r'Cir|Ct|Pl|Hwy|Pkwy|Trl|Ter|Run|Row|Al|Aly|Cres|Plz|Xing|Cv|Bnd|La))\.?)'
)

for block in church_blocks[:35]:
    # Normalize whitespace
    block = re.sub(r'\s+', ' ', block).strip()
    
    # Fix common OCR artifacts
    block = block.replace('’', "'")
    
    m = ADDR_PAT.search(block)
    if m:
        name = m.group(1).strip().rstrip(',').rstrip('.')
        addr = m.group(2).strip()
        rest = block[m.end():].strip()
        if rest:
            addr += ' ' + rest
        addr = re.sub(r'\s+', ' ', addr).strip()
        # Clean: remove parenthetical codes like (D), (L), (R), (28052)
        addr = re.sub(r'\s*\([A-Z0-9\s,]+\)\s*', ' ', addr).strip()
    else:
        name = block
        addr = ''
    
    print(f'  {name}')
    print(f'    → {addr}')
    print()
