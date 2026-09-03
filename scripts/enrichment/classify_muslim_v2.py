"""
Muslim Doctrinal Classification v2
===================================
Classifies remaining unclassified Islam entries (~76K gap) by tradition.
Also cleans up misclassifications (non-Islamic traditions under Islam faith).

Usage:
    python scripts/enrichment/classify_muslim_v2.py
    python scripts/enrichment/classify_muslim_v2.py --dry-run
    python scripts/enrichment/classify_muslim_v2.py --limit 5000
"""

import argparse, re, sqlite3, sys, time
from pathlib import Path

_project_root = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(_project_root))
from gw_db import connect, Provenance, log_change, log_changes_batch

SCRIPT_NAME = "classify_muslim_v2"
CHUNK_SIZE = 2000

# ═══════════════════════════════════════════════════════════════════
# COUNTRY-BASED PRIORS
# ═══════════════════════════════════════════════════════════════════

# Country → (tradition, confidence, source_note)
# Sunni/Shia/Ibadi breakdown by country (dominant tradition)
COUNTRY_PRIORS = {
    # ── Shia majority ──
    'IR': ('Twelver', 0.55, 'geo_iran'),
    'IQ': ('Twelver', 0.40, 'geo_iraq'),
    'AZ': ('Twelver', 0.40, 'geo_azerbaijan'),
    'BH': ('Twelver', 0.35, 'geo_bahrain'),
    'LB': ('Twelver', 0.30, 'geo_lebanon'),

    # ── Ismaili concentrations ──
    'TJ': ('Ismaili', 0.30, 'geo_tajikistan'),

    # ── Ibadhi majority ──
    'OM': ('Ibadi', 0.50, 'geo_oman'),
    'MU': ('Ibadi', 0.20, 'geo_mauritius'),

    # ── Sunni / Hanafi (South Asia, Turkey, Balkans, Central Asia) ──
    'PK': ('Hanafi', 0.40, 'geo_pakistan'),
    'IN': ('Hanafi', 0.35, 'geo_india'),
    'BD': ('Hanafi', 0.40, 'geo_bangladesh'),
    'AF': ('Hanafi', 0.40, 'geo_afghanistan'),
    'TR': ('Hanafi', 0.40, 'geo_turkey'),
    'UZ': ('Hanafi', 0.40, 'geo_uzbekistan'),
    'TM': ('Hanafi', 0.40, 'geo_turkmenistan'),
    'KG': ('Hanafi', 0.40, 'geo_kyrgyzstan'),
    'KZ': ('Hanafi', 0.40, 'geo_kazakhstan'),
    'TJ': ('Hanafi', 0.35, 'geo_tajikistan_h'),
    'AZ': ('Hanafi', 0.30, 'geo_azerbaijan_h'),
    'AL': ('Hanafi', 0.40, 'geo_albania'),
    'XK': ('Hanafi', 0.40, 'geo_kosovo'),
    'BA': ('Hanafi', 0.40, 'geo_bosnia'),
    'MK': ('Hanafi', 0.40, 'geo_macedonia'),
    'RS': ('Hanafi', 0.35, 'geo_serbia'),
    'BG': ('Hanafi', 0.35, 'geo_bulgaria'),
    'CY': ('Hanafi', 0.30, 'geo_cyprus'),
    'GR': ('Hanafi', 0.30, 'geo_greece'),
    'CN': ('Hanafi', 0.30, 'geo_china'),
    'MN': ('Hanafi', 0.30, 'geo_mongolia'),
    'MM': ('Hanafi', 0.30, 'geo_myanmar'),
    'LK': ('Hanafi', 0.30, 'geo_sri_lanka'),

    # ── Sunni / Maliki (West Africa, Maghreb) ──
    'MA': ('Maliki', 0.45, 'geo_morocco'),
    'DZ': ('Maliki', 0.40, 'geo_algeria'),
    'TN': ('Maliki', 0.40, 'geo_tunisia'),
    'LY': ('Maliki', 0.40, 'geo_libya'),
    'MR': ('Maliki', 0.35, 'geo_mauritania'),
    'SN': ('Maliki', 0.40, 'geo_senegal'),
    'ML': ('Maliki', 0.35, 'geo_mali'),
    'GN': ('Maliki', 0.35, 'geo_guinea'),
    'CI': ('Maliki', 0.35, 'geo_cote_ivoire'),
    'BF': ('Maliki', 0.35, 'geo_burkina_faso'),
    'BJ': ('Maliki', 0.35, 'geo_benin'),
    'TG': ('Maliki', 0.35, 'geo_togo'),
    'NE': ('Maliki', 0.35, 'geo_niger'),
    'TD': ('Maliki', 0.35, 'geo_chad'),
    'NG': ('Maliki', 0.30, 'geo_nigeria'),
    'SL': ('Maliki', 0.30, 'geo_sierra_leone'),
    'GM': ('Maliki', 0.35, 'geo_gambia'),
    'GW': ('Maliki', 0.35, 'geo_guinea_bissau'),

    # ── Sunni / Shafi'i (Horn of Africa, SE Asia, Kurdistan) ──
    'SO': ('Shafii', 0.45, 'geo_somalia'),
    'DJ': ('Shafii', 0.40, 'geo_djibouti'),
    'ET': ('Shafii', 0.35, 'geo_ethiopia'),
    'ER': ('Shafii', 0.35, 'geo_eritrea'),
    'KE': ('Shafii', 0.30, 'geo_kenya'),
    'TZ': ('Shafii', 0.30, 'geo_tanzania'),
    'ID': ('Shafii', 0.45, 'geo_indonesia'),
    'MY': ('Shafii', 0.40, 'geo_malaysia'),
    'PH': ('Shafii', 0.30, 'geo_philippines'),
    'TH': ('Shafii', 0.25, 'geo_thailand'),
    'SG': ('Shafii', 0.25, 'geo_singapore'),

    # ── Sunni / General (Arab world) ──
    'SA': ('Salafi', 0.30, 'geo_saudi'),
    'AE': ('Salafi', 0.25, 'geo_uae'),
    'QA': ('Salafi', 0.25, 'geo_qatar'),
    'KW': ('Salafi', 0.25, 'geo_kuwait'),
    'BH': ('Salafi', 0.25, 'geo_bahrain_s'),
    'OM': ('Salafi', 0.20, 'geo_oman_s'),
    'YE': ('Sunni', 0.25, 'geo_yemen'),
    'SY': ('Sunni', 0.30, 'geo_syria'),
    'JO': ('Sunni', 0.30, 'geo_jordan'),
    'PS': ('Sunni', 0.30, 'geo_palestine'),
    'EG': ('Sunni', 0.30, 'geo_egypt'),
    'SD': ('Sunni', 0.30, 'geo_sudan'),
    'LB': ('Sunni', 0.25, 'geo_lebanon_s'),

    # ── Western countries (diverse, default Hanafi) ──
    'US': ('Hanafi', 0.20, 'geo_us'),
    'GB': ('Hanafi', 0.20, 'geo_uk'),
    'DE': ('Hanafi', 0.20, 'geo_germany'),
    'FR': ('Hanafi', 0.20, 'geo_france'),
    'NL': ('Hanafi', 0.20, 'geo_netherlands'),
    'BE': ('Hanafi', 0.20, 'geo_belgium'),
    'AT': ('Hanafi', 0.20, 'geo_austria'),
    'CH': ('Hanafi', 0.20, 'geo_switzerland'),
    'SE': ('Hanafi', 0.20, 'geo_sweden'),
    'DK': ('Hanafi', 0.20, 'geo_denmark'),
    'NO': ('Hanafi', 0.20, 'geo_norway'),
    'FI': ('Hanafi', 0.20, 'geo_finland'),
    'IT': ('Hanafi', 0.20, 'geo_italy'),
    'ES': ('Hanafi', 0.20, 'geo_spain'),
    'AU': ('Hanafi', 0.20, 'geo_australia'),
    'CA': ('Hanafi', 0.20, 'geo_canada'),
    'ZA': ('Hanafi', 0.20, 'geo_south_africa'),
    'RU': ('Hanafi', 0.25, 'geo_russia'),
}

