"""Test parser v2 on Gastonia sample - multi-line aware."""
import re, sys

text = open('E:/grid/data/directories/sample_gastonia_1976.txt', encoding='utf-8', errors='ignore').read()

# ── Extract churches section ──────────────────────────────────────────
patterns = [
    r'CHURCHES\s+AND\s+SYNAGOGUES',
    r'CHURCHES?\s+AND\s+CHARACTER\s+BUILDING',
]

section_start = None
for pat in patterns:
    m = re.search(pat, text, re.IGNORECASE)
    if m:
        section_start = m.start()
        break

if not section_start:
    print('No section found')
    sys.exit()

# Grab from first header onward, limit to 30K chars
raw_section = text[section_start:section_start + 30000]
print(f'Section: {len(raw_section):,} chars\n')

# ── Parse entries ────────────────────────────────────────────────────
# Strategy: join multi-line entries, detect new entries by look-ahead

lines = raw_section.split('\n')

# Skip headers, page numbers, blank lines
clean_lines = []
for line in lines:
    s = line.strip()
    if not s:
        clean_lines.append('')  # Keep blank lines as separators
        continue
    if re.match(r'^CHURCHES?\s+(AND\s+)?(SYNAGOGUES|CONTD|CIVIC)', s, re.IGNORECASE):
        continue
    if re.match(r'^\d{1,3}$', s):  # Page numbers
        continue
    if re.match(r'^[IVX]+$', s):  # Roman numerals
        continue
    if s in ('INTRODUCTION', 'GASTONIA', 'CITY DIRECTORY', 'INDEX TO ADVERTISERS'):
        continue
    clean_lines.append(s)

# Now reassemble multi-line entries
# A NEW entry starts when:
#   - Previous entry had a complete address (number + street)
#   - Line looks like a new organization name (starts with capital, has church-like words)
# An entry CONTINUES when:
#   - Line starts with number, N/S/E/W, or street suffix
#   - Line is part of the organization name

entries = []
current_lines = []

STREET_SUFFIXES = {'St', 'Av', 'Ave', 'Rd', 'Dr', 'Blvd', 'Blvd', 'Ln', 'Way',
                   'Cir', 'Ct', 'Pl', 'Hwy', 'Pkwy', 'Blvd', 'Trl', 'Pk', 'Cir',
                   'Ter', 'Run', 'Row', 'Al', 'Aly', 'Cres', 'Pk', 'Dr', 'Pl',
                   'Plz', 'Xing', 'Cv', 'Bnd', 'Frk', 'Frwy', 'Expy', 'Jct'}

def looks_like_address(s):
    """Check if a line looks like it's an address continuation."""
    s = s.strip()
    # Starts with number or directional
    if re.match(r'^\d', s):
        return True
    if re.match(r'^[NSEW]\s', s):
        return True
    # Is just a street suffix
    if s in STREET_SUFFIXES:
        return True
    # Is a continuation of a street name
    if re.match(r'^(St|Av|Rd|Dr|Ln|Way|Cir|Ct|Pl|Blvd)', s):
        return True
    # Contains "Tel" or "PO Box"
    if re.match(r'^(?:Tel|PO|P\.O\.)\s', s, re.IGNORECASE):
        return True
    # Is a continuation word (like a street name part)
    if re.match(r'^[A-Z][a-z]+(?: St| Rd| Dr| Av| Blvd| Ln| Way| Cir| Ct| Pl)?$', s):
        # Single word - could be a street name continuation OR standalone
        return False  # Don't assume
    return False

def looks_like_new_church(s):
    """Check if a line looks like the start of a new church entry."""
    # Must start with capital letter
    if not s or not s[0].isupper():
        return False
    # Church keyword check
    church_words = ['church', 'chapel', 'temple', 'synagogue', 'mosque', 'tabernacle',
                    'ministry', 'fellowship', 'worship', 'assembly', 'congregation',
                    'cathedral', 'parish', 'mission', 'sanctuary', 'presbyterian',
                    'methodist', 'baptist', 'lutheran', 'episcopal', 'catholic',
                    'pentecostal', 'holiness', 'nazarene', 'adventist', 'apostolic',
                    'gospel', 'calvary', 'bethel', 'bethlehem', 'zion', 'shiloh',
                    'ebenezer', 'emmanuel', 'trinity', 'grace', 'faith', 'hope',
                    'love', 'peace', 'first', 'second', 'third', 'st\\.', 'saint',
                    'mount', 'new hope', 'new life', 'christ', 'jesus', 'god',
                    'redeemer', 'savior', 'mormon', 'latter.day', 'jehovah',
                    'house of', 'church of', 'temple of']
    s_lower = s.lower()
    for kw in church_words:
        if kw in s_lower:
            return True
    return False

for line in clean_lines:
    if not line:
        # Blank line - end current entry
        if current_lines:
            entries.append(' '.join(current_lines))
            current_lines = []
        continue
    
    if not current_lines:
        current_lines.append(line)
    elif looks_like_address(line):
        current_lines.append(line)
    elif looks_like_new_church(line):
        # Start new entry
        entries.append(' '.join(current_lines))
        current_lines = [line]
    else:
        # Could be name continuation
        current_lines.append(line)

# Last entry
if current_lines:
    entries.append(' '.join(current_lines))

print(f'Assembled {len(entries)} entries\n')

# ── Parse each assembled entry into name + address ───────────────────
for entry in entries[:30]:
    # Clean up multiple spaces
    entry = re.sub(r'\s+', ' ', entry).strip()
    
    # Try to split at address (digits followed by street-like word)
    m = re.search(r'(.*?)(\d+\s+(?:[NSEW]\s+)?[A-Z][a-z]+(?:\s+(?:St|Av|Ave|Rd|Dr|Blvd|Ln|Way|Cir|Ct|Pl|Hwy|Pkwy|Trl|Ter|Run|Row|Al|Aly|Cres|Pl|Plz|Xing|Cv|Bnd))\.?)', entry)
    if m:
        name = m.group(1).strip().rstrip(',').rstrip('.')
        addr = m.group(2).strip()
        # Grab rest of address after match
        rest = entry[m.end():].strip()
        if rest:
            addr += ' ' + rest
    else:
        name = entry
        addr = ''
    
    print(f'  {name}')
    print(f'    → {addr}')
    print()
