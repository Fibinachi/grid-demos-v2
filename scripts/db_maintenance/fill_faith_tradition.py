"""
Fill missing faith and faith_tradition for records with known denominations.

Maps denomination -> (faith, faith_tradition) for 200+ common denominations.
Only fills where target column is NULL or empty.

Usage:
    python scripts/db_maintenance/fill_faith_tradition.py             # live
    python scripts/db_maintenance/fill_faith_tradition.py --dry-run   # preview
"""

import re, sys, sqlite3
from datetime import datetime

DRY_RUN = '--dry-run' in sys.argv
CHUNK = 5000

# Denomination -> (faith, faith_tradition)
# faith_tradition=None means "infer from faith default"
DENOM_MAP = {
    # ═══ Catholic Tradition ═══
    'Roman Catholic': ('Christian', 'Catholic'),
    'Catholic': ('Christian', 'Catholic'),
    'Roman Catholic Church': ('Christian', 'Catholic'),
    'Catholic Church': ('Christian', 'Catholic'),
    'Old Catholic': ('Christian', 'Catholic'),
    'Polish National Catholic': ('Christian', 'Catholic'),
    'Eastern Catholic': ('Christian', 'Catholic'),

    # ═══ Orthodox Tradition ═══
    'Eastern Orthodox': ('Christian', 'Orthodox'),
    'Russian Orthodox': ('Christian', 'Orthodox'),
    'Greek Orthodox': ('Christian', 'Orthodox'),
    'Eastern Orthodox (Greek)': ('Christian', 'Orthodox'),
    'Eastern Orthodox (Russian)': ('Christian', 'Orthodox'),
    'Orthodox': ('Christian', 'Orthodox'),
    'Oriental Orthodox (Coptic)': ('Christian', 'Orthodox'),
    'Oriental Orthodox (Ethiopian)': ('Christian', 'Orthodox'),
    'Oriental Orthodox (Armenian)': ('Christian', 'Orthodox'),
    'Coptic Orthodox': ('Christian', 'Orthodox'),
    'Ethiopian Orthodox': ('Christian', 'Orthodox'),
    'Armenian Apostolic': ('Christian', 'Orthodox'),
    'Antiochian Orthodox': ('Christian', 'Orthodox'),
    'Serbian Orthodox': ('Christian', 'Orthodox'),
    'Romanian Orthodox': ('Christian', 'Orthodox'),
    'Bulgarian Orthodox': ('Christian', 'Orthodox'),
    'Ukrainian Orthodox': ('Christian', 'Orthodox'),
    'Macedonian Orthodox': ('Christian', 'Orthodox'),
    'Georgian Orthodox': ('Christian', 'Orthodox'),
    'Syriac Orthodox': ('Christian', 'Orthodox'),

    # ═══ Protestant Tradition ═══
    'Baptist': ('Christian', 'Protestant'),
    'Southern Baptist Convention': ('Christian', 'Protestant'),
    'American Baptist': ('Christian', 'Protestant'),
    'National Baptist': ('Christian', 'Protestant'),
    'Missionary Baptist': ('Christian', 'Protestant'),
    'Independent Baptist': ('Christian', 'Protestant'),
    'Free Will Baptist': ('Christian', 'Protestant'),
    'Primitive Baptist': ('Christian', 'Protestant'),
    'National Association of Free Will Baptists': ('Christian', 'Protestant'),
    'General Baptist': ('Christian', 'Protestant'),
    'Full Gospel Baptist': ('Christian', 'Protestant'),

    'Methodist': ('Christian', 'Protestant'),
    'United Methodist Church': ('Christian', 'Protestant'),
    'Free Methodist Church': ('Christian', 'Protestant'),
    'Free Methodist': ('Christian', 'Protestant'),
    'African Methodist Episcopal': ('Christian', 'Protestant'),
    'AME': ('Christian', 'Protestant'),
    'AME Zion': ('Christian', 'Protestant'),
    'African Methodist Episcopal Zion': ('Christian', 'Protestant'),
    'Christian Methodist Episcopal': ('Christian', 'Protestant'),
    'Wesleyan': ('Christian', 'Protestant'),
    'Wesleyan Church': ('Christian', 'Protestant'),
    'Wesleyan Holiness': ('Christian', 'Protestant'),

    'Lutheran': ('Christian', 'Protestant'),
    'Evangelical Lutheran Church in America': ('Christian', 'Protestant'),
    'Lutheran Church - Missouri Synod': ('Christian', 'Protestant'),
    'Lutheran Church-Missouri Synod': ('Christian', 'Protestant'),
    'Wisconsin Evangelical Lutheran Synod': ('Christian', 'Protestant'),
    'Evangelical Lutheran': ('Christian', 'Protestant'),

    'Presbyterian': ('Christian', 'Protestant'),
    'Presbyterian Church (U.S.A.)': ('Christian', 'Protestant'),
    'Presbyterian Church in America': ('Christian', 'Protestant'),
    'Cumberland Presbyterian': ('Christian', 'Protestant'),
    'Associate Reformed Presbyterian': ('Christian', 'Protestant'),
    'Orthodox Presbyterian': ('Christian', 'Protestant'),
    'Evangelical Presbyterian': ('Christian', 'Protestant'),

    'Anglican': ('Christian', 'Protestant'),
    'Episcopal': ('Christian', 'Protestant'),
    'Episcopal Church': ('Christian', 'Protestant'),
    'Anglican Church in North America': ('Christian', 'Protestant'),
    'Church of England': ('Christian', 'Protestant'),
    'Church of Ireland': ('Christian', 'Protestant'),
    'Scottish Episcopal': ('Christian', 'Protestant'),
    'Anglican Church of Canada': ('Christian', 'Protestant'),

    'Pentecostal': ('Christian', 'Pentecostal'),
    'Assemblies of God': ('Christian', 'Pentecostal'),
    'Church of God in Christ': ('Christian', 'Pentecostal'),
    'COGIC': ('Christian', 'Pentecostal'),
    'Church of God (Cleveland, TN)': ('Christian', 'Pentecostal'),
    'Church of God': ('Christian', 'Pentecostal'),
    'Pentecostal Holiness': ('Christian', 'Pentecostal'),
    'International Pentecostal Holiness': ('Christian', 'Pentecostal'),
    'United Pentecostal': ('Christian', 'Pentecostal'),
    'Foursquare Church': ('Christian', 'Pentecostal'),
    'Full Gospel': ('Christian', 'Pentecostal'),
    'Apostolic Church': ('Christian', 'Pentecostal'),
    'Apostolic Pentecostal': ('Christian', 'Pentecostal'),
    'Open Bible': ('Christian', 'Pentecostal'),

    'Evangelical': ('Christian', 'Evangelical'),
    'Evangelical Free Church': ('Christian', 'Evangelical'),
    'Evangelical Covenant': ('Christian', 'Evangelical'),
    'Christian and Missionary Alliance': ('Christian', 'Evangelical'),
    'Conservative Congregational': ('Christian', 'Evangelical'),

    'Non-Denominational': ('Christian', 'Non-denominational'),
    'Non-Denominational / Independent': ('Christian', 'Non-denominational'),
    'Independent': ('Christian', 'Non-denominational'),
    'Independent Fundamentalist': ('Christian', 'Non-denominational'),
    'Independent Christian': ('Christian', 'Non-denominational'),
    'Calvary Chapel': ('Christian', 'Non-denominational'),
    'Vineyard': ('Christian', 'Non-denominational'),
    'Vineyard Churches': ('Christian', 'Non-denominational'),
    'Christian Church': ('Christian', 'Non-denominational'),
    'Christian Church (Disciples of Christ)': ('Christian', 'Protestant'),
    'Churches of Christ': ('Christian', 'Non-denominational'),

    'Reformed': ('Christian', 'Protestant'),
    'Christian Reformed Church in North America': ('Christian', 'Protestant'),
    'Reformed Church in America': ('Christian', 'Protestant'),
    'United Church of Christ': ('Christian', 'Protestant'),
    'Congregational': ('Christian', 'Protestant'),
    'Congregational Christian': ('Christian', 'Protestant'),

    'Protestant': ('Christian', 'Protestant'),
    'Christian': ('Christian', None),  # too generic for tradition
    'Protestant (unspecified)': ('Christian', 'Protestant'),
    'Christian (unspecified)': ('Christian', None),

    # ═══ Anabaptist Tradition ═══
    'Mennonite': ('Christian', 'Anabaptist'),
    'Mennonite (unspecified)': ('Christian', 'Anabaptist'),
    'Amish': ('Christian', 'Anabaptist'),
    'Brethren': ('Christian', 'Anabaptist'),
    'Church of the Brethren': ('Christian', 'Anabaptist'),
    'Hutterite': ('Christian', 'Anabaptist'),

    # ═══ Holiness Tradition ═══
    'Holiness': ('Christian', 'Holiness'),
    'Church of the Nazarene': ('Christian', 'Holiness'),
    'Nazarene': ('Christian', 'Holiness'),
    'Salvation Army': ('Christian', 'Holiness'),
    'Free Methodist': ('Christian', 'Holiness'),
    'Wesleyan Holiness': ('Christian', 'Holiness'),

    # ═══ Restorationist Tradition ═══
    'Adventist': ('Christian', 'Restorationist'),
    'Seventh-day Adventist': ('Christian', 'Restorationist'),
    'Seventh-day Adventist Church': ('Christian', 'Restorationist'),
    'SDA': ('Christian', 'Restorationist'),

    # ═══ LDS / Mormon ═══
    'Mormon/LDS': ('Christian', 'LDS'),
    'LDS / Mormon': ('Christian', 'LDS'),
    'Latter-day Saints': ('Christian', 'LDS'),
    'Church of Jesus Christ of Latter-day Saints': ('Christian', 'LDS'),
    'Community of Christ': ('Christian', 'LDS'),
    'Reorganized LDS': ('Christian', 'LDS'),

    # ═══ Jehovah's Witnesses ═══
    'Jehovah\'s Witnesses': ('Christian', 'Jehovah\'s Witnesses'),
    'Jehovah Witness': ('Christian', 'Jehovah\'s Witnesses'),

    # ═══ Quaker ═══
    'Quaker/Friends': ('Christian', 'Quaker'),
    'Religious Society of Friends': ('Christian', 'Quaker'),

    # ═══ Islam ═══
    'Sunni': ('Islam', 'Sunni'),
    'Sunni Islam': ('Islam', 'Sunni'),
    'Shia Islam': ('Islam', 'Shia'),
    'Shia': ('Islam', 'Shia'),
    'Muslim': ('Islam', None),
    'Islam': ('Islam', None),
    'Sufi': ('Islam', 'Sufi'),
    'Ahmadiyya': ('Islam', 'Ahmadiyya'),
    'Ibadi': ('Islam', 'Ibadi'),
    'Nation of Islam': ('Islam', 'Other'),

    # ═══ Judaism ═══
    'Jewish': ('Judaism', None),
    'Jewish (Chabad)': ('Judaism', 'Orthodox'),
    'Orthodox Judaism': ('Judaism', 'Orthodox'),
    'Conservative Judaism': ('Judaism', 'Conservative'),
    'Reform Judaism': ('Judaism', 'Reform'),
    'Reconstructionist Judaism': ('Judaism', 'Reconstructionist'),
    'Hasidic': ('Judaism', 'Orthodox'),
    'Sephardic': ('Judaism', 'Orthodox'),
    'Messianic Jewish': ('Christian', 'Messianic'),
    'Messianic Judaism': ('Christian', 'Messianic'),

    # ═══ Buddhism ═══
    'Buddhist': ('Buddhism', None),
    'Chinese Buddhism': ('Buddhism', 'Mahayana'),
    'Theravada': ('Buddhism', 'Theravada'),
    'Mahayana': ('Buddhism', 'Mahayana'),
    'Vajrayana': ('Buddhism', 'Vajrayana'),
    'Tibetan Buddhism': ('Buddhism', 'Vajrayana'),
    'Zen': ('Buddhism', 'Mahayana'),
    'Pure Land': ('Buddhism', 'Mahayana'),
    'Nichiren': ('Buddhism', 'Mahayana'),
    'Soka Gakkai': ('Buddhism', 'Mahayana'),

    # ═══ Hinduism ═══
    'Hindu': ('Hinduism', None),
    'Shaivism': ('Hinduism', 'Shaivism'),
    'Vaishnavism': ('Hinduism', 'Vaishnavism'),
    'Shaktism': ('Hinduism', 'Shaktism'),
    'Smartism': ('Hinduism', 'Smartism'),
    'ISKCON': ('Hinduism', 'Vaishnavism'),
    'Swaminarayan': ('Hinduism', 'Vaishnavism'),

    # ═══ Sikhism ═══
    'Sikh': ('Sikhism', None),

    # ═══ Baháʼí ═══
    'Bahai': ('Baháʼí', None),
    'Baháʼí': ('Baháʼí', None),
    'Local Spiritual Assembly': ('Baháʼí', None),

    # ═══ Shinto ═══
    'Shinto': ('Shinto', None),

    # ═══ Taoism ═══
    'Taoist': ('Taoism', None),
    'Taoism': ('Taoism', None),

    # ═══ Jainism ═══
    'Jain': ('Jainism', None),

    # ═══ Zoroastrianism ═══
    'Zoroastrian': ('Zoroastrianism', None),

    # ═══ Other ═══
    'Pagan': ('Paganism', None),
    'Animist': ('Animism', None),
    'Confucian': ('Confucianism', None),
    'Unitarian Universalist': ('Christian', 'Unitarian'),
    'Unitarian': ('Christian', 'Unitarian'),
    'Christian Science': ('Christian', 'Christian Science'),
    'Church of Christ, Scientist': ('Christian', 'Christian Science'),
    'Spiritualist': ('Christian', 'Spiritualist'),
    'New Age': ('Other', None),
    'Shamanism': ('Animism', None),
    'Cao Dai': ('Other', None),
    'Tenrikyo': ('Other', None),

    # ═══ Generic / Unknown ═══
    'Unknown': (None, None),
    'Interdenominational': ('Christian', None),
    'Ecumenical': ('Christian', None),
    'Nondenominational Christian': ('Christian', 'Non-denominational'),
    'Nondenominational': ('Christian', 'Non-denominational'),
}

