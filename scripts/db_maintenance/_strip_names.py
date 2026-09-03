"""Strip non-Latin text from mixed-script church names.
Strategy: For records with both Latin and non-Latin characters,
extract the Latin portion as the 'name', save the original to 'name_original'.
"""
import sqlite3, re, time, sys

DB_PATH = r'E:\grid\churches.db'
BATCH_SIZE = 5000

# Latin chars we keep: A-Z, a-z, accented Latin, digits, basic punctuation
# Non-Latin ranges to REMOVE
NON_LATIN_RE = re.compile(
    '[' 
    '\u0300-\u036F'   # Combining diacritical marks (keep accents ON latin chars, but these standalone)
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
    '\u2D30-\u2D7F'   # Tifinagh
    '\u2E80-\u2EFF'   # CJK Radicals Supplement
    '\u2F00-\u2FDF'   # Kangxi Radicals
    '\u2FF0-\u2FFF'   # Ideographic Description Characters
    '\u3040-\u309F'   # Hiragana
    '\u30A0-\u30FF'   # Katakana
    '\u3100-\u312F'   # Bopomofo
    '\u3130-\u318F'   # Hangul Compatibility Jamo
    '\u31C0-\u31EF'   # CJK Strokes
    '\u3200-\u32FF'   # Enclosed CJK Letters and Months
    '\u3300-\u33FF'   # CJK Compatibility
    '\u3400-\u4DBF'   # CJK Unified Ideographs Extension A
    '\u4E00-\u9FFF'   # CJK Unified Ideographs
    '\uA000-\uA48F'   # Yi
    '\uA490-\uA4CF'   # Yi Radicals
    '\uA4D0-\uA4FF'   # Lisu
    '\uA500-\uA63F'   # Vai
    '\uA640-\uA69F'   # Cyrillic Extended-B
    '\uA800-\uA82F'   # Syloti Nagri
    '\uA840-\uA87F'   # Phags-pa
    '\uA880-\uA8DF'   # Saurashtra
    '\uA8E0-\uA8FF'   # Devanagari Extended
    '\uA900-\uA92F'   # Kayah Li
    '\uA930-\uA95F'   # Rejang
    '\uAA00-\uAA5F'   # Cham
    '\uAC00-\uD7AF'   # Hangul Syllables
    '\uF900-\uFAFF'   # CJK Compatibility Ideographs
    '\uFB00-\uFB4F'   # Alphabetic Presentation Forms (Latin+Hebrew ligatures)
    '\uFB50-\uFDFF'   # Arabic Presentation Forms-A
    '\uFE70-\uFEFF'   # Arabic Presentation Forms-B
    '\U00010000-\U0001007F'  # Linear B
    '\U00010080-\U000100FF'
    '\U00010300-\U0001032F'  # Old Italic
    '\U00010330-\U0001034F'  # Gothic
    '\U00010400-\U0001044F'  # Deseret
    '\U00010450-\U0001047F'  # Shavian
    '\U00010480-\U000104AF'  # Osmanya
    '\U00010800-\U0001083F'  # Cypriot
    '\U00012000-\U000123FF'  # Cuneiform
    '\U0001D000-\U0001D0FF'  # Byzantine Musical Symbols
    '\U0001D100-\U0001D1FF'  # Musical Symbols
    '\U00020000-\U0002A6DF'  # CJK Extension B
    '\U0002F800-\U0002FA1F'  # CJK Supplement
    ']'
)