# ═══════════════════════════════════════════════════════════════════
# NAME-BASED RULES (enhanced from classify_muslim.py)
# ═══════════════════════════════════════════════════════════════════

# Higher priority: specific doctrinal signals
SPECIFIC_RULES = [
    # Shia
    (r'\b(ja[ea]fari|jafri)\b', 'Twelver', 0.70, 'name_jafari'),
    (r'\b(ahlul.?bayt|ahl.?al.?bayt)\b', 'Twelver', 0.70, 'name_ahlulbayt'),
    (r'\b(imam.?mahdi|imam.?zaman|imam.?sadiq|imam.?ridha|imam.?kadhim)\b', 'Twelver', 0.70, 'name_imam'),
    (r'\b(husayniyya|imambargah|azakhana)\b', 'Twelver', 0.70, 'name_shia_term'),
    (r'\b(majlis|muharram|ashura|arbaeen)\b', 'Twelver', 0.50, 'name_shia_practice'),
    (r'\bqom\b', 'Twelver', 0.45, 'name_qom'),
    (r'\bsyedna\b', 'Twelver', 0.50, 'name_syedna'),

    # Ismaili
    (r'\b(ismaili|aga.?khan|jamatkhana)\b', 'Ismaili', 0.70, 'name_ismaili'),

    # Bohra
    (r'\b(bohra|dawoodi|mumineen)\b', 'Bohra', 0.70, 'name_bohra'),

    # Zaydi
    (r'\bzaydi\b', 'Zaydi', 0.60, 'name_zaydi'),

    # Sufi
    (r'\b(sufi|tasawwuf|tariqa[ht]?)\b', 'Sufi', 0.60, 'name_sufi'),
    (r'\b(naqshbandi|qadiri[^e]|chishti|suhrawardi)\b', 'Sufi', 0.70, 'name_sufi_order'),
    (r'\b(barelvi|barelwi|ahle.?sunnat|dawate.?islami)\b', 'Sufi', 0.70, 'name_barelvi'),
    (r'\b(mawlid|zawiya)\b', 'Sufi', 0.50, 'name_sufi_practice'),

    # Salafi
    (r'\bsalafi\b', 'Salafi', 0.70, 'name_salafi'),
    (r'\b(ahl.?hadith|ahl.?tawheed)\b', 'Salafi', 0.70, 'name_ahl_hadith'),
    (r'\b(minhaj.?sunnah|dar.?hadith|dar.?tawheed)\b', 'Salafi', 0.60, 'name_salafi_term'),
    (r'\b(furqan|quranic.?center)\b', 'Salafi', 0.45, 'name_salafi_center'),

    # Deobandi
    (r'\bdeobandi\b', 'Deobandi', 0.70, 'name_deobandi'),
    (r'\b(darul.?uloom|dars.?nizami)\b', 'Deobandi', 0.55, 'name_darul_uloom'),
    (r'\btablighi\b', 'Deobandi', 0.55, 'name_tablighi'),

    # Hanafi
    (r'\bhanafi\b', 'Hanafi', 0.70, 'name_hanafi'),
    (r'\bdiyanet\b', 'Hanafi', 0.60, 'name_diyanet'),
    (r'\b(turkish|turkiye)\s*(mosque|masjid|islamic|center|diyanet)\b', 'Hanafi', 0.45, 'name_turkish'),

    # Shafi'i
    (r'\b(shafi[ei]|shafii)\b', 'Shafii', 0.70, 'name_shafii'),
    (r'\b(somali|kurdish|kurdi)\s*(mosque|masjid|center|community|islamic)\b', 'Shafii', 0.50, 'name_shafii_ethnic'),

    # Maliki
    (r'\bmaliki\b', 'Maliki', 0.70, 'name_maliki'),
    (r'\bzaytuna\b', 'Maliki', 0.45, 'name_zaytuna'),

    # Hanbali
    (r'\bhanbali\b', 'Hanbali', 0.70, 'name_hanbali'),

    # Ibadi
    (r'\bibad[hi]+\b', 'Ibadi', 0.70, 'name_ibadi'),

    # Ahmadiyya
    (r'\b(ahmadiyya|ahmadi)\b', 'Ahmadiyya', 0.70, 'name_ahmadi'),
    (r'\b(masroor|baitul|mirza.?ghulam)\b', 'Ahmadiyya', 0.70, 'name_ahmadi_term'),

    # Quranist
    (r'\b(quran.?only|submitter|rashad.?khalifa)\b', 'Quranist', 0.70, 'name_quranist'),

    # Nation of Islam
    (r'\b(nation.?of.?islam|noi)\b', 'Nation of Islam', 0.60, 'name_noi'),
    (r'\b(masjid.?muhammad|elijah.?muhammad|final.?call)\b', 'Nation of Islam', 0.60, 'name_noi_term'),
]

