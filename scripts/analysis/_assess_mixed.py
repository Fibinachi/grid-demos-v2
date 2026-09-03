"""Assess mixed vs pure non-Latin names in churches.db."""
import sqlite3, re

db = sqlite3.connect(r'E:\grid\churches.db')

LATIN_RE = re.compile(r'[A-Za-z0-9\s\'\-\.\,\&\(\)\[\]]')
NON_LATIN_RE = re.compile(
    '[' 
    '\u0370-\u03FF\u0400-\u04FF\u0500-\u052F\u0530-\u058F'
    '\u0590-\u05FF\u0600-\u06FF\u0700-\u074F\u0750-\u077F'
    '\u0900-\u097F\u0980-\u09FF\u0A00-\u0A7F\u0A80-\u0AFF'
    '\u0B00-\u0B7F\u0B80-\u0BFF\u0C00-\u0C7F\u0C80-\u0CFF'
    '\u0D00-\u0D7F\u0D80-\u0DFF\u0E00-\u0E7F\u0E80-\u0EFF'
    '\u0F00-\u0FFF\u1000-\u109F\u1100-\u11FF\u1200-\u137F'
    '\u1780-\u17FF\u1A00-\u1A1F\u1B00-\u1B7F\u2D30-\u2D7F'
    '\u3040-\u309F\u30A0-\u30FF\u3100-\u312F\u3130-\u318F'
    '\u31C0-\u31EF\u3200-\u32FF\u3300-\u33FF'
    '\u3400-\u4DBF\u4E00-\u9FFF\uA000-\uA48F'
    '\uA4D0-\uA4FF\uA500-\uA63F\uA640-\uA69F'
    '\uA800-\uA82F\uA840-\uA87F\uA880-\uA8DF\uA8E0-\uA8FF'
    '\uA900-\uA92F\uA930-\uA95F\uAA00-\uAA5F'
    '\uAC00-\uD7AF\uF900-\uFAFF\uFB00-\uFB4F'
    '\uFB50-\uFDFF\uFE70-\uFEFF'
    '\U00010000-\U0001007F\U00010080-\U000100FF'
    '\U00010300-\U0001032F\U00010330-\U0001034F'
    '\U00010400-\U0001044F\U00010450-\U0001047F'
    '\U00010480-\U000104AF'
    '\U00012000-\U000123FF'
    '\U0001D000-\U0001D0FF\U0001D100-\U0001D1FF'
    '\U00020000-\U0002A6DF\U0002F800-\U0002FA1F'
    ']'
)

# Scan for mixed vs pure non-Latin
c = db.execute("""
    SELECT name, country, source
    FROM churches
    WHERE name IS NOT NULL
""")

total = 0
mixed = 0  # has both Latin and non-Latin
pure_nonlatin = 0  # entirely non-Latin
pure_latin = 0  # entirely Latin (should be most)
nonlatin_short = 0  # non-Latin under 20 chars (likely corrupt/garbage)
mixed_arabic = 0
mixed_cyrillic = 0
mixed_chinese = 0
mixed_thai = 0
mixed_other = 0
pure_by_script = {}

def guess_script(text):
    """Return primary script for a pure non-Latin text."""
    for ch in text:
        cp = ord(ch)
        if 0x0600 <= cp <= 0x06FF or 0x0750 <= cp <= 0x077F or 0xFB50 <= cp <= 0xFDFF or 0xFE70 <= cp <= 0xFEFF:
            return 'Arabic'
        elif 0x0400 <= cp <= 0x052F or 0xA640 <= cp <= 0xA69F:
            return 'Cyrillic'
        elif 0x4E00 <= cp <= 0x9FFF or 0x3400 <= cp <= 0x4DBF or 0xF900 <= cp <= 0xFAFF:
            return 'Chinese'
        elif 0x0E00 <= cp <= 0x0E7F:
            return 'Thai'
        elif 0xAC00 <= cp <= 0xD7AF or 0x1100 <= cp <= 0x11FF:
            return 'Korean'
        elif 0x0370 <= cp <= 0x03FF:
            return 'Greek'
        elif 0x1000 <= cp <= 0x109F:
            return 'Myanmar'
        elif 0x0900 <= cp <= 0x097F or 0xA8E0 <= cp <= 0xA8FF:
            return 'Devanagari'
        elif 0x0590 <= cp <= 0x05FF:
            return 'Hebrew'
        elif 0x0530 <= cp <= 0x058F:
            return 'Armenian'
        elif 0x0980 <= cp <= 0x09FF:
            return 'Bengali'
        elif 0x1780 <= cp <= 0x17FF:
            return 'Khmer'
        elif 0x0B80 <= cp <= 0x0BFF:
            return 'Tamil'
        elif 0x3040 <= cp <= 0x309F or 0x30A0 <= cp <= 0x30FF:
            return 'Japanese'
        elif 0x0E80 <= cp <= 0x0EFF:
            return 'Lao'
        elif 0x1200 <= cp <= 0x137F:
            return 'Ethiopic'
        elif 0x0D80 <= cp <= 0x0DFF:
            return 'Sinhala'
        elif 0x0C00 <= cp <= 0x0C7F:
            return 'Telugu'
        elif 0x0A80 <= cp <= 0x0AFF:
            return 'Gujarati'
        elif 0x0A00 <= cp <= 0x0A7F:
            return 'Gurmukhi'
        elif 0x0D00 <= cp <= 0x0D7F:
            return 'Malayalam'
        elif 0x0700 <= cp <= 0x074F:
            return 'Syriac'
        elif 0x0F00 <= cp <= 0x0FFF:
            return 'Tibetan'
    return 'other'

for row in c:
    name = row[0] or ''
    has_latin = bool(LATIN_RE.search(name))
    has_nonlatin = bool(NON_LATIN_RE.search(name))
    
    if not has_nonlatin:
        pure_latin += 1
    else:
        total += 1
        if has_latin:
            mixed += 1
            # Which script in the mix
            if re.search(r'[\u0600-\u06FF\u0750-\u077F\uFB50-\uFDFF\uFE70-\uFEFF]', name):
                mixed_arabic += 1
            elif re.search(r'[\u0400-\u052F\uA640-\uA69F]', name):
                mixed_cyrillic += 1
            elif re.search(r'[\u4E00-\u9FFF\u3400-\u4DBF]', name):
                mixed_chinese += 1
            elif re.search(r'[\u0E00-\u0E7F]', name):
                mixed_thai += 1
            else:
                mixed_other += 1
        else:
            pure_nonlatin += 1
            script = guess_script(name)
            if len(name) < 20:
                nonlatin_short += 1
            pure_by_script[script] = pure_by_script.get(script, 0) + 1
    
    if (pure_latin + total) % 300000 == 0:
        print(f"  Scanned {pure_latin + total:,}... ({total:,} non-Latin found)")

print(f"Total records scanned: {pure_latin + total:,}")
print(f"  Pure Latin:     {pure_latin:,}")
print(f"  Mixed:          {mixed:,}")
print(f"    - with Arabic:  {mixed_arabic:,}")
print(f"    - with Cyrillic: {mixed_cyrillic:,}")
print(f"    - with Chinese:  {mixed_chinese:,}")
print(f"    - with Thai:     {mixed_thai:,}")
print(f"    - other mixed:   {mixed_other:,}")
print(f"  Pure non-Latin: {pure_nonlatin:,}  ({nonlatin_short:,} under 20 chars)")
print()
print("--- Pure non-Latin by script ---")
for script, count in sorted(pure_by_script.items(), key=lambda x: -x[1]):
    print(f"  {script:15s} {count:>8,}")

db.close()
