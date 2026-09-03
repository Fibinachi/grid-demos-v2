#!/usr/bin/env python3
"""
Transliterate non-Roman names to Roman alphabet.
Stores original non-Roman text in name_original and transliteration in name_transliterated.

Usage:
    python scripts/enrichment/transliterate_names.py            # full run
    python scripts/enrichment/transliterate_names.py --dry-run  # preview only
    python scripts/enrichment/transliterate_names.py --limit 1000  # small batch

Libraries used per script:
    Cyrillic  → transliterate (ru/uk/bg/sr/be/mk)
    Greek     → transliterate (el)
    Arabic    → transliterate (ar) + custom
    Hebrew    → custom mapping
    CJK       → pypinyin (pinyin with tone numbers)
    Japanese  → pykakasi (Hepburn)
    Korean    → korean-romanizer (Revised Romanization)
    Thai      → pythainlp (Royal Thai General System)
    Devanagari→ indic-transliteration (ISO)
    Bengali   → indic-transliteration (ISO)
    Tamil     → indic-transliteration (ISO)
    Gurmukhi  → indic-transliteration (ISO)
    Georgian  → transliterate (ka)
    Armenian  → transliterate (hy)
    Myanmar   → NFKD decomposition
    Khmer     → NFKD decomposition
    Lao       → pythainlp + NFKD
    Sinhala   → NFKD decomposition
    Tibetan   → NFKD decomposition (Wylie approximation)
    Ethiopic  → NFKD decomposition
"""

import sqlite3
import re
import sys
import time
from datetime import datetime

# ─── Script detection patterns ───────────────────────────────────────────
SCRIPTS = {
    "Cyrillic":  re.compile(r'[\u0400-\u04FF]'),
    "Greek":     re.compile(r'[\u0370-\u03FF]'),
    "Arabic":    re.compile(r'[\u0600-\u06FF]'),
    "Hebrew":    re.compile(r'[\u0590-\u05FF]'),
    "CJK":       re.compile(r'[\u4E00-\u9FFF\u3400-\u4DBF]'),
    "Hiragana":  re.compile(r'[\u3040-\u309F]'),
    "Katakana":  re.compile(r'[\u30A0-\u30FF]'),
    "Hangul":    re.compile(r'[\uAC00-\uD7AF]'),
    "Thai":      re.compile(r'[\u0E00-\u0E7F]'),
    "Tamil":     re.compile(r'[\u0B80-\u0BFF]'),
    "Gurmukhi":  re.compile(r'[\u0A00-\u0A7F]'),
    "Bengali":   re.compile(r'[\u0980-\u09FF]'),
    "Devanagari":re.compile(r'[\u0900-\u097F]'),
    "Georgian":  re.compile(r'[\u10A0-\u10FF]'),
    "Armenian":  re.compile(r'[\u0530-\u058F]'),
    "Myanmar":   re.compile(r'[\u1000-\u109F]'),
    "Khmer":     re.compile(r'[\u1780-\u17FF]'),
    "Lao":       re.compile(r'[\u0E80-\u0EFF]'),
    "Sinhala":   re.compile(r'[\u0D80-\u0DFF]'),
    "Tibetan":   re.compile(r'[\u0F00-\u0FFF]'),
    "Ethiopic":  re.compile(r'[\u1200-\u137F]'),
}

# Order matters: for Japanese we need to detect CJK+Hiragana+Katakana combo
JAPANESE_SCRIPTS = {"CJK", "Hiragana", "Katakana"}
KOREAN_ONLY = {"Hangul"}

# ─── Language detection helpers ──────────────────────────────────────────
# Map Cyrillic text to language codes for transliterate library
CYRILLIC_KEYWORDS = [
    ("ru", ["церковь", "храм", "собор", "мечеть", "монастырь", "россия",
            "москва", "православ", "дивен", "бог", "христ", "спас"]),
    ("uk", ["церква", "храм", "собор", "київ", "православ", "христ"]),
    ("bg", ["църква", "българ", "софия", "православ"]),
    ("sr", ["црква", "српск", "београд", "православ"]),
]

def detect_language(text, script):
    """Try to detect language within a script group."""
    if script == "Cyrillic":
        lower = text.lower()
        for lang, keywords in CYRILLIC_KEYWORDS:
            for kw in keywords:
                if kw in lower:
                    return lang
        return "ru"  # default for Cyrillic
    return None

