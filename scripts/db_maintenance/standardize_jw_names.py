"""
JW Name Normalizer — Standardize all Kingdom Hall / JW names.
Groups by unique name patterns for efficiency, then batch-updates all matching rows.

Usage:
    python scripts/db_maintenance/standardize_jw_names.py         # run for real
    python scripts/db_maintenance/standardize_jw_names.py --dry-run   # preview only
"""
import sqlite3, re, sys
from datetime import datetime

CHUNK = 500

# Normalize unicode apostrophes
def fix_apost(s):
    s = s.replace('\u2019', "'").replace('\u2018', "'").replace('\u201a', "'").replace('\u201b', "'")
    s = s.replace('\u00c6', "'").replace('\u00e6', "'")
    s = s.replace('Æ', "'").replace('æ', "'")
    return s


def translate_non_english(name, low, canonical, has_city_col):
    """For non-English names, check for a city prefix before the foreign pattern."""
    foreign_keywords = [
        'königreichssaal', 'königreichsaal', 'koninkrijkszaal',
        'salón del reino', 'salon del reino', 'salão do reino', 'salao do reino',
        'salle du royaume', 'rikets sal', 'rigssal', 'valtakunnansali',
        'királyságterme', 'vavolombelon', 'nalunaajaa', 'ríkissalur',
        'królestwa', 'regatului', 'stævnehal', 'stevnehall',
        'ufalme', 'zeugen', 'vittnen', 'vitners', 'vidner',
        'todistajien', 'tanúinak', 'getuigen', 'sala del regno',
        'königreichsaal', 'konigreichssaal',
    ]
    idx = len(low)
    for kw in foreign_keywords:
        pos = low.find(kw)
        if pos >= 0 and pos < idx:
            idx = pos
    if idx > 0:
        prefix = name[:idx].strip().rstrip('- ,;:(').strip()
        prefix_low = prefix.lower()
        if (len(prefix) > 1
                and not re.search(r'jehov|witness|kingdom|assembly|hall|church|congregation|the |jw', prefix_low)
                and prefix_low not in ('', 'the')
                and not re.match(r'^\d+\s', prefix)):
            prefix = re.sub(r'[,\-:\s]+$', '', prefix).strip()
            backfill = prefix if not has_city_col else None
            return f"{canonical} \u2014 {prefix}", backfill
    return canonical, None


