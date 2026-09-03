"""
Classify Bible Student / JW splinter groups from existing data + web scrape plan.

Taxonomy targets (all under Jehovah's Witnesses id=16):
  Bible Student Movement (id=678)
    Dawn Bible Students Association (679)
    Pastoral Bible Institute (680)
    Associated Bible Students (681)
    Free Bible Students (682)
    New Covenant Bible Students (683)
    Standfast Bible Students (684)
    Epiphany Bible Students (685)
    Bible Student (other) (686)
  Independent Jehovah's Witnesses (id=687)
    Christian Millennial Fellowship (688)
    Reform Jehovah's Witnesses (689)
    True Faith Jehovah's Witnesses (690)
    Friends of the Kingdom (691)
  JW-Derived Hybrid Groups (id=692)
    Servants of Yahweh (693)
    Yahweh's Assembly (694)

Usage:
  python scripts/enrichment/_classify_jw_splinters.py          # classify existing data
  python scripts/enrichment/_classify_jw_splinters.py --dry-run  # preview only
  python scripts/enrichment/_classify_jw_splinters.py --scrape-plan  # print scrape targets
"""

import sys
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from gw_db import connect

db = connect()

# ── Smart name patterns ──────────────────────────────────────────────
# Each pattern is (LIKE string, target_taxonomy_id, confidence)
# Order matters: more specific patterns first to avoid false positives

RULES = [
    # ── Dawn Bible Students ──
    ('%dawn bible student%', 679, 0.90),
    ('%dawn bible students association%', 679, 0.95),
    # ── Pastoral Bible Institute ──
    ('%pastoral bible institute%', 680, 0.95),
    # ── Associated Bible Students ──
    ('%associated bible students of %', 681, 0.90),
    ('%associated bible students%', 681, 0.85),
    # ── Free Bible Students ──
    ('%free bible student%', 682, 0.85),
    ('%freie bibelforscher%', 682, 0.90),  # German
    # ── New Covenant Bible Students (NOT "New Covenant Bible Church" or generic "Fellowship"!) ──
    ('%new covenant bible student%', 683, 0.90),
    ('%new covenant believers%', 683, 0.85),
    # Note: '%new covenant fellowship%' excluded — overwhelmingly generic Evangelical churches
    # ── Standfast ──
    ('%stand fast bible%', 684, 0.95),
    ('%standfast bible%', 684, 0.95),
    # ── Epiphany Bible Students ──
    ('%epiphany bible student%', 685, 0.95),
    ('%laymen%home missionary%', 685, 0.90),  # LHMM → Epiphany splinter
    # ── Bible Student (catch-all) ──
    ('%bible student%ecclesia%', 686, 0.85),
    ('%bible students ecclesia%', 686, 0.85),
    ('%bible student%class%', 686, 0.80),
    ('%international bible students association%', 686, 0.80),
    ('%bible student church%', 686, 0.75),
    ('%bible students church%', 686, 0.75),
    # ── Christian Millennial Fellowship ──
    ('%christian millennial fellowship%', 688, 0.95),
    ('%christian discipling ministries%', 688, 0.90),  # CMF renamed to CDMI
    # ── Reform Jehovah's Witnesses ──
    ('%reform jehovah%witness%', 689, 0.95),
    # ── True Faith Jehovah's Witnesses ──
    ('%true faith jehovah%', 690, 0.95),
    ('%theocratic organization of jehovah%', 690, 0.90),  # Russian splinter
    # ── Friends of the Kingdom ──
    ('%friends of the kingdom%', 691, 0.90),
    # ── Servants of Yahweh ──
    ('%servants of yahweh%', 693, 0.90),
    # ── Yahweh's Assembly ──
    ('%yahweh%assembly in messiah%', 694, 0.90),
    ('%yahweh%s assembly%', 694, 0.80),
    # ── Berean Bible Students (distinct from Berean Bible Church!) ──
    ('%berean bible student%', 681, 0.85),  # Berean Bible Institute (AU) → Associated
    # ── Chicago Bible Students ──
    ('%chicago bible student%', 681, 0.90),
]