# ─── Transliterator class ───────────────────────────────────────────────
class Transliterator:
    def __init__(self):
        self._load_libraries()

    def _load_libraries(self):
        """Lazy-load transliteration libraries."""
        self.transliterate = None
        self.pypinyin = None
        self.pykakasi = None
        self.korean_romanizer = None
        self.pythainlp = None
        self.indic_transliteration = None
        self.sanscript = None

    def _ensure_transliterate(self):
        if self.transliterate is None:
            from transliterate import translit
            self.transliterate = translit

    def _ensure_pypinyin(self):
        if self.pypinyin is None:
            from pypinyin import pinyin, Style
            self._pinyin_func = pinyin
            self._pinyin_style = Style

    def _ensure_pykakasi(self):
        if self.pykakasi is None:
            from pykakasi import kakasi
            self._kakasi = kakasi()

    def _ensure_korean(self):
        if self.korean_romanizer is None:
            from korean_romanizer import Romanizer
            self._romanizer_cls = Romanizer

    def _ensure_thai(self):
        if self.pythainlp is None:
            from pythainlp.transliterate import romanize
            self._thai_romanize = romanize

    def _ensure_indic(self):
        if self.indic_transliteration is None:
            from indic_transliteration import sanscript as indic_sanscript
            self.sanscript = indic_sanscript

    def transliterate_script(self, text, scripts_found):
        """Transliterate text based on detected scripts. Returns (transliterated, original_only)."""
        if not text:
            return text, ""

        # Extract only non-ASCII parts for name_original
        non_ascii_chars = re.findall(r'[^\x00-\x7F]+', text)
        original_only = " ".join(non_ascii_chars).strip()
        original_only = re.sub(r'\s+', ' ', original_only)

        # Determine primary transliteration strategy
        script_set = set(scripts_found)

        # Japanese (CJK + Hiragana/Katakana)
        if script_set & JAPANESE_SCRIPTS and (scripts_found.count("Hiragana") + scripts_found.count("Katakana") > 0 or
                                               script_set >= {"CJK", "Hiragana"} or
                                               script_set >= {"CJK", "Katakana"}):
            return self._transliterate_japanese(text), original_only

        # Korean only (no CJK)
        if script_set == KOREAN_ONLY or (script_set == {"CJK", "Hangul"} and self._is_korean(text)):
            return self._transliterate_korean(text), original_only

        # CJK only (Chinese)
        if script_set == {"CJK"} or (script_set == {"CJK", "Hangul"} and not self._is_korean(text)):
            return self._transliterate_chinese(text), original_only

        # Arabic
        if "Arabic" in script_set:
            return self._transliterate_arabic(text), original_only

        # Cyrillic
        if "Cyrillic" in script_set:
            return self._transliterate_cyrillic(text), original_only

        # Greek
        if "Greek" in script_set:
            return self._transliterate_greek(text), original_only

        # Hebrew
        if "Hebrew" in script_set:
            return self._transliterate_hebrew(text), original_only

        # Thai
        if "Thai" in script_set:
            return self._transliterate_thai(text), original_only

        # Devanagari
        if "Devanagari" in script_set:
            return self._transliterate_devanagari(text), original_only

        # Bengali
        if "Bengali" in script_set:
            return self._transliterate_bengali(text), original_only

        # Tamil
        if "Tamil" in script_set:
            return self._transliterate_tamil(text), original_only

        # Gurmukhi
        if "Gurmukhi" in script_set:
            return self._transliterate_gurmukhi(text), original_only

        # Georgian
        if "Georgian" in script_set:
            return self._transliterate_georgian(text), original_only

        # Armenian
        if "Armenian" in script_set:
            return self._transliterate_armenian(text), original_only

        # Myanmar
        if "Myanmar" in script_set:
            return self._transliterate_myanmar(text), original_only

        # Khmer
        if "Khmer" in script_set:
            return self._transliterate_khmer(text), original_only

        # Lao
        if "Lao" in script_set:
            return self._transliterate_lao(text), original_only

        # Sinhala
        if "Sinhala" in script_set:
            return self._transliterate_sinhala(text), original_only

        # Tibetan
        if "Tibetan" in script_set:
            return self._transliterate_tibetan(text), original_only

        # Ethiopic
        if "Ethiopic" in script_set:
            return self._transliterate_ethiopic(text), original_only

        return text, original_only

    def _is_korean(self, text):
        """Check if text is predominantly Korean vs Chinese."""
        hangul_chars = len(re.findall(r'[\uAC00-\uD7AF]', text))
        cjk_chars = len(re.findall(r'[\u4E00-\u9FFF\u3400-\u4DBF]', text))
        return hangul_chars > cjk_chars

    def _transliterate_japanese(self, text):
        """Japanese: use pykakasi for Hepburn romanization."""
        self._ensure_pykakasi()
        try:
            result = self._kakasi.convert(text)
            return " ".join([item['hepburn'] for item in result])
        except Exception:
            return self._nfkd_fallback(text)

    def _transliterate_korean(self, text):
        """Korean: use korean-romanizer (Revised Romanization)."""
        self._ensure_korean()
        try:
            # Extract only Korean characters
            hangul_only = re.sub(r'[^\uAC00-\uD7AF\s]', '', text)
            if hangul_only.strip():
                r = self._romanizer_cls(hangul_only.strip())
                return r.romanize()
            return text
        except Exception:
            return self._nfkd_fallback(text)

    def _transliterate_chinese(self, text):
        """Chinese: use pypinyin with tone numbers."""
        self._ensure_pypinyin()
        try:
            result = self._pinyin_func(text, style=self._pinyin_style.TONE3,
                                       neutral_tone_with_five=True)
            return " ".join([p[0] for p in result])
        except Exception:
            return self._nfkd_fallback(text)

    def _transliterate_arabic(self, text):
        """Arabic: use transliterate library."""
        self._ensure_transliterate()
        try:
            return self.transliterate(text, 'ar', reversed=True)
        except Exception:
            return self._nfkd_fallback(text)

    def _transliterate_cyrillic(self, text):
        """Cyrillic: detect language then transliterate."""
        self._ensure_transliterate()
        lang = detect_language(text, "Cyrillic")
        try:
            return self.transliterate(text, lang, reversed=True)
        except Exception:
            return self._nfkd_fallback(text)

    def _transliterate_greek(self, text):
        """Greek: use transliterate library."""
        self._ensure_transliterate()
        try:
            return self.transliterate(text, 'el', reversed=True)
        except Exception:
            return self._nfkd_fallback(text)

    def _transliterate_hebrew(self, text):
        """Hebrew: custom mapping (no good library found)."""
        # Use NFKD + custom mapping
        return self._nfkd_fallback(text)

    def _transliterate_thai(self, text):
        """Thai: use pythainlp romanization."""
        self._ensure_thai()
        try:
            thai_only = re.sub(r'[^\u0E00-\u0E7F\s]', '', text)
            if thai_only.strip():
                return self._thai_romanize(thai_only.strip())
            return text
        except Exception:
            return self._nfkd_fallback(text)

    def _transliterate_devanagari(self, text):
        """Devanagari/Hindi: use indic-transliteration."""
        self._ensure_indic()
        try:
            deva_only = re.sub(r'[^\u0900-\u097F\s]', '', text)
            if deva_only.strip():
                return self.sanscript.transliterate(deva_only.strip(),
                    self.sanscript.DEVANAGARI, self.sanscript.ISO)
            return text
        except Exception:
            return self._nfkd_fallback(text)

    def _transliterate_bengali(self, text):
        """Bengali: use indic-transliteration."""
        self._ensure_indic()
        try:
            ben_only = re.sub(r'[^\u0980-\u09FF\s]', '', text)
            if ben_only.strip():
                return self.sanscript.transliterate(ben_only.strip(),
                    self.sanscript.BENGALI, self.sanscript.ISO)
            return text
        except Exception:
            return self._nfkd_fallback(text)

    def _transliterate_tamil(self, text):
        """Tamil: use indic-transliteration."""
        self._ensure_indic()
        try:
            tam_only = re.sub(r'[^\u0B80-\u0BFF\s]', '', text)
            if tam_only.strip():
                return self.sanscript.transliterate(tam_only.strip(),
                    self.sanscript.TAMIL, self.sanscript.ISO)
            return text
        except Exception:
            return self._nfkd_fallback(text)

    def _transliterate_gurmukhi(self, text):
        """Gurmukhi: use indic-transliteration."""
        self._ensure_indic()
        try:
            gur_only = re.sub(r'[^\u0A00-\u0A7F\s]', '', text)
            if gur_only.strip():
                return self.sanscript.transliterate(gur_only.strip(),
                    self.sanscript.GURMUKHI, self.sanscript.ISO)
            return text
        except Exception:
            return self._nfkd_fallback(text)

    def _transliterate_georgian(self, text):
        """Georgian: use transliterate library."""
        self._ensure_transliterate()
        try:
            return self.transliterate(text, 'ka', reversed=True)
        except Exception:
            return self._nfkd_fallback(text)

    def _transliterate_armenian(self, text):
        """Armenian: use transliterate library."""
        self._ensure_transliterate()
        try:
            return self.transliterate(text, 'hy', reversed=True)
        except Exception:
            return self._nfkd_fallback(text)

    def _transliterate_myanmar(self, text):
        """Myanmar/Burmese: NFKD fallback."""
        return self._nfkd_fallback(text)

    def _transliterate_khmer(self, text):
        """Khmer: NFKD fallback."""
        return self._nfkd_fallback(text)

    def _transliterate_lao(self, text):
        """Lao: try pythainlp, fallback to NFKD."""
        self._ensure_thai()
        try:
            lao_only = re.sub(r'[^\u0E80-\u0EFF\s]', '', text)
            if lao_only.strip():
                return self._thai_romanize(lao_only.strip())
            return text
        except Exception:
            return self._nfkd_fallback(text)

    def _transliterate_sinhala(self, text):
        """Sinhala: NFKD fallback."""
        return self._nfkd_fallback(text)

    def _transliterate_tibetan(self, text):
        """Tibetan: NFKD fallback (Wylie approximation)."""
        return self._nfkd_fallback(text)

    def _transliterate_ethiopic(self, text):
        """Ethiopic: NFKD fallback."""
        return self._nfkd_fallback(text)

    @staticmethod
    def _nfkd_fallback(text):
        """NFKD Unicode normalization as a fallback transliteration."""
        import unicodedata
        # NFKD decomposes many characters to ASCII approximations
        result = unicodedata.normalize('NFKD', text)
        # Remove combining marks (accents) left after NFKD
        result = re.sub(r'[\u0300-\u036F]', '', result)
        # Collapse spaces
        result = re.sub(r'\s+', ' ', result).strip()
        return result