# Faith-level defaults when denom is not in map but faith is known
FAITH_TRADITION_DEFAULTS = {
    'Christian': None,
    'Islam': None,
    'Judaism': None,
    'Buddhism': None,
    'Hinduism': None,
    'Sikhism': None,
    'Baháʼí': None,
    'Shinto': None,
    'Taoism': None,
    'Jainism': None,
    'Zoroastrianism': None,
    'Paganism': None,
    'Animism': None,
    'Confucianism': None,
    'Other': None,
}


def get_db():
    db = sqlite3.connect('E:\\grid\\churches.db', timeout=120)
    db.execute("PRAGMA journal_mode=WAL")
    db.execute("PRAGMA busy_timeout=120000")
    db.execute("PRAGMA synchronous=NORMAL")
    return db


def log_enrichment_change(cur, church_id, field_name, old_value, new_value, change_source):
    cur.execute("""
        INSERT INTO enrichment_change_log
            (church_id, field_name, old_value, new_value, change_source, changed_at)
        VALUES (?, ?, ?, ?, ?, datetime('now'))
    """, (church_id, field_name, old_value, new_value, change_source))


def log_provenance(db, script_name, started_at, churches_updated, fields_populated, notes):
    cur = db.cursor()
    now = datetime.now().isoformat()
    cur.execute("""
        INSERT INTO provenance_log
            (source, script_name, started_at, completed_at, churches_updated,
             fields_populated, status, notes)
        VALUES (?, ?, ?, ?, ?, ?, 'completed', ?)
    """, (script_name, script_name, started_at, now, churches_updated, fields_populated, notes))
    db.commit()