# ── Exclusion patterns (these are NOT Bible Student groups) ──
NOT_BS = [
    '%berean bible church%',      # Evangelical
    '%berean bible fellowship%',  # Baptist/Evangelical
    '%new covenant bible church%', # Evangelical
    '%new covenant bible college%',
    '%new covenant fellowship%',  # generic Evangelical, not JW splinter
    '%new covenant fellowship church%',
    '%new covenant fellowship baptist%',
    '%new covenant fellowship pentecostal%',
    '%new covenant fellowship independent%',
    '%new covenant fellowship undenominational%',
    '%bible student fellowship%',  # generic, not BS movement
    '%bible student union%',
    '%bible student missionary%',
    '%bible student movement%',   # meta-reference
    '%bible student ministries%',
    '%bible student convention%',
]

def is_excluded(name: str) -> bool:
    """Check if a church name matches exclusion patterns (false positives)."""
    name_lower = name.lower()
    for pat in NOT_BS:
        # Convert SQL LIKE pattern to simple substring check
        clean = pat.replace('%', '').strip()
        if clean and clean in name_lower:
            return True
    return False


def classify_existing(dry_run: bool = False):
    """Find and classify existing churches matching JW splinter patterns."""
    seen = {}  # church_id -> (name, city, country, current_tax, target_tax, confidence)
    already_correct = 0
    excluded = 0

    for pattern, target_tax, confidence in RULES:
        rows = db.execute('''
            SELECT id, name, city, country, taxonomy_id
            FROM churches
            WHERE LOWER(name) LIKE ?
            ORDER BY id
        ''', (pattern,)).fetchall()

        for row in rows:
            church_id, name, city, country, current_tax = row

            # Skip already classified correctly
            if current_tax == target_tax:
                already_correct += 1
                continue

            # Skip if matches exclusion pattern
            if is_excluded(name):
                excluded += 1
                continue

            # Deduplicate: keep highest confidence match per church
            if church_id in seen:
                if confidence > seen[church_id][5]:
                    seen[church_id] = (name, city, country, current_tax, target_tax, confidence)
                continue

            seen[church_id] = (name, city, country, current_tax, target_tax, confidence)

    changes = [(cid,) + data for cid, data in seen.items()]

    print(f'Found {len(changes)} churches to reclassify')
    print(f'  Already correct: {already_correct}')
    print(f'  Excluded (false positives): {excluded}')
    print()

    if not changes:
        return

    # Show preview
    print('=== Reclassification preview ===')
    for church_id, name, city, country, current_tax, target_tax, confidence in changes[:30]:
        cur_name = db.execute('SELECT name FROM taxonomy WHERE id=?', (current_tax,)).fetchone()
        new_name = db.execute('SELECT name FROM taxonomy WHERE id=?', (target_tax,)).fetchone()
        cur_label = cur_name[0] if cur_name else f'id={current_tax}'
        new_label = new_name[0] if new_name else f'id={target_tax}'
        print(f'  #{church_id} {name[:60]} | {city or "?"}, {country or "?"}')
        print(f'         {cur_label} → {new_label}  ({confidence:.0%})')

    if len(changes) > 30:
        print(f'  ... and {len(changes)-30} more')

    if dry_run:
        print(f'\nDRY RUN — no changes made. Remove --dry-run to apply.')
        return

    # Apply changes
    print(f'\nApplying {len(changes)} reclassifications...')
    chunk_size = 500
    for i in range(0, len(changes), chunk_size):
        batch = changes[i:i+chunk_size]
        db.execute('BEGIN')
        for church_id, name, city, country, current_tax, target_tax, confidence in batch:
            db.execute('UPDATE churches SET taxonomy_id=? WHERE id=?', (target_tax, church_id))
        db.execute('COMMIT')
        print(f'  Committed batch {i//chunk_size + 1}: {len(batch)} rows')

    print(f'Done. {len(changes)} churches reclassified.')