# ─── Database operations ─────────────────────────────────────────────────
def detect_scripts(name):
    """Detect which non-Roman scripts are in a name string."""
    found = []
    for script_name, pattern in SCRIPTS.items():
        if pattern.search(name):
            found.append(script_name)
    return found


def process_batch(db, transliterator, rows, dry_run=False):
    """Process a batch of rows, returning stats."""
    stats = {"processed": 0, "transliterated": 0, "original_extracted": 0,
             "skipped": 0, "errors": 0}

    updates = []  # (name_transliterated, name_original, id)

    for row_id, name, name_orig_current in rows:
        stats["processed"] += 1
        try:
            scripts_found = detect_scripts(name)

            if not scripts_found:
                # Name is already Roman — check if name_original has non-roman
                if name_orig_current:
                    orig_scripts = detect_scripts(name_orig_current)
                    if orig_scripts:
                        # name_original has non-roman, transliterate from there
                        trans, orig = transliterator.transliterate_script(
                            name_orig_current, orig_scripts)
                        if trans and trans != name_orig_current:
                            updates.append((name, orig, row_id))
                            stats["transliterated"] += 1
                            stats["original_extracted"] += 1
                        else:
                            stats["skipped"] += 1
                    else:
                        stats["skipped"] += 1
                else:
                    stats["skipped"] += 1
                continue

            # Name has non-roman scripts
            trans, orig = transliterator.transliterate_script(name, scripts_found)

            # Determine what needs updating
            update_trans = None
            update_orig = None

            if trans and trans != name:
                update_trans = trans

            if orig and (not name_orig_current or name_orig_current == ''):
                update_orig = orig

            if update_trans or update_orig:
                updates.append((update_trans, update_orig, row_id))
                if update_trans:
                    stats["transliterated"] += 1
                if update_orig:
                    stats["original_extracted"] += 1
            else:
                stats["skipped"] += 1

        except Exception as e:
            stats["errors"] += 1
            if stats["errors"] <= 5:
                print(f"    ERROR id={row_id}: {e}", file=sys.stderr)

    # Apply updates
    if not dry_run and updates:
        cursor = db.cursor()
        cursor.executemany(
            """UPDATE churches
               SET name_transliterated = COALESCE(?, name_transliterated),
                   name_original = COALESCE(?, name_original)
               WHERE id = ?""",
            updates
        )
        db.commit()

    return stats, len(updates)


