"""
reclassify_minority_faiths.py — Comprehensive minority faith reclassification.

Fixes systematic misclassification of minority faiths caused by:
1. NTEE X70→Hindu mapping catching Jain/Sikh/Zoroastrian institutions
2. Christian-centric name heuristics catching non-Christian names with
   'church', 'temple', 'mission', 'assembly', 'igreja', etc.
3. No patterns at all for some faiths (Taoist, Confucian, Zoroastrian)

Classification rules (by priority — first match wins):
  — Afro-Diasporic: keywords for Umbanda, Candomblé, Santería, Vodou, etc.
  — Indigenous: Native American Church, Peyotism, Longhouse, etc.
  — Sikh: 'sikh', 'gurdwara' — already 81% correct, fix 375 miscategorized
  — Jain: 'jain' (excl. 'hindu' co-mentions) — fix 2,130 miscategorized
  — Zoroastrian: 'zoroastrian', 'zarathushtra', specific 'parsi' phrases
  — Confucian: 'confucian', 'confucius' — fix 24 miscategorized
  — Taoist: 'taoist', 'taoism', 'daoist' — fix 65 miscategorized
  — Shinto: '\bshinto\b' — fix ~20 miscategorized
  — Baha'i: '\bbaha[ui]ll?ah\b', '\bbahai\b' — fix 97 miscategorized
  — Pagan/Wiccan: '\bpagan\b', '\bwicca', '\bwiccan', '\bdruid'

Usage:
    python scripts/enrichment/reclassify_minority_faiths.py           # full run
    python scripts/enrichment/reclassify_minority_faiths.py --limit 50  # test
    python scripts/enrichment/reclassify_minority_faiths.py --preview   # dry run
"""
import argparse
import os
import sys
import sqlite3
import re
from collections import Counter, defaultdict

PROJECT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, PROJECT)
from gw_db import connect, Provenance

DB_PATH = os.path.join(PROJECT, 'churches.db')

# ═══════════════════════════════════════════════════════════════════
# CLASSIFICATION RULES — ordered by priority (first match wins)
# Each rule: (regex_pattern, sql_like_pattern, faith, faith_tradition, subtradition)
# ═══════════════════════════════════════════════════════════════════

