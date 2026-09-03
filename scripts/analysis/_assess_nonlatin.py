"""Assess non-Latin script names in churches.db for translation."""
import sqlite3, re, collections

db = sqlite3.connect(r'E:\grid\churches.db')

# Regex to detect if a string contains any non-Latin script characters
# Latin: U+0000–U+024F (basic + extended), U+1E00–U+1EFF (Latin Extended Additional)
# We'll check for characters outside those ranges in common non-Latin scripts
NON_LATIN_RE = re.compile(
    '[' 
    '\u0370-\u03FF'   # Greek
    '\u0400-\u04FF'   # Cyrillic
    '\u0500-\u052F'   # Cyrillic Supplement
    '\u0530-\u058F'   # Armenian
    '\u0590-\u05FF'   # Hebrew
    '\u0600-\u06FF'   # Arabic
    '\u0700-\u074F'   # Syriac
    '\u0750-\u077F'   # Arabic Supplement
    '\u0780-\u07BF'   # Thaana
    '\u0900-\u097F'   # Devanagari
    '\u0980-\u09FF'   # Bengali
    '\u0A00-\u0A7F'   # Gurmukhi
    '\u0A80-\u0AFF'   # Gujarati
    '\u0B00-\u0B7F'   # Oriya
    '\u0B80-\u0BFF'   # Tamil
    '\u0C00-\u0C7F'   # Telugu
    '\u0C80-\u0CFF'   # Kannada
    '\u0D00-\u0D7F'   # Malayalam
    '\u0D80-\u0DFF'   # Sinhala
    '\u0E00-\u0E7F'   # Thai
    '\u0E80-\u0EFF'   # Lao
    '\u0F00-\u0FFF'   # Tibetan
    '\u1000-\u109F'   # Myanmar
    '\u1100-\u11FF'   # Hangul Jamo
    '\u1200-\u137F'   # Ethiopic
    '\u1780-\u17FF'   # Khmer
    '\u1A00-\u1A1F'   # Buginese
    '\u1B00-\u1B7F'   # Balinese
    '\u1C00-\u1C4F'   # Lepcha
    '\u1DC0-\u1DFF'   # Combining Diacritical Marks Supplement
    '\u2D30-\u2D7F'   # Tifinagh
    '\u2E80-\u2EFF'   # CJK Radicals Supplement
    '\u2F00-\u2FDF'   # Kangxi Radicals
    '\u2FF0-\u2FFF'   # Ideographic Description Characters
    '\u3040-\u309F'   # Hiragana
    '\u30A0-\u30FF'   # Katakana
    '\u3100-\u312F'   # Bopomofo
    '\u3130-\u318F'   # Hangul Compatibility Jamo
    '\u3190-\u319F'   # Kanbun
    '\u31C0-\u31EF'   # CJK Strokes
    '\u31F0-\u31FF'   # Katakana Phonetic Extensions
    '\u3200-\u32FF'   # Enclosed CJK Letters and Months
    '\u3300-\u33FF'   # CJK Compatibility
    '\u3400-\u4DBF'   # CJK Unified Ideographs Extension A
    '\u4E00-\u9FFF'   # CJK Unified Ideographs
    '\uA000-\uA48F'   # Yi
    '\uA490-\uA4CF'   # Yi Radicals
    '\uA4D0-\uA4FF'   # Lisu
    '\uA500-\uA63F'   # Vai
    '\uA640-\uA69F'   # Cyrillic Extended-B
    '\uA700-\uA71F'   # Modifier Tone Letters (mostly latin context)
    '\uA800-\uA82F'   # Syloti Nagri
    '\uA840-\uA87F'   # Phags-pa
    '\uA880-\uA8DF'   # Saurashtra
    '\uA8E0-\uA8FF'   # Devanagari Extended
    '\uA900-\uA92F'   # Kayah Li
    '\uA930-\uA95F'   # Rejang
    '\uAA00-\uAA5F'   # Cham
    '\uAC00-\uD7AF'   # Hangul Syllables
    '\uF900-\uFAFF'   # CJK Compatibility Ideographs
    '\uFB00-\uFB4F'   # Alphabetic Presentation Forms (Latin+Hebrew)
    '\uFB50-\uFDFF'   # Arabic Presentation Forms-A
    '\uFE70-\uFEFF'   # Arabic Presentation Forms-B
    '\uFF00-\uFFEF'   # Fullwidth/Halfwidth forms (includes fullwidth Latin)
    '\U00010000-\U0001007F'  # Linear B Syllabary
    '\U00010080-\U000100FF'  # Linear B Ideograms
    '\U00010100-\U0001013F'  # Aegean Numbers
    '\U00010300-\U0001032F'  # Old Italic
    '\U00010330-\U0001034F'  # Gothic
    '\U00010380-\U0001039F'  # Ugaritic
    '\U00010400-\U0001044F'  # Deseret
    '\U00010450-\U0001047F'  # Shavian
    '\U00010480-\U000104AF'  # Osmanya
    '\U00010800-\U0001083F'  # Cypriot Syllabary
    '\U00010900-\U0001091F'  # Phoenician
    '\U00010A00-\U00010A5F'  # Kharoshthi
    '\U00012000-\U000123FF'  # Cuneiform
    '\U00012400-\U0001247F'  # Cuneiform Numbers
    '\U0001D000-\U0001D0FF'  # Byzantine Musical Symbols
    '\U0001D100-\U0001D1FF'  # Musical Symbols
    '\U0001D200-\U0001D24F'  # Ancient Greek Musical Notation
    '\U0001D300-\U0001D35F'  # Tai Xuan Jing
    '\U0001D360-\U0001D37F'  # Counting Rod Numerals
    '\U0001F000-\U0001F02F'  # Mahjong
    '\U0001F030-\U0001F09F'  # Domino Tiles
    '\U00020000-\U0002A6DF'  # CJK Unified Ideographs Extension B
    '\U0002F800-\U0002FA1F'  # CJK Compatibility Ideographs Supplement
    ']'
)

