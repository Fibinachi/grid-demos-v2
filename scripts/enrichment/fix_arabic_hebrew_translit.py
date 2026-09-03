"""Fix Arabic and Hebrew transliteration - the existing script's NFKD fallback doesn't work for these scripts.
Uses proper character mapping tables."""
import sqlite3
import re

conn = sqlite3.connect(r"E:\grid\churches.db")
c = conn.cursor()

# ─── Hebrew transliteration table ───────────────────────────────────────
HE_MAP = str.maketrans({
    '\u05D0': '',     # א aleph
    '\u05D1': 'b',    # ב bet
    '\u05D2': 'g',    # ג gimel
    '\u05D3': 'd',    # ד dalet
    '\u05D4': 'h',    # ה he
    '\u05D5': 'v',    # ו vav
    '\u05D6': 'z',    # ז zayin
    '\u05D7': 'kh',   # ח khet
    '\u05D8': 't',    # ט tet
    '\u05D9': 'y',    # י yod
    '\u05DA': 'kh',   # ך final kaf
    '\u05DB': 'k',    # כ kaf
    '\u05DC': 'l',    # ל lamed
    '\u05DD': 'm',    # ם final mem
    '\u05DE': 'm',    # מ mem
    '\u05DF': 'n',    # ן final nun
    '\u05E0': 'n',    # נ nun
    '\u05E1': 's',    # ס samekh
    '\u05E2': '',     # ע ayin
    '\u05E3': 'f',    # ף final pe
    '\u05E4': 'p',    # פ pe
    '\u05E5': 'ts',   # ץ final tsadi
    '\u05E6': 'ts',   # צ tsadi
    '\u05E7': 'k',    # ק kof
    '\u05E8': 'r',    # ר resh
    '\u05E9': 'sh',   # ש shin
    '\u05EA': 't',    # ת tav
    # Niqqud - strip
    '\u05B0': '', '\u05B1': '', '\u05B2': '', '\u05B3': '',
    '\u05B4': '', '\u05B5': '', '\u05B6': '', '\u05B7': '',
    '\u05B8': '', '\u05B9': '', '\u05BA': '', '\u05BB': '',
    '\u05BC': '', '\u05BD': '', '\u05BF': '', '\u05C1': '',
    '\u05C2': '', '\u05C7': '',
    # Geresh
    '\u05F3': "'", '\u05F4': '"',
})

# ─── Arabic transliteration table ──────────────────────────────────────
AR_MAP = {
    '\u0621': "'", '\u0622': 'a', '\u0623': "'", '\u0624': "'",
    '\u0625': "'", '\u0626': "'", '\u0627': 'a', '\u0628': 'b',
    '\u0629': 'h', '\u062A': 't', '\u062B': 'th', '\u062C': 'j',
    '\u062D': 'h', '\u062E': 'kh', '\u062F': 'd', '\u0630': 'dh',
    '\u0631': 'r', '\u0632': 'z', '\u0633': 's', '\u0634': 'sh',
    '\u0635': 's', '\u0636': 'd', '\u0637': 't', '\u0638': 'z',
    '\u0639': "'", '\u063A': 'gh', '\u0640': '', '\u0641': 'f',
    '\u0642': 'q', '\u0643': 'k', '\u0644': 'l', '\u0645': 'm',
    '\u0646': 'n', '\u0647': 'h', '\u0648': 'w', '\u0649': 'a',
    '\u064A': 'y',
    # Arabic diacritics - strip
    '\u064B': '', '\u064C': '', '\u064D': '', '\u064E': '',
    '\u064F': '', '\u0650': '', '\u0651': '', '\u0652': '',
    '\u0653': '', '\u0670': '',
    # Persian-specific
    '\u067E': 'p', '\u0686': 'ch', '\u0698': 'zh', '\u06AF': 'g',
    '\u06A4': 'v',
    # Urdu-specific
    '\u06C1': 'h', '\u06C2': 'h', '\u06BE': 'h',
    '\u06CC': 'y', '\u06D2': 'e',
}

def translit_hebrew(text):
    """Transliterate Hebrew script to Latin using char mapping."""
    return text.translate(HE_MAP)

def translit_arabic(text):
    """Transliterate Arabic script to Latin using char mapping."""
    result = []
    for ch in text:
        result.append(AR_MAP.get(ch, ch))
    return ''.join(result)

def has_hebrew(text):
    return bool(re.search(r'[\u0590-\u05FF]', text)) if text else False

def has_arabic(text):
    return bool(re.search(r'[\u0600-\u06FF\u0750-\u077F\u08A0-\u08FF]', text)) if text else False

# ─── Step 1: Fix Hebrew transliterations ──────────────────────────────
print("=== Fixing Hebrew transliterations ===")
c.execute("""
    SELECT id, name, name_transliterated
    FROM churches
    WHERE name GLOB '*[א-ת]*'
""")
rows = c.fetchall()
print(f"Found {len(rows)} Hebrew-script records")

CHUNK = 500
heb_fixed = 0
for i in range(0, len(rows), CHUNK):
    chunk = rows[i:i+CHUNK]
    for r in chunk:
        id_, name, current_trans = r
        new_trans = translit_hebrew(name)
        # Clean up: collapse multiple spaces
        new_trans = re.sub(r'\s+', ' ', new_trans).strip()
        if new_trans != (current_trans or ''):
            c.execute("UPDATE churches SET name_transliterated=? WHERE id=?", (new_trans, id_))
            heb_fixed += 1
    conn.commit()
    if (i // CHUNK) % 20 == 0:
        print(f"  Progress: {i+len(chunk):,}/{len(rows):,} ({heb_fixed} fixed)")

print(f"Hebrew fixes: {heb_fixed}")

# ─── Step 2: Fix Arabic transliterations ──────────────────────────────
print("\n=== Fixing Arabic transliterations ===")
# Use unicode range for Arabic
c.execute("""
    SELECT id, name, name_transliterated
    FROM churches
    WHERE (name GLOB '*[ء-ي]*' OR name GLOB '*[ٱ-ۿ]*' OR name GLOB '*[ﭐ-﷿]*')
    AND name NOT GLOB '*[א-ת]*'
""")
rows = c.fetchall()
print(f"Found {len(rows)} Arabic-script records")

ara_fixed = 0
for i in range(0, len(rows), CHUNK):
    chunk = rows[i:i+CHUNK]
    for r in chunk:
        id_, name, current_trans = r
        # Only process if it actually has Arabic chars
        if not has_arabic(name):
            continue
        new_trans = translit_arabic(name)
        new_trans = re.sub(r'\s+', ' ', new_trans).strip()
        if new_trans != (current_trans or ''):
            c.execute("UPDATE churches SET name_transliterated=? WHERE id=?", (new_trans, id_))
            ara_fixed += 1
    conn.commit()
    if (i // CHUNK) % 20 == 0:
        print(f"  Progress: {i+len(chunk):,}/{len(rows):,} ({ara_fixed} fixed)")

print(f"Arabic fixes: {ara_fixed}")

conn.close()
print(f"\nDone! Hebrew: {heb_fixed} | Arabic: {ara_fixed}")