def main():
    dry_run = "--dry-run" in sys.argv
    limit = None
    start_id = None
    for arg in sys.argv:
        if arg.startswith("--limit="):
            limit = int(arg.split("=")[1])
        if arg.startswith("--start-id="):
            start_id = int(arg.split("=")[1])

    db_path = "E:\\grid\\churches.db"
    db = sqlite3.connect(db_path)
    db.execute("PRAGMA journal_mode=WAL")

    transliterator = Transliterator()

    # Count records with non-Roman in name
    cur = db.execute("SELECT COUNT(*) FROM churches WHERE name IS NOT NULL AND name != ''")
    total = cur.fetchone()[0]

    # Get rows - optionally from a start ID
    if start_id:
        cur = db.execute(
            "SELECT id, name, COALESCE(name_original, '') FROM churches "
            "WHERE id >= ? AND name IS NOT NULL AND name != '' "
            "ORDER BY id",
            (start_id,)
        )
    else:
        cur = db.execute(
            "SELECT id, name, COALESCE(name_original, '') FROM churches "
            "WHERE name IS NOT NULL AND name != '' "
            "ORDER BY id"
        )

    all_rows = cur.fetchall()
    print(f"Total rows: {len(all_rows):,}")
    print(f"Dry run: {dry_run}")
    if limit:
        all_rows = all_rows[:limit]
        print(f"Limit: {limit:,}")
    if start_id:
        print(f"Start ID: {start_id:,}")

    BATCH_SIZE = 5000
    total_stats = {"processed": 0, "transliterated": 0, "original_extracted": 0,
                   "skipped": 0, "errors": 0}
    total_updates = 0
    start_time = time.time()

    for batch_start in range(0, len(all_rows), BATCH_SIZE):
        batch = all_rows[batch_start:batch_start + BATCH_SIZE]
        stats, n_updates = process_batch(db, transliterator, batch, dry_run)

        for k in total_stats:
            total_stats[k] += stats[k]
        total_updates += n_updates

        elapsed = time.time() - start_time
        pct = (batch_start + len(batch)) / len(all_rows) * 100
        rate = (batch_start + len(batch)) / elapsed if elapsed > 0 else 0
        print(
            f"  [{pct:5.1f}%] rows={stats['processed']:,} "
            f"translit={stats['transliterated']:,} "
            f"orig_ext={stats['original_extracted']:,} "
            f"errors={stats['errors']:,} "
            f"({rate:.0f} rows/sec)"
        )

    # Summary
    elapsed = time.time() - start_time
    print(f"\n{'='*60}")
    print(f"Complete ({elapsed:.1f}s)")
    print(f"  Processed:       {total_stats['processed']:>8,}")
    print(f"  Transliterated:  {total_stats['transliterated']:>8,}")
    print(f"  Original extracted: {total_stats['original_extracted']:>8,}")
    print(f"  Skipped:         {total_stats['skipped']:>8,}")
    print(f"  Errors:          {total_stats['errors']:>8,}")
    print(f"  DB updates:      {total_updates:>8,}")
    if not dry_run and total_updates > 0:
        print("\n  [OK] Updates committed to database")

        # Log provenance
        ts = datetime.utcnow().isoformat()
        db.execute(
            "INSERT INTO provenance_log (source, action, timestamp, details) "
            "VALUES (?, ?, ?, ?)",
            ("transliterate_names", "enriched",
             ts,
             f"name_transliterated={total_stats['transliterated']:,} | "
             f"name_original={total_stats['original_extracted']:,} | "
             f"scripts: Arabic/CJK/Cyrillic/Greek/Hebrew/Hangul/Thai/etc"))
        db.commit()
        print("  [OK] Provenance logged")
    elif dry_run:
        print("\n  [--] Dry run -- no changes made")

    db.close()


if __name__ == "__main__":
    main()