# Step 1: Count total and by country
total = 0
c = db.execute("SELECT COUNT(*) FROM churches")
total = c.fetchone()[0]

# Step 2: Find non-Latin names, gather stats
c = db.execute("""
    SELECT name, country, source,
           CASE WHEN name_original IS NOT NULL AND name_original != '' THEN 1 ELSE 0 END as has_original
    FROM churches
    WHERE name IS NOT NULL
""")

script_counts = collections.Counter()
country_counts = collections.Counter()
source_counts = collections.Counter()
with_original = 0
without_original = 0
samples_by_script = collections.defaultdict(list)

# Rough script detection functions
def detect_scripts(text):
    """Return set of script names detected in text."""
    scripts = set()
    for ch in text:
        cp = ord(ch)
        if 0x0370 <= cp <= 0x03FF:
            scripts.add('Greek')
        elif 0x0400 <= cp <= 0x052F or 0xA640 <= cp <= 0xA69F:
            scripts.add('Cyrillic')
        elif 0x0530 <= cp <= 0x058F:
            scripts.add('Armenian')
        elif 0x0590 <= cp <= 0x05FF or 0xFB00 <= cp <= 0xFB4F:
            scripts.add('Hebrew')
        elif 0x0600 <= cp <= 0x06FF or 0x0750 <= cp <= 0x077F or 0xFB50 <= cp <= 0xFDFF or 0xFE70 <= cp <= 0xFEFF:
            scripts.add('Arabic')
        elif 0x0900 <= cp <= 0x097F or 0xA8E0 <= cp <= 0xA8FF:
            scripts.add('Devanagari')
        elif 0x0980 <= cp <= 0x09FF:
            scripts.add('Bengali')
        elif 0x0B80 <= cp <= 0x0BFF:
            scripts.add('Tamil')
        elif 0x0C00 <= cp <= 0x0C7F:
            scripts.add('Telugu')
        elif 0x0D00 <= cp <= 0x0D7F:
            scripts.add('Malayalam')
        elif 0x0E00 <= cp <= 0x0E7F:
            scripts.add('Thai')
        elif 0x0F00 <= cp <= 0x0FFF:
            scripts.add('Tibetan')
        elif 0x1100 <= cp <= 0x11FF or 0x3130 <= cp <= 0x318F or 0xAC00 <= cp <= 0xD7AF:
            scripts.add('Korean')
        elif 0x3040 <= cp <= 0x309F:
            scripts.add('Hiragana')
        elif 0x30A0 <= cp <= 0x30FF:
            scripts.add('Katakana')
        elif 0x3400 <= cp <= 0x4DBF or 0x4E00 <= cp <= 0x9FFF or 0xF900 <= cp <= 0xFAFF or 0x2E80 <= cp <= 0x2EFF or 0x2F00 <= cp <= 0x2FDF or 0x3190 <= cp <= 0x319F or 0x31C0 <= cp <= 0x31EF:
            scripts.add('Chinese')
        elif 0x1200 <= cp <= 0x137F:
            scripts.add('Ethiopic')
        elif 0x1000 <= cp <= 0x109F:
            scripts.add('Myanmar')
        elif 0x1780 <= cp <= 0x17FF:
            scripts.add('Khmer')
        elif 0x0E80 <= cp <= 0x0EFF:
            scripts.add('Lao')
        elif 0x0A00 <= cp <= 0x0A7F:
            scripts.add('Gurmukhi')
        elif 0x0A80 <= cp <= 0x0AFF:
            scripts.add('Gujarati')
        elif 0x0D80 <= cp <= 0x0DFF:
            scripts.add('Sinhala')
        elif 0x0700 <= cp <= 0x074F:
            scripts.add('Syriac')
    return scripts

row_count = 0
for row in c:
    name = row[0] or ''
    if NON_LATIN_RE.search(name):
        row_count += 1
        scripts = detect_scripts(name)
        script_str = '+'.join(sorted(scripts)) if scripts else 'other'
        script_counts[script_str] += 1
        country_counts[row[1] or ''] += 1
        source_counts[row[2] or ''] += 1
        if row[3]:
            with_original += 1
        else:
            without_original += 1
        if len(samples_by_script[script_str]) < 5:
            samples_by_script[script_str].append(name[:80])

    if row_count % 200000 == 0 and row_count > 0:
        print(f"  Scanned {row_count}...")

print(f"==========================================")
print(f"Total churches: {total:,}")
print(f"Non-Latin script names: {row_count:,}")
print(f"  With name_original already: {with_original:,}")
print(f"  Without name_original: {without_original:,}")
print(f"==========================================")

print(f"\n--- By script ---")
for script, count in script_counts.most_common():
    print(f"  {script:30s} {count:>8,}")

print(f"\n--- By country (top 30) ---")
for country, count in country_counts.most_common(30):
    print(f"  {country:30s} {count:>8,}")

print(f"\n--- By source (top 20) ---")
for source, count in source_counts.most_common(20):
    print(f"  {source:30s} {count:>8,}")

print(f"\n--- Sample names by script ---")
for script in sorted(samples_by_script.keys()):
    print(f"\n  [{script}] ({script_counts[script]:,} records)")
    for s in samples_by_script[script][:5]:
        print(f"    {s}")

db.close()