def clean_name(name):
    """Strip non-Latin chars and clean up."""
    if not name:
        return None
    # Step 1: Remove non-Latin characters
    stripped = NON_LATIN_RE.sub('', name)
    # Step 2: Remove empty or whitespace-only parentheses/brackets
    stripped = re.sub(r'\(\s*\)', '', stripped)
    stripped = re.sub(r'\[\s*\]', '', stripped)
    stripped = re.sub(r'\{\s*\}', '', stripped)
    # Step 3: Clean up patterns like ", ," (comma chains from stripped content)
    stripped = re.sub(r',\s*,(\s*,)*', ', ', stripped)
    stripped = re.sub(r';\s*;(\s*;)*', '; ', stripped)
    # Step 4: Clean leading/trailing noise
    stripped = stripped.strip('|').strip('-').strip(',').strip(';').strip('/').strip('\\').strip('"').strip("'").strip('.')
    # Step 5: Collapse multiple spaces
    stripped = re.sub(r'\s+', ' ', stripped).strip()
    # Step 6: Remove trailing standalone punctuation
    stripped = re.sub(r'\s+[,\-;/|:"\'\\]\s*$', '', stripped)
    stripped = re.sub(r'^\s*[,\-;/|:"\'\\]\s+', '', stripped)
    # Step 7: Clean trailing " -" patterns
    stripped = re.sub(r'\s+-\s*$', '', stripped)
    stripped = re.sub(r'^\s*-\s+', '', stripped)
    return stripped

def is_acceptable(stripped):
    """A stripped name is acceptable if it has meaningful English content."""
    if not stripped or len(stripped) < 8:
        return False
    # Must have at least one ASCII letter
    if not re.search(r'[A-Za-z]', stripped):
        return False
    # Must have at least 2 words or one long word
    if len(stripped.split()) < 2 and len(stripped) < 12:
        return False
    # Reject if mostly parenthetical (e.g. "(KCCNJ) (4)")
    # Count content outside parens vs inside
    outside = re.sub(r'\([^)]*\)', '', stripped).strip()
    if len(outside) < 3:
        return False
    return True

def main():
    db = sqlite3.connect(DB_PATH)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA journal_mode=WAL")
    
    # Find all mixed-script records that DON'T already have name_original set
    c = db.execute("""
        SELECT rowid, name, name_original
        FROM churches
        WHERE name IS NOT NULL
          AND (name_original IS NULL OR name_original = '')
    """)
    
    candidates = []
    for row in c:
        name = row['name']
        # Check if it has non-Latin characters
        if NON_LATIN_RE.search(name):
            stripped = clean_name(name)
            if is_acceptable(stripped):
                # Only strip if the stripped version is actually different
                if stripped != name:
                    candidates.append((row['rowid'], name, stripped))
    
    print(f"Found {len(candidates):,} candidates for stripping")
    
    if not candidates:
        print("Nothing to do!")
        db.close()
        return
    
    # Show some samples
    print(f"\n--- First 20 samples ---")
    for i, (rid, orig, stripped) in enumerate(candidates[:20]):
        print(f"  [{i+1}] {stripped[:70]}")
        print(f"       orig: {orig[:70]}")
        print()
    
    print(f"\nTotal: {len(candidates):,} records to update.")
    
    # PROCEED — user said "do the easy strip"
    print("Proceeding with UPDATE...")
    
    import datetime
    started_at = datetime.datetime.now().isoformat()
    
    # Update in batches
    updated = 0
    for i in range(0, len(candidates), BATCH_SIZE):
        batch = candidates[i:i+BATCH_SIZE]
        for rid, orig, stripped in batch:
            db.execute("""
                UPDATE churches 
                SET name = ?, name_original = ?
                WHERE rowid = ?
            """, (stripped, orig, rid))
        db.commit()
        updated += len(batch)
        print(f"  Updated {updated:,}/{len(candidates):,}...")
    
    # Log provenance after successful completion
    completed_at = datetime.datetime.now().isoformat()
    cur = db.execute("""
        INSERT INTO provenance_log 
        (source, script_name, started_at, completed_at, churches_updated, records_attempted, records_matched, fields_populated, status, notes)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'completed', ?)
    """, (
        'script',
        '_strip_names.py',
        started_at,
        completed_at,
        updated,
        len(candidates),
        len(candidates),
        'name, name_original',
        f'Stripped non-Latin text from mixed-script church names, saved originals to name_original'
    ))
    prov_id = cur.lastrowid
    db.commit()
    
    print(f"\n✅ Done! Updated {updated:,} records.")
    print(f"Provenance logged (id={prov_id}).")
    db.close()

if __name__ == '__main__':
    main()

if __name__ == '__main__':
    main()