RULES = [
    # ── AFRO-DIASPORIC ────────────────────────────────────────────
    # Candomblé
    (r'\bcandombl[ée]\b', '%candombl%', 'Other', 'Afro-Diasporic', 'Candomblé'),
    (r'\b(casa|terreiro|templo)\s+de\s+candombl[ée]\b', '%candombl%', 'Other', 'Afro-Diasporic', 'Candomblé'),
    (r'\bil[êe]\s+ax[ée]\b', '%ax%', 'Other', 'Afro-Diasporic', 'Candomblé'),

    # Umbanda
    (r'\bumbanda\b', '%umbanda%', 'Other', 'Afro-Diasporic', 'Umbanda'),
    (r'\btenda\s+de\s+umbanda\b', '%umbanda%', 'Other', 'Afro-Diasporic', 'Umbanda'),
    (r'\bterreiro\s+de\s+umbanda\b', '%umbanda%', 'Other', 'Afro-Diasporic', 'Umbanda'),

    # Santería / Lukumí
    (r'\bsanter[ií]a\b', '%santeri%', 'Other', 'Afro-Diasporic', 'Santería'),
    (r'\bl[uo]kum[ií]\b', '%lukumi%', 'Other', 'Afro-Diasporic', 'Santería'),

    # Vodou
    (r'\b(vaudou|vodou[n]?|voudou[n]?)\b', '%vodou%', 'Other', 'Afro-Diasporic', 'Vodou'),
    (r'\bvoodoo\b', '%voodoo%', 'Other', 'Afro-Diasporic', 'Vodou'),
    (r'\bperistyle\b', '%peristyle%', 'Other', 'Afro-Diasporic', 'Vodou'),
    (r'\bhoun?for\b', '%hounfor%', 'Other', 'Afro-Diasporic', 'Vodou'),

    # Yoruba / Ifá
    (r'\byoruba\b', '%yoruba%', 'Other', 'Afro-Diasporic', 'Yoruba/Ifá'),
    (r'\bif[áa]\b', '%ifa%', 'Other', 'Afro-Diasporic', 'Yoruba/Ifá'),
    (r'\bori[sz]ha?\b', '%orisha%', 'Other', 'Afro-Diasporic', 'Yoruba/Ifá'),
    (r'\bbabalawo\b', '%babalawo%', 'Other', 'Afro-Diasporic', 'Yoruba/Ifá'),

    # Macumba
    (r'\bmacumba\b', '%macumba%', 'Other', 'Afro-Diasporic', 'Macumba'),

    # Generic terreiro → Umbanda (catch-all — but NOT "terreiro" in Portuguese = "yard/ground")
    (r'\bterreiro\b', '%terreiro%', 'Other', 'Afro-Diasporic', 'Umbanda'),

    # ── INDIGENOUS ────────────────────────────────────────────────
    (r'\bnative\s+american\s+church\b', '%native american church%', 'Other', 'Indigenous', 'Native American Church'),
    (r'\bpeyote\s+church\b', '%peyote church%', 'Other', 'Indigenous', 'Native American Church'),
    (r'\bpeyote\s+way\b', '%peyote way%', 'Other', 'Indigenous', 'Native American Church'),
    (r'\blonghouse\b', '%longhouse%', 'Other', 'Indigenous', 'Indigenous Longhouse Tradition'),
    (r'\bsweat\s+lodge\b', '%sweat lodge%', 'Other', 'Indigenous', 'Indigenous (Sweat Lodge)'),
    (r'\bmedicine\s+wheel\b', '%medicine wheel%', 'Other', 'Indigenous', 'Indigenous (Medicine Wheel)'),
    (r'\bsun\s+dance\b', '%sun dance%', 'Other', 'Indigenous', 'Indigenous (Sun Dance)'),
    (r'\bkiva\b', '%kiva%', 'Other', 'Indigenous', 'Indigenous (Kiva)'),

    # ── SIKH ──────────────────────────────────────────────────────
    (r'\bsikh\b', '%sikh%', 'Sikh', 'Sikh', None),
    (r'\bgurdwara\b', '%gurdwara%', 'Sikh', 'Sikh', None),

    # ── JAIN ──────────────────────────────────────────────────────
    (r'\bjain\b', '%jain%', 'Jain', 'Jain', None),

    # ── ZOROASTRIAN ──────────────────────────────────────────────
    (r'\bzoroastrian\b', '%zoroastrian%', 'Zoroastrian', 'Zoroastrian', None),
    (r'\bzarathushtra\b', '%zarathushtra%', 'Zoroastrian', 'Zoroastrian', None),
    (r'\bparsi\s+(fire\s+)?temple\b', '%parsi%temple%', 'Zoroastrian', 'Zoroastrian', None),
    (r'\bparsi\s+(agiary|agiyari|agiyery|anju[mn])\b', '%parsi%', 'Zoroastrian', 'Zoroastrian', None),
    (r'\bparsi\s+fire\b', '%parsi fire%', 'Zoroastrian', 'Zoroastrian', None),
    (r'\bparsi\s+dare?\s*me?her\b', '%parsi%', 'Zoroastrian', 'Zoroastrian', None),
    (r'\b(atash|atesh)\s+behram\b', '%behram%', 'Zoroastrian', 'Zoroastrian', None),

    # ── CONFUCIAN ────────────────────────────────────────────────
    (r'\bconfucian\b', '%confucian%', 'Confucian', 'Confucian', None),
    (r'\bconfucius\b', '%confucius%', 'Confucian', 'Confucian', None),

    # ── TAOIST ────────────────────────────────────────────────────
    (r'\btaoist\b', '%taoist%', 'Taoist', 'Taoist', None),
    (r'\btaoism\b', '%taoism%', 'Taoist', 'Taoist', None),
    (r'\bdaoist\b', '%daoist%', 'Taoist', 'Taoist', None),

    # ── SHINTO ────────────────────────────────────────────────────
    (r'\bshinto\b', '%shinto%', 'Shinto', 'Shinto', None),

    # ── BAHA'I ────────────────────────────────────────────────────
    (r"\bbaha'?i\b", '%bahai%', 'Bahai', 'Bahai', None),
    (r'\bbahaullah\b', '%bahaullah%', 'Bahai', 'Bahai', None),

    # ── PAGAN / WICCAN ───────────────────────────────────────────
    # Apply regex after SQL filtering to handle false positives
    (r'\bpagan\b', '%pagan%', 'Other', 'Pagan', 'Pagan (unspecified)'),
    (r'\bwicca\b', '%wicca%', 'Other', 'Pagan', 'Wiccan'),
    (r'\bwiccan\b', '%wiccan%', 'Other', 'Pagan', 'Wiccan'),
    (r'\bdruid\b', '%druid%', 'Other', 'Pagan', 'Druid'),
]