# Lower priority: generic Islamic names
GENERIC_RULES = [
    (r'\b(masjid|mosque|islamic)\s+(al[-\s]?)?(salam|huda|noor|falah|rahma|iman|ansar|aqsa|quds|tawheed|furqan|nabawi)\b', 'Sunni', 0.50, 'name_masjid_common'),
    (r'\bmusallah\b', 'Sunni', 0.45, 'name_musallah'),
    (r'\b(masjid|mosque)\b', 'Sunni', 0.40, 'name_masjid'),
    (r'\bislamic\s*(center|society|foundation|association|council)\b', 'Sunni', 0.40, 'name_islamic_org'),
    (r'\bislamic\b', 'Sunni', 0.35, 'name_islamic'),
    (r'\b(muslim|quran|allah|ummah|halal)\b', 'Sunni', 0.30, 'name_muslim_term'),
]


def classify_by_name(name: str, city: str) -> tuple:
    """Try to classify by name. Returns (tradition, confidence, source) or None."""
    if not name:
        return None
    n = name.lower()
    c = (city or "").lower()

    # Specific rules first
    for pattern, tradition, confidence, source in SPECIFIC_RULES:
        if re.search(pattern, n):
            return tradition, confidence, source
        # Also check city for shia/ismaili patterns
        if re.search(pattern, c):
            return tradition, min(confidence - 0.1, 0.5), f"{source}_in_city"

    # Generic rules
    for pattern, tradition, confidence, source in GENERIC_RULES:
        if re.search(pattern, n):
            return tradition, confidence, source

    return None