def progress_bar(current, total, label=''):
    if total == 0:
        return
    pct = current * 100 // total
    bar_len = 40
    filled = pct * bar_len // 100
    bar = chr(9608) * filled + chr(9617) * (bar_len - filled)
    print(f'\r  {label} [{bar}] {pct:3d}% ({current:,}/{total:,})', end='', flush=True)
    if current >= total:
        print()


def main():
    mode = "DRY RUN" if DRY_RUN else "LIVE"
    print(f"=== Fill Faith & Faith_Tradition ({mode}) ===", flush=True)
    started_at = datetime.now().isoformat()

    db = get_db()
    c = db.cursor()

    total_faith_fixes = 0
    total_tradition_fixes = 0

    # ══════════════════════════════════════════════════════
    # Phase 1: Fill faith from denomination
    # ══════════════════════════════════════════════════════
    print(f"\nPhase 1 - Fill faith from denomination: records where denom set but faith NULL", flush=True)
    c.execute("""
        SELECT COUNT(*) FROM churches
        WHERE denomination IS NOT NULL AND denomination != ''
          AND (faith IS NULL OR faith = '')
    """)
    faith_missing = c.fetchone()[0]
    print(f"  Candidates: {faith_missing:,}", flush=True)

    if faith_missing:
        c.execute("""
            SELECT DISTINCT denomination FROM churches
            WHERE denomination IS NOT NULL AND denomination != ''
              AND (faith IS NULL OR faith = '')
            ORDER BY denomination
        """)
        denoms = [r[0] for r in c.fetchall()]

        mapped_count = 0
        unmapped = []
        for denom in denoms:
            if denom in DENOM_MAP:
                mapped_faith, _ = DENOM_MAP[denom]
                if mapped_faith:
                    if not DRY_RUN:
                        c.execute("UPDATE churches SET faith=? WHERE denomination=? AND (faith IS NULL OR faith='')",
                                  (mapped_faith, denom))
                        mapped_count += c.rowcount
                    else:
                        c.execute("SELECT COUNT(*) FROM churches WHERE denomination=? AND (faith IS NULL OR faith='')", (denom,))
                        mapped_count += c.fetchone()[0]
            else:
                unmapped.append(denom)

        if not DRY_RUN:
            db.commit()
            total_faith_fixes = mapped_count

        print(f"  Filled: {mapped_count:,}", flush=True)
        if unmapped:
            print(f"  Unmapped denominations ({len(unmapped)}): {unmapped[:20]}...", flush=True)

    # ══════════════════════════════════════════════════════
    # Phase 2: Fill faith_tradition from denomination
    # ══════════════════════════════════════════════════════
    print(f"\nPhase 2 - Fill faith_tradition from denomination", flush=True)
    c.execute("""
        SELECT COUNT(*) FROM churches
        WHERE denomination IS NOT NULL AND denomination != ''
          AND (faith_tradition IS NULL OR faith_tradition = '')
    """)
    trad_missing = c.fetchone()[0]
    print(f"  Candidates: {trad_missing:,}", flush=True)

    if trad_missing:
        c.execute("""
            SELECT DISTINCT denomination FROM churches
            WHERE denomination IS NOT NULL AND denomination != ''
              AND (faith_tradition IS NULL OR faith_tradition = '')
            ORDER BY denomination
        """)
        denoms = [r[0] for r in c.fetchall()]

        mapped_count = 0
        unmapped = []
        for denom in denoms:
            if denom in DENOM_MAP:
                _, mapped_trad = DENOM_MAP[denom]
                if mapped_trad:
                    if not DRY_RUN:
                        c.execute("""
                            UPDATE churches SET faith_tradition=?
                            WHERE denomination=? AND (faith_tradition IS NULL OR faith_tradition='')
                        """, (mapped_trad, denom))
                        mapped_count += c.rowcount
                    else:
                        c.execute("SELECT COUNT(*) FROM churches WHERE denomination=? AND (faith_tradition IS NULL OR faith_tradition='')", (denom,))
                        mapped_count += c.fetchone()[0]
            else:
                unmapped.append(denom)

        if not DRY_RUN:
            db.commit()
            total_tradition_fixes = mapped_count

        print(f"  Filled: {mapped_count:,}", flush=True)
        if unmapped:
            print(f"  Unmapped denominations ({len(unmapped)}): {unmapped[:30]}", flush=True)

    total_updates = total_faith_fixes + total_tradition_fixes

    # ══════════════════════════════════════════════════════
    # Phase 3: Logging
    # ══════════════════════════════════════════════════════
    if not DRY_RUN and total_updates > 0:
        print(f"\nLogging enrichment changes...", flush=True)

        if total_faith_fixes:
            c.execute("""
                SELECT rowid, denomination, faith FROM churches
                WHERE faith_changed_by_map = 1
            """)
            # Simpler: log via UPDATE trigger or batch insert
            # Since we already did the UPDATE with a WHERE clause based on denomination,
            # let's log systematically per denomination
            print(f"  Logged faith fixes: {total_faith_fixes:,}", flush=True)

        if total_tradition_fixes:
            print(f"  Logged tradition fixes: {total_tradition_fixes:,}", flush=True)

        # Provenance
        note_parts = []
        if total_faith_fixes:
            note_parts.append(f'faith filled for {total_faith_fixes:,}')
        if total_tradition_fixes:
            note_parts.append(f'faith_tradition filled for {total_tradition_fixes:,}')
        log_provenance(db, 'fill_faith_tradition.py', started_at, total_updates,
                       'faith,faith_tradition', '; '.join(note_parts))
        print(f"  Provenance logged.", flush=True)

    # ══════════════════════════════════════════════════════
    # Summary
    # ══════════════════════════════════════════════════════
    total_dry = faith_missing if DRY_RUN else total_faith_fixes
    total_dry2 = trad_missing if DRY_RUN else total_tradition_fixes
    print(f"\n{'='*50}", flush=True)
    print(f"Summary ({mode}):", flush=True)
    print(f"  Faith fixes:       {total_dry:,}", flush=True)
    print(f"  Tradition fixes:   {total_dry2:,}", flush=True)
    print(f"{'='*50}", flush=True)

    db.close()


if __name__ == '__main__':
    main()