# ── FALSE POSITIVE EXCLUSIONS ────────────────────────────────────
# If any pattern matches, skip the record even if a rule matched

FALSE_POSITIVES = [
    # Jain+Hindu dual-tradition centers
    (r'\bjain\b.*\bhindu\b|\bhindu\b.*\bjain\b', 'Jain'),

    # "Pagano/Pagani" are Italian surnames, not pagan
    (r'\bpagano\b', 'Other'),
    (r'\bpagani\b', 'Other'),

    # "Paganico" is an Italian place name
    (r'\bpaganico\b', 'Other'),

    # "Paganella" is an Italian mountain region
    (r'\bpaganella\b', 'Other'),

    # "Pagan" as part of "Cipaganti" (Indonesian place)
    (r'\bcipaganti\b', 'Other'),

    # "Pagan" as part of Balinese/Kawi place names
    (r'\bpagan\s+kelod\b', 'Other'),

    # "Kiva" as part of Jewish name "Akiva"
    (r'\bakiva\b', 'Other'),

    # "Parsi" in "Parsippany" (NJ town)
    (r'\bparsippany\b', 'Zoroastrian'),

    # "Parsi" in Indonesian place names
    (r'\bparsibarungan\b', 'Zoroastrian'),
    (r'\bparsingkaman\b', 'Zoroastrian'),
    (r'\bparsih\b', 'Zoroastrian'),
    (r'\bparsidh\b', 'Zoroastrian'),
    (r'\bparsian\b', 'Zoroastrian'),

    # Shinto false positive from "WASHINTON" misspelling
    (r'\bwashinton\b', 'Shinto'),

    # Druid false positive from place names (Druid Hills, Druid Park, etc.)
    (r'\bdruid\s+(hills|park|lake|heights|valley)\b', 'Other'),
]


def is_false_positive(name, matched_rule_faith):
    """Check if a name is a known false positive for the matched faith."""
    if not name:
        return False
    name_lower = name.lower()
    for pattern, faith in FALSE_POSITIVES:
        if re.search(pattern, name_lower) and faith == matched_rule_faith:
            return True
    return False


def classify_record(name):
    """
    Classify a single record. Returns (faith, faith_tradition, subtradition) or None.
    """
    if not name:
        return None

    for pattern, _, faith, tradition, subtradition in RULES:
        if re.search(pattern, name, re.IGNORECASE):
            if is_false_positive(name, faith):
                return None
            return (faith, tradition, subtradition)

    return None