def classify_by_country(country: str) -> tuple:
    """Try to classify by country prior. Returns (tradition, confidence, source) or None."""
    if not country:
        return None
    key = country.upper().strip()
    if key in COUNTRY_PRIORS:
        return COUNTRY_PRIORS[key]
    return None


def main():
    parser = argparse.ArgumentParser(description='Muslim doctrinal classification v2')
    parser.add_argument('--dry-run', action='store_true', help='Preview without writing')
    parser.add_argument('--limit', type=int, default=0, help='Limit records to process')
    parser.add_argument('--fix-misclass', action='store_true', help='Fix misclassifications first')
    args = parser.parse_args()

    db = connect(timeout=60)
    c = db.cursor()

    # ════════════════════════════════════════════════════════════
    # STEP 0: Fix misclassifications
    # ════════════════════════════════════════════════════════════
    if args.fix_misclass:
        print("=== Fixing misclassifications ===")
        # Traditions that don't belong under Islam
        bad_traditions = [
            'Shrine Shinto', 'Protestant', 'Vaishnavism', 'Rabbinic',
            'Mahayana', 'Orthodox', 'Sikh', 'Anglican', 'Catholic',
            'Shaktism', 'Neo-Hindu', 'Buddhist', 'Shaivism', 'jewish',
            'Holiness Churches', 'Muslim'
        ]
        for bt in bad_traditions:
            c.execute("""
                UPDATE churches SET faith='Other', tradition=NULL, taxonomy_id=NULL
                WHERE faith='Islam' AND tradition=? AND muslim_affiliation IS NULL
            """, (bt,))
            if c.rowcount:
                print(f"  {bt:25s}: {c.rowcount:>6,} fixed (faith→Other)")

        # Also fix records with non-Islam muslim_affiliation  
        c.execute("""
            UPDATE churches SET faith='Other'
            WHERE faith='Islam' AND muslim_affiliation IN ('Shrine Shinto','Protestant','Vaishnavism')
        """)
        print(f"  Muslim_affiliation fixes: {c.rowcount:,}")
        db.commit()
        print("  Misclassification fixes applied")

    # ════════════════════════════════════════════════════════════
    # STEP 1: Get unclassified records
    # ════════════════════════════════════════════════════════════
    where = "AND (tradition IS NULL OR tradition = '') AND (muslim_affiliation IS NULL OR muslim_affiliation = '')"
    limit = f"LIMIT {args.limit}" if args.limit else ""

    rows = c.execute(f"""
        SELECT id, name, city, country FROM churches
        WHERE faith = 'Islam'
        {where}
        ORDER BY id
        {limit}
    """).fetchall()

    print(f"\nUnclassified Islam records: {len(rows):,}")
    if args.dry_run:
        print("  DRY RUN - no changes written\n")

    if not rows and not args.fix_misclass:
        print("Nothing to classify!")
        db.close()
        return

    # ════════════════════════════════════════════════════════════
    # STEP 2: Classify by name + country
    # ════════════════════════════════════════════════════════════
    name_matched = 0
    country_matched = 0
    still_unclassified = 0

    updates = []  # (id, tradition, confidence, source)

    with Provenance(db, SCRIPT_NAME, source="muslim_classifier_v2",
                     action="enriched",
                     fields="tradition,muslim_affiliation,muslim_confidence,muslim_classification_source",
                     records_attempted=len(rows)) as prov:

        for r in rows:
            ch_id, name, city, country = r

            # Phase 1: Name-based
            result = classify_by_name(name, city)
            if result:
                tradition, confidence, source = result
                updates.append((ch_id, tradition, confidence, source, 'name'))
                name_matched += 1
                continue

            # Phase 2: Country prior
            result = classify_by_country(country)
            if result:
                tradition, confidence, source = result
                updates.append((ch_id, tradition, confidence, source, 'geo'))
                country_matched += 1
                continue

            still_unclassified += 1

        print(f"\n  Name-based:     {name_matched:>6,}")
        print(f"  Country prior:  {country_matched:>6,}")
        print(f"  Unclassified:   {still_unclassified:>6,}")

        # ════════════════════════════════════════════════════════
        # STEP 3: Apply updates in batches
        # ════════════════════════════════════════════════════════
        if not args.dry_run and updates:
            from datetime import datetime, timezone
            now = datetime.now(timezone.utc).isoformat()

            for i in range(0, len(updates), CHUNK_SIZE):
                batch = updates[i:i + CHUNK_SIZE]
                changes = []

                for ch_id, tradition, confidence, source, method in batch:
                    c.execute("""
                        UPDATE churches SET
                            tradition = ?,
                            muslim_affiliation = ?,
                            muslim_confidence = ?,
                            muslim_classification_source = ?,
                            muslim_updated = ?
                        WHERE id = ?
                    """, (tradition, tradition, confidence, source, now, ch_id))

                    changes.append((ch_id, 'tradition', None, tradition))
                    changes.append((ch_id, 'muslim_affiliation', None, tradition))
                    changes.append((ch_id, 'muslim_confidence', None, str(confidence)))

                log_changes_batch(db, changes, source=SCRIPT_NAME)

                if (i // CHUNK_SIZE) % 5 == 0:
                    db.commit()

                # Progress bar
                pct = min((i + len(batch)) / len(updates) * 100, 100)
                bar = '█' * int(pct / 2) + '░' * (50 - int(pct / 2))
                print(f"\r  [{bar}] {pct:.0f}% ({i + len(batch):,}/{len(updates):,})", end='')

            db.commit()
            print()

            total_classified = name_matched + country_matched
            prov.churches_updated = total_classified
            prov.records_matched = total_classified

    # ════════════════════════════════════════════════════════════
    # REPORT
    # ════════════════════════════════════════════════════════════
    if not args.dry_run:
        print(f"\n{'='*60}")
        rs = c.execute("""
            SELECT tradition, COUNT(*) as cnt,
                   ROUND(AVG(muslim_confidence), 3) as avg_conf
            FROM churches
            WHERE faith='Islam' AND tradition IS NOT NULL AND tradition != ''
            GROUP BY tradition
            ORDER BY cnt DESC
        """).fetchall()
        print(f"{'Tradition':25s} {'Count':>10s} {'Avg Conf':>8s}")
        print('-' * 45)
        total = 0
        for r in rs:
            print(f"{str(r[0] or 'NULL'):25s} {r[1]:>10,} {str(r[2] or 'N/A'):>8s}")
            total += r[1]

        remaining = c.execute("""
            SELECT COUNT(*) FROM churches
            WHERE faith='Islam' AND (tradition IS NULL OR tradition = '')
        """).fetchone()[0]
        print(f"{'TOTAL CLASSIFIED':25s} {total:>10,}")
        print(f"{'STILL UNCLASSIFIED':25s} {remaining:>10,}")
        print(f"{'GRAND TOTAL ISLAM':25s} {total + remaining:>10,}")

    db.close()


if __name__ == '__main__':
    main()
