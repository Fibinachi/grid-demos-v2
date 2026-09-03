"""
Transliterate non-Latin and accented Latin city names to ASCII English.
Uses unidecode + special handling for common patterns.
Also deduplicates cities that become identical after transliteration.

Usage:
  python transliterate_cities.py              # Compute + apply
  python transliterate_cities.py --apply-only  # Apply from JSON cache
"""
import sqlite3, json, os, sys
from unidecode import unidecode
from collections import Counter

DB = "e:/grid/churches.db"
CACHE = "e:/grid/outputs/city_transliterations.json"
APPLY_ONLY = "--apply-only" in sys.argv

def transliterate_city(city):
    """Convert city to ASCII English, with special handling."""
    if not city:
        return city
    result = unidecode(city)
    result = ' '.join(result.split())
    result = result.encode('ascii', errors='ignore').decode('ascii')
    return result.strip()

def apply_translations(translations):
    """Apply cached translations to DB using temp table."""
    if not translations:
        print("No translations to apply.")
        return
    
    db = sqlite3.connect(DB)
    db.execute("PRAGMA journal_mode=WAL")
    db.execute("PRAGMA busy_timeout=120000")
    
    print(f"\nApplying {len(translations):,} translations via temp table...")
    db.execute("CREATE TEMP TABLE IF NOT EXISTS _city_trans (orig TEXT PRIMARY KEY, trans TEXT)")
    db.execute("DELETE FROM _city_trans")
    
    items = list(translations.items())
    for i in range(0, len(items), 500):
        db.executemany("INSERT OR REPLACE INTO _city_trans VALUES (?, ?)", items[i:i+500])
    
    db.commit()
    
    updated = db.execute("""
        UPDATE churches SET city = (
            SELECT trans FROM _city_trans WHERE orig = churches.city
        )
        WHERE city IN (SELECT orig FROM _city_trans)
    """).rowcount
    
    db.commit()
    
    unique_after = db.execute("SELECT COUNT(DISTINCT city) FROM churches WHERE city IS NOT NULL AND city != ''").fetchone()[0]
    print(f"Updated: {updated:,} rows | Unique cities: {unique_after:,}")
    db.close()

def main():
    if APPLY_ONLY:
        if not os.path.exists(CACHE):
            print(f"No cache at {CACHE}")
            return
        with open(CACHE, 'r', encoding='utf-8') as f:
            translations = json.load(f)
        print(f"Loaded {len(translations):,} translations from cache")
        apply_translations(translations)
        return
    
    db = sqlite3.connect(DB)
    db.execute("PRAGMA journal_mode=WAL")
    db.execute("PRAGMA busy_timeout=60000")
    
    # Get all unique cities that need transliteration
    # Non-Latin: any char beyond Latin Extended-B (U+024F)
    # Accented Latin: chars with diacritics in Latin range
    cities_to_fix = set()
    for row in db.execute("SELECT DISTINCT city FROM churches WHERE city IS NOT NULL AND city != ''"):
        city = row[0]
        needs_fix = False
        for c in city:
            if c > '\u024F':
                needs_fix = True
                break
            # Also flag accented Latin (diacritics)
            if '\u00C0' <= c <= '\u024F' and c not in 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789':
                needs_fix = True
                break
        if needs_fix:
            cities_to_fix.add(city)
    
    print(f"Cities to transliterate: {len(cities_to_fix):,}")
    
    # Build translation map
    translations = {}
    skipped = 0
    became_empty = 0
    unchanged = 0
    
    for city in cities_to_fix:
        translated = transliterate_city(city)
        if not translated:
            became_empty += 1
            continue
        if translated == city:
            unchanged += 1
            continue
        translations[city] = translated
    
    print(f"Translated: {len(translations):,}")
    print(f"  Became empty: {became_empty}")
    print(f"  Unchanged: {unchanged}")
    
    # Save to JSON cache
    os.makedirs(os.path.dirname(CACHE), exist_ok=True)
    with open(CACHE, 'w', encoding='utf-8') as f:
        json.dump(translations, f, ensure_ascii=False)
    print(f"Saved {len(translations):,} translations to {CACHE}")
    
    db.close()
    
    # Try to apply immediately
    apply_translations(translations)
    print(f"\nSample transliterations:")
    for orig, trans in list(translations.items())[:30]:
        if orig != trans:
            print(f"  '{orig}' → '{trans}'")
    
    # Apply updates using temp table (much faster than individual UPDATEs)
    print(f"\nApplying updates via temp table...")
    db.execute("CREATE TEMP TABLE IF NOT EXISTS _city_trans (orig TEXT PRIMARY KEY, trans TEXT)")
    db.execute("DELETE FROM _city_trans")
    
    items = list(translations.items())
    CHUNK = 500
    for i in range(0, len(items), CHUNK):
        db.executemany("INSERT OR REPLACE INTO _city_trans VALUES (?, ?)", items[i:i+CHUNK])
    
    db.commit()
    
    updated = db.execute("""
        UPDATE churches SET city = (
            SELECT trans FROM _city_trans WHERE orig = churches.city
        )
        WHERE city IN (SELECT orig FROM _city_trans)
    """).rowcount
    
    db.commit()
    print(f"Total updated: {updated:,} rows")
    
    # Final stats
    unique_after = db.execute("SELECT COUNT(DISTINCT city) FROM churches WHERE city IS NOT NULL AND city != ''").fetchone()[0]
    print(f"\nFinal unique cities: {unique_after:,}")
    
    db.close()
    print("Done.")

if __name__ == '__main__':
    main()