def normalize_name_pattern(name, has_city):
    """
    Determine the canonical form for one unique name pattern.
    Returns (canonical_name, backfill_city_or_None).
    """
    orig = name
    name = fix_apost(name)
    low = name.lower().strip()

    # ── PHASE 1: Detect and translate non-English ──
    has_foreign_chars = bool(re.search(r'[^\x00-\x7f]', name))
    has_foreign_kw = any(kw in low for kw in [
        'königreich', 'koninkrijk', 'testigos', 'testemunha',
        'témoins', 'temoins', 'rikets', 'rigssal', 'valtakunnan',
        'királyság', 'vavolombelon', 'nalunaajaa', 'salón',
        'salão', 'salle', 'salao', 'salon', 'zeugen',
        'getuigen', 'todistajien', 'vitnum', 'vitners', 'vittnen',
        'vidner', 'vidners', 'stævnehal', 'stevnehall',
        'królestwa', 'tanúinak', 'tanúi', 'efitrano', 'fanjakan',
        'naalagaaffi', 'ufalme', 'regatului',
        'ríkissalur', 'rikissalur', 'koninkrijk',
    ])

    is_foreign = has_foreign_chars or has_foreign_kw

    if is_foreign:
        # German
        if 'königreichssaal' in low or 'königreichsaal' in low or 'konigreichssaal' in low or 'königreichsaal' in low:
            return translate_non_english(name, low, "Kingdom Hall of Jehovah's Witnesses", has_city)
        if 'zeugen jehovas' in low and 'königreich' not in low and 'königreich' not in low and 'kongress' not in low:
            if 'kongress' in low:
                return "Assembly Hall of Jehovah's Witnesses", None
            return translate_non_english(name, low, "Jehovah's Witnesses", has_city)
        if 'kongress-saal' in low or 'kongress saal' in low:
            return "Assembly Hall of Jehovah's Witnesses", None

        # Spanish
        if ('salón' in low or 'salon' in low) and ('reino' in low or 'testigos' in low):
            if 'asambleas' in low:
                return translate_non_english(name, low, "Assembly Hall of Jehovah's Witnesses", has_city)
            return translate_non_english(name, low, "Kingdom Hall of Jehovah's Witnesses", has_city)
        if low.startswith('testigos de jehova') or low.startswith('testigos de jehová'):
            return "Jehovah's Witnesses", None
        if low.startswith('iglesia testigos'):
            return "Jehovah's Witnesses", None

        # Portuguese
        if ('salão' in low or 'salao' in low) and 'reino' in low:
            if 'assembleia' in low or 'assembléia' in low:
                return "Assembly Hall of Jehovah's Witnesses", None
            return translate_non_english(name, low, "Kingdom Hall of Jehovah's Witnesses", has_city)

        # French
        if 'salle du royaume' in low:
            return translate_non_english(name, low, "Kingdom Hall of Jehovah's Witnesses", has_city)
        if low.strip() in ('témoin de jéhovah', 'temoin de jehovah'):
            return "Jehovah's Witnesses", None
        if 'témoins' in low or 'temoins' in low:
            return "Jehovah's Witnesses", None

        # Dutch
        if 'koninkrijkszaal' in low:
            return translate_non_english(name, low, "Kingdom Hall of Jehovah's Witnesses", has_city)
        if low.strip() in ("jehovah's getuigen", "jehova's getuigen", "jehovah getuigen"):
            return "Jehovah's Witnesses", None

        # Swedish
        if 'rikets sal' in low or 'vittnen' in low or 'vitners' in low:
            if 'rikets' in low:
                return translate_non_english(name, low, "Kingdom Hall of Jehovah's Witnesses", has_city)
            if low.strip() in ('jehovas vittnen', 'jehovas vitners', 'jehovas vittnens'):
                return "Jehovah's Witnesses", None

        # Danish
        if 'rigssal' in low:
            if 'stævnehal' in low or 'staevnehal' in low:
                return "Assembly Hall of Jehovah's Witnesses", None
            return translate_non_english(name, low, "Kingdom Hall of Jehovah's Witnesses", has_city)
        if low.strip() in ('jehovas vidner',):
            return "Jehovah's Witnesses", None

        # Norwegian
        if 'stevnehall' in low or 'vitners stevne' in low:
            return "Assembly Hall of Jehovah's Witnesses", None

        # Finnish
        if 'valtakunnansali' in low or 'todistajien' in low:
            return translate_non_english(name, low, "Kingdom Hall of Jehovah's Witnesses", has_city)

        # Hungarian
        if 'királyságterme' in low or 'királyságterme' in low or 'királyság' in low:
            return translate_non_english(name, low, "Kingdom Hall of Jehovah's Witnesses", has_city)

        # Malagasy
        if 'vavolombelon' in low:
            if 'efitrano' in low or 'fanjakan' in low:
                return "Kingdom Hall of Jehovah's Witnesses", None
            return "Jehovah's Witnesses", None

        # Greenlandic
        if 'nalunaajaasuisa' in low:
            return "Kingdom Hall of Jehovah's Witnesses", None

        # Icelandic
        if 'ríkissalur' in low or 'rikissalur' in low:
            return "Kingdom Hall of Jehovah's Witnesses", None

        # Polish / Romanian / Italian / Swahili
        if 'królestwa' in low:
            return "Kingdom Hall of Jehovah's Witnesses", None
        if 'regatului' in low:
            return "Kingdom Hall of Jehovah's Witnesses", None
        if low.startswith('sala del regno'):
            return "Kingdom Hall of Jehovah's Witnesses", None
        if low.strip() == 'ufalme':
            return "Kingdom Hall of Jehovah's Witnesses", None

        # Generic: catch-all for other non-English
        if has_foreign_chars:
            return "Kingdom Hall of Jehovah's Witnesses", None

    # ── PHASE 2: English patterns ──
    # Normalize apostrophes in "Jehovah's"
    name_fixed = re.sub(r'\bJehovah[\'`´ˈ′]?s?\b', "Jehovah's", name, flags=re.IGNORECASE)
    name_fixed = re.sub(r'\bJehova[\'`´ˈ′]?s?\b', "Jehovah's", name_fixed, flags=re.IGNORECASE)
    name_fixed = re.sub(r'\bJehova\b(?!\')', "Jehovah", name_fixed, flags=re.IGNORECASE)
    name_fixed = re.sub(r'\bJahova\b', "Jehovah", name_fixed, flags=re.IGNORECASE)
    name_fixed = re.sub(r'\bJevovah\b', "Jehovah", name_fixed, flags=re.IGNORECASE)
    name_fixed = re.sub(r'\bJahovah\b', "Jehovah", name_fixed, flags=re.IGNORECASE)

    low2 = name_fixed.lower().strip()

    # "Assembly Hall of Jehovah's Witnesses"
    if 'assembly hall' in low2 and ('jehov' in low2 or 'witness' in low2):
        return "Assembly Hall of Jehovah's Witnesses", None

    # Short standalone forms → "Jehovah's Witnesses"
    standalone = low2.strip().rstrip('.')
    if standalone in (
        "jehovah's witnesses", "jehovah witnesses", "jehovah witness",
        "jehovah's witness", "jehovahs witnesses", "jehovahs witness",
        "jehovas witnesses", "jehovas witness",
        "jehova's witnesses", "jehova's witness",
        "jehovah's witnesses hall", "jehovah's witnesses hll",
        "jehovah's witnesses church",
    ):
        return "Jehovah's Witnesses", None

    # "KINGDOM HALL" variants with city prefixes and suffixes
    if 'kingdom hall' in low2 or 'kingdom hall' in low2:
        # Fix "K哈ll" typo etc
        name_fixed = re.sub(r'\bK[哈í]ll\b', 'Hall', name_fixed, flags=re.IGNORECASE)
        low2 = name_fixed.lower()

        kh = re.search(r'kingdom\s*hall', low2)
        if not kh:
            return "Kingdom Hall of Jehovah's Witnesses", None

        prefix = name_fixed[:kh.start()].strip().rstrip('- ,;:(\u2014').strip() if kh.start() > 0 else ''
        suffix = name_fixed[kh.end():].strip().lstrip('- ,;:(\u2014').strip() if kh.end() < len(name_fixed) else ''

        prefix_low = prefix.lower().strip()
        suffix_low = suffix.lower().strip()

        # Determine if prefix/suffix is a location (not a JW keyword)
        def is_location(text):
            if not text or len(text) <= 1:
                return False
            tl = text.lower()
            # Reject if it starts with a number — that's a street address, not a city
            if re.match(r'^\d+\s', text):
                return False
            if re.search(r'jehov|witness|kingdom|assembly|hall|church|congregation|the |jw |study|hl |hll|wtns|wtnss|wittness|wittnesses|centre', tl):
                return False
            if tl in ('', 'the', 'of', 'and', 'for', 'in', 'at', 'on', 'to', 'by', 'north', 'south', 'east', 'west', 'central', 'old', 'new'):
                return False
            return True

        city_name = None
        if is_location(prefix) and not is_location(suffix):
            city_name = prefix
        elif is_location(suffix) and not is_location(prefix):
            city_name = suffix
        elif is_location(prefix) and is_location(suffix):
            # Both look like places — use prefix
            city_name = prefix

        canonical = "Kingdom Hall of Jehovah's Witnesses"
        if city_name:
            city_name = re.sub(r'[,\-:\s]+$', '', city_name).strip()
            result = f"{canonical} \u2014 {city_name}"
            backfill = city_name if not has_city else None
            return result, backfill
        return canonical, None

    # "Jehovah's Witnesses Kingdom Hall" (reversed order)
    if 'jehov' in low2 and 'witness' in low2 and 'kingdom hall' in low2:
        return "Kingdom Hall of Jehovah's Witnesses", None

    # "Kingdom Hall Church" → remove "Church"
    if low2.strip() == 'kingdom hall church':
        return "Kingdom Hall of Jehovah's Witnesses", None

    # "Kingdom Hall" standalone
    if low2.strip() in ('kingdom hall', 'kingdom hall '):
        return "Kingdom Hall of Jehovah's Witnesses", None

    # "JW Kingdom Hall"
    if low2.strip() == 'jw kingdom hall':
        return "Kingdom Hall of Jehovah's Witnesses", None

    # "Jehovah Kingdom Hall"
    if low2.strip() == 'jehovah kingdom hall':
        return "Kingdom Hall of Jehovah's Witnesses", None

    # Grab-bag: any remaining name with "Kingdom Hall" and "Jehovah"
    if 'kingdom hall' in low2:
        return "Kingdom Hall of Jehovah's Witnesses", None

    # If nothing matched, return cleaned original
    return name_fixed, None