def print_scrape_plan():
    """Print web scrape targets for each JW splinter group."""
    targets = [
        (679, 'Dawn Bible Students Association',
         'https://www.dawnbible.com/',
         'Radio/TV program reach: US, Canada, South America, Europe, Africa, Asia. '
         'Australian work via Berean Bible Institute (Melbourne). '
         'Canadian work via Canadian Bible Students. Look for ecclesia/convention listings.'),
        (680, 'Pastoral Bible Institute',
         'https://www.heraldmag.org/',
         'Publishes The Herald of Christ\'s Kingdom. Congregations are independent "Associated Bible Students" classes. '
         'No central directory — look for convention announcements and class listings in the magazine.'),
        (681, 'Associated Bible Students',
         'https://www.biblestudents.com/',
         'Lists congregations worldwide. Also check biblestudents.net, internationalbiblestudents.com. '
         'Most congregations meet in rented facilities. Key hubs: Central Ohio, Brooklyn NY, Chicago, Detroit.'),
        (682, 'Free Bible Students',
         'https://www.bbschurch.org/ (Berean Bible Students Church, Lombard IL)',
         'German: Freie Bibelforscher. European congregations post-WWII. '
         'Also Christian Discipling Ministries International (cmfellowship.us — Somersworth NH, Port Orange FL).'),
        (683, 'New Covenant Bible Students',
         'https://en.wikipedia.org/wiki/Free_Bible_Students#New_Covenant_Believers',
         'Small group descended from 1909 schism. Published The Kingdom Scribe until 1975. '
         'Now known as Berean Bible Students Church in Lombard, IL. Also New Covenant Fellowship (Australia).'),
        (684, 'Standfast Bible Students',
         None,
         'Founded Portland OR 1918 by Charles Heard. Pacifist splinter. '
         'Mostly historical — membership dwindled. Elijah Voice Society splinter (1923).'),
        (685, 'Epiphany Bible Students',
         None,
         'Laymen\'s Home Missionary Movement (LHMM) founded by Paul S.L. Johnson 1919. '
         'After Johnson\'s death (1950): Epiphany Bible Students Association + Laodicean Home Missionary Movement. '
         'Small congregations in US and Europe.'),
        (688, 'Christian Millennial Fellowship',
         'https://cmfellowship.us/',
         '36 Chapel Lane, Somersworth NH 03878. Also 6156 Shoreline Drive, Port Orange FL 32127. '
         'Now known as Christian Discipling Ministries International (CDMI). Publishes The New Creation since 1940.'),
        (689, 'Reform Jehovah\'s Witnesses',
         None,
         'Various small independent groups rejecting disfellowshipping and centralized authority. '
         'No central directory. Look for ex-JW community forums, Reddit r/exjw, Facebook groups.'),
        (690, 'True Faith Jehovah\'s Witnesses',
         'https://www.acami.ro/despre (Romanian)',
         'Romanian breakaway (1992). Also Theocratic Organization of Jehovah\'s Witnesses in Russia/Ukraine/Moldova. '
         'Website: the-true-jw.oltenia.ro (archived).'),
        (691, 'Friends of the Kingdom',
         None,
         'Small independent group. Also "Friends of Man" (Switzerland, Alexander Freytag 1920). '
         'Published The Monitor of the Reign of Justice and Paper for All.'),
        (693, 'Servants of Yahweh',
         None,
         'Hybrid JW + Sacred Name movement. Independent congregations. '
         'One known: Servants Of Yahweh Covenant Community, SS2, Malaysia (already in DB).'),
        (694, "Yahweh's Assembly",
         None,
         'Hybrid groups combining JW eschatology with Sacred Name theology. '
         'Some in DB: Yahwehs Assembly in Messiah (Comodoro Rivadavia), Yahweh\'s Frystown Assembly (Myerstown PA).'),
    ]

    print('=== Web Scrape Targets for JW Splinter Groups ===')
    print()
    for tax_id, name, url, notes in targets:
        print(f'── {name} (tax_id={tax_id}) ──')
        if url:
            print(f'   URL: {url}')
        else:
            print(f'   URL: (no central website — use web search)')
        print(f'   Notes: {notes}')
        print()


if __name__ == '__main__':
    if '--scrape-plan' in sys.argv:
        print_scrape_plan()
    elif '--dry-run' in sys.argv:
        classify_existing(dry_run=True)
    else:
        classify_existing(dry_run=False)