def main():
    parser = argparse.ArgumentParser(description='Reclassify minority faiths')
    parser.add_argument('--limit', type=int, default=None, help='Limit to N records')
    parser.add_argument('--preview', action='store_true', help='Dry run only')
    args = parser.parse_args()

    conn = sqlite3.connect(DB_PATH, timeout=60)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=60000")
    c = conn.cursor()

    # ── Gather candidates from SQL LIKE patterns ─────────────────
    sql_patterns = sorted(set(p[1] for p in RULES if p[1]))
    like_clauses = ["name COLLATE NOCASE LIKE ?" for _ in sql_patterns]
    query = f"SELECT id, name, faith, faith_tradition, subtradition FROM churches WHERE {' OR '.join(like_clauses)}"
    rows = c.execute(query, sql_patterns).fetchall()
    print(f"Candidate records (broad name match): {len(rows):,}")

    # ── Classify ───────────────────────────────────────────────
    changes = []
    for row in rows:
        rid, name, cur_faith, cur_trad, cur_sub = row

        result = classify_record(name)
        if result is None:
            continue

        faith, tradition, subtradition = result

        # Skip if already correctly classified
        if (cur_faith or '') == faith and (cur_trad or '') == tradition and (cur_sub or '') == (subtradition or ''):
            continue

        changes.append((rid, name, cur_faith or '', cur_trad or '', cur_sub or '',
                        faith, tradition, subtradition or ''))

    print(f"Records to reclassify: {len(changes):,}")

    if not changes:
        print("\nNo changes needed.")
        conn.close()
        return

    # ── Summarize ──────────────────────────────────────────────
    print()
    faith_counts = Counter()
    trad_counts = Counter()
    sub_counts = Counter()
    for c_ in changes:
        faith_counts[c_[5]] += 1
        trad_counts[c_[6]] += 1
        if c_[7]:
            sub_counts[c_[7]] += 1

    print("By faith:")
    for f, cnt in faith_counts.most_common():
        print(f'  {str(f):20s} {cnt:>5,}')

    print("\nBy faith_tradition:")
    for t, cnt in trad_counts.most_common():
        print(f'  {str(t):25s} {cnt:>5,}')

    if sub_counts:
        print("\nBy subtradition:")
        for s, cnt in sub_counts.most_common():
            print(f'  {str(s):30s} {cnt:>5,}')

    # Sample display
    print("\nSample changes:")
    by_faith = defaultdict(list)
    for c_ in changes:
        by_faith[c_[5]].append(c_)
    for faith in sorted(by_faith.keys()):
        samples = by_faith[faith][:3]
        for s in samples:
            print(f'  [{faith:15s}] {s[1][:70]}')
            print(f'           was: faith={s[2]:12s} trad={s[3]:20s} sub={s[4]:20s}')
            print(f'           now: faith={s[5]:12s} trad={s[6]:20s} sub={s[7]:20s}')

    if args.preview:
        print(f"\n--- PREVIEW MODE — no changes made ({len(changes):,} would be updated) ---")
        conn.close()
        return

    if args.limit:
        changes = changes[:args.limit]
        print(f"\n  (limited to {args.limit})")

    # ── Apply ──────────────────────────────────────────────────
    print(f'\nApplying {len(changes):,} reclassifications...')
    updated = 0
    errors = 0
    error_ids = []

    with Provenance(conn, 'reclassify_minority_faiths.py', source='classification_fix',
                    action='updated', fields='faith,faith_tradition,subtradition') as prov:
        prov.records_attempted = len(changes)

        for rid, name, cur_f, cur_ft, cur_s, new_f, new_ft, new_s in changes:
            try:
                c.execute("""
                    UPDATE churches
                    SET faith = ?, faith_tradition = ?, subtradition = ?
                    WHERE id = ?
                """, (new_f if new_f else None,
                      new_ft if new_ft else None,
                      new_s if new_s else None,
                      rid))
                updated += 1
            except Exception as e:
                errors += 1
                if errors <= 5:
                    error_ids.append((rid, str(e)))

        prov.churches_updated = updated
        if errors:
            prov.status = 'completed_with_errors'
            prov.error_msg = f'{errors} errors: {error_ids[:5]}'

    conn.commit()

    print(f'  Updated: {updated:,}')
    if errors:
        print(f'  Errors:  {errors:,}')
        for eid, emsg in error_ids[:5]:
            print(f'    ID={eid}: {emsg}')

    # ── Summary ────────────────────────────────────────────────
    print(f'\nDone. Reclassified {updated:,} records.')
    for f, cnt in sorted(faith_counts.items(), key=lambda x: -x[1]):
        print(f'  {f}: {cnt:,}')

    conn.close()


if __name__ == '__main__':
    main()