def main():
    dry_run = '--dry-run' in sys.argv

    db = sqlite3.connect(r'E:\grid\churches.db', timeout=120)
    db.execute("PRAGMA journal_mode=WAL")
    db.execute("PRAGMA busy_timeout=120000")
    c = db.cursor()

    print("=== JW Name Normalizer ===")
    print("Querying unique name patterns...")

    rows = c.execute("""
        SELECT name,
               COUNT(*) as cnt,
               MAX(CASE WHEN city IS NOT NULL AND city != '' AND city != 'None' THEN city ELSE NULL END) as sample_city,
               country
        FROM churches
        WHERE (name LIKE '%Kingdom%Hall%' OR name LIKE '%Jehovah%' OR name LIKE '%Jehova%'
           OR name LIKE '%Salon%Reino%' OR name LIKE '%Salon%Reino%' OR name LIKE '%Salao%Reino%'
           OR name LIKE '%Salao%Reino%' OR name LIKE '%Assembly%Hall%Jehov%'
           OR name LIKE '%Testigos%Jehova%' OR name LIKE '%Testemunha%Jeova%'
           OR name LIKE '%Witnesses%')
        AND name NOT LIKE '%Universal%' AND name NOT LIKE '%IURD%'
        AND name NOT LIKE '%JIREH%' AND name NOT LIKE '%Jireh%'
        AND name NOT LIKE '%BAPTIST%' AND name NOT LIKE '%Baptist%'
        AND name NOT LIKE '%LUTHERAN%' AND name NOT LIKE '%Lutheran%'
        AND name NOT LIKE '%SHAMMAH%'
        AND name NOT LIKE '%RAPHA%'
        AND name NOT LIKE '%MINISTRIES%' AND name NOT LIKE '%Ministries%'
        AND name NOT LIKE '%METHODIST%' AND name NOT LIKE '%Pentecostal%'
        AND name NOT LIKE '%PENTECOSTAL%'
        AND name NOT LIKE '%CHRISTIAN%'
        AND name NOT LIKE '%FELLOWSHIP%' AND name NOT LIKE '%Fellowship%'
        AND name NOT LIKE '%PRAISE%' AND name NOT LIKE '%Praise%'
        AND name NOT LIKE '%WORSHIP%' AND name NOT LIKE '%Worship%'
        AND name NOT LIKE '%COMMUNITY%' AND name NOT LIKE '%Community%'
        AND name NOT LIKE '%MISSIONARY%' AND name NOT LIKE '%Missionary%'
        AND name NOT LIKE '%DELIVERANCE%'
        AND name NOT LIKE '%NISSI%' AND name NOT LIKE '%Nissi%'
        AND name NOT LIKE '%SAMA%' AND name NOT LIKE '%Sama%'
        AND name NOT LIKE '%SHALOM%' AND name NOT LIKE '%Shalom%'
        AND name NOT LIKE '%CHURCH OF%' AND name NOT LIKE '%Church of%'
        AND name NOT LIKE '%GOSPEL%' AND name NOT LIKE '%Gospel%'
        AND name NOT LIKE '%ROI%' AND name NOT LIKE '%Rohi%'
        AND name NOT LIKE '%EL BUEN PASTOR%'
        AND name NOT LIKE '%PRAYER%' AND name NOT LIKE '%Prayer%'
        AND name NOT LIKE '%HOUSE OF%' AND name NOT LIKE '%House of%'
        GROUP BY name
        ORDER BY cnt DESC
    """).fetchall()

    total_entries = sum(r[1] for r in rows)
    print(f"Found {len(rows):,} unique patterns ({total_entries:,} entries)")

    # Compute canonical forms
    print("\nComputing canonical names...")
    pattern_map = {}
    changes = 0
    unchanged = 0
    translated = 0
    city_found = 0

    for name, cnt, sample_city, country in rows:
        has_city = bool(sample_city and sample_city not in ('', 'None'))
        new_name, backfill_city = normalize_name_pattern(name, has_city)
        if new_name != name:
            pattern_map[name] = (new_name, backfill_city)
            changes += cnt
            if backfill_city:
                city_found += cnt
            if bool(re.search(r'[^\x00-\x7f]', name)):
                translated += cnt
            elif any(kw in name.lower() for kw in [
                    'königreich', 'koninkrijk', 'testigos', 'testemunha',
                    'témoins', 'temoins', 'rikets', 'rigssal', 'valtakunnan',
                    'királyság', 'vavolombelon', 'nalunaajaa', 'salón',
                    'salão', 'salle', 'salao', 'salon', 'zeugen',
                    'getuigen', 'todistajien', 'vitnum', 'vitners', 'vittnen',
                    'vidner', 'vidners', 'stævnehal', 'stevnehall',
                    'królestwa', 'tanúinak', 'tanúi', 'efitrano', 'fanjakan',
                    'naalagaaffi', 'ufalme', 'regatului',
                    'ríkissalur', 'rikissalur']):
                translated += cnt
        else:
            unchanged += cnt

    print(f"\nSummary:")
    print(f"  {changes:,} entries will be changed ({len(pattern_map)} patterns)")
    print(f"  {unchanged:,} entries already canonical")
    print(f"  {translated:,} non-English translated")
    print(f"  {city_found:,} city names extracted")

    if dry_run:
        print("\n=== DRY RUN — no changes made ===")
        print("\nAll pattern changes:")
        for old_name, (new_name, bc) in sorted(pattern_map.items(), key=lambda x: -c.execute(
                'SELECT COUNT(*) FROM churches WHERE name=?', (x[0],)).fetchone()[0]):
            cnt = c.execute('SELECT COUNT(*) FROM churches WHERE name=?', (old_name,)).fetchone()[0]
            bc_str = f"  +city={bc}" if bc else ""
            print(f"  [{cnt:4d}] {old_name[:90]}")
            print(f"       \u2192 {new_name[:90]}{bc_str}")
        return

    # Apply changes
    print("\nApplying changes...")
    c.execute("BEGIN TRANSACTION")
    applied = 0
    now = datetime.now().isoformat()

    for old_name, (new_name, backfill_city) in pattern_map.items():
        # Capture church IDs BEFORE the update (update changes the name)
        # Filter out NULL ids (some records have NULL ids)
        ids = [r[0] for r in c.execute("SELECT id FROM churches WHERE name = ? AND id IS NOT NULL", (old_name,)).fetchall()]
        if not ids:
            # No non-NULL ids to track — still update but skip provenance
            c.execute("UPDATE churches SET name = ? WHERE name = ?", (new_name, old_name))
            rows_affected = c.execute("SELECT changes()").fetchone()[0]
            applied += rows_affected
            continue

        if backfill_city:
            c.execute("""
                UPDATE churches
                SET name = ?,
                    city = COALESCE(NULLIF(NULLIF(city, ''), 'None'), ?)
                WHERE name = ?
            """, (new_name, backfill_city, old_name))
        else:
            c.execute("UPDATE churches SET name = ? WHERE name = ?", (new_name, old_name))

        # Count how many rows were actually updated (including NULL-id rows)
        rows_affected = c.execute("SELECT changes()").fetchone()[0]
        applied += rows_affected

        # Log provenance (first non-NULL id of this pattern)
        c.execute("""
            INSERT INTO enrichment_change_log (church_id, field_name, old_value, new_value, change_source, changed_at)
            VALUES (?, 'name', ?, ?, 'jw_name_normalizer', ?)
        """, (ids[0], old_name, new_name, now))

        if applied % CHUNK == 0:
            c.execute("COMMIT")
            c.execute("BEGIN TRANSACTION")
            print(f"  Applied {applied:,}/{changes:,}...", flush=True)

    c.execute("COMMIT")

    # Final provenance
    c.execute("""
        INSERT INTO provenance_log (source, script_name, started_at, completed_at,
                                     churches_updated, fields_populated, records_attempted, status)
        VALUES ('jw_name_normalizer', 'standardize_jw_names.py', ?, ?, ?, ?, ?, 'completed')
    """, (now, datetime.now().isoformat(), changes, 'name,city', total_entries))
    db.commit()

    print(f"\n\u2713 COMPLETE: {applied:,} entries updated")
    print(f"  Translated {translated:,} non-English names")
    print(f"  Extracted city for {city_found:,} entries")
    print(f"  Provenance logged")

    db.close()


if __name__ == '__main__':
    main()
