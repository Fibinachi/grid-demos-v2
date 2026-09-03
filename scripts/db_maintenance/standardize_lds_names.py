"""
LDS Name Normalizer — Standardize all LDS church names to canonical forms.
Groups by unique name patterns for efficiency, then batch-updates all matching rows.

Usage:
    python scripts/db_maintenance/standardize_lds_names.py              # run for real
    python scripts/db_maintenance/standardize_lds_names.py --dry-run    # preview only

Rules:
    - Only modifies churches with LDS-branch taxonomy_ids
    - Meetinghouse (generic): "The Church of Jesus Christ of Latter-day Saints"
    - Stake center: "LDS Stake Center — [Name]"
    - Temple: "LDS Temple — [Location]" (mostly done by _fix_lds_temple_names.py)
    - Seminary: "LDS Seminary — [Name/Location]"
    - Institute: "LDS Institute of Religion — [Location]"
    - Employment center: "LDS Employment Resource Center — [Location]"
    - Family history center: "LDS Family History Center — [Location]"
    - Mission office: "LDS Mission Office — [Mission Name]"
    - Storehouse: "LDS Bishops' Storehouse — [Location]"
    - Area office: "Corporation of the Presiding Bishop — [Location]"
    - HQ: "LDS Church Headquarters"
    - Normalizes non-English names (Spanish, Portuguese, French, etc.)
"""

import sqlite3, re, sys
from datetime import datetime

CHUNK = 500

# ── LDS taxonomy IDs ──────────────────────────────────────────────────
# All IDs under the "Latter-day Saints" branch (id=17)
LDS_TAXONOMY_IDS = (
    17, 166, 167, 168, 169, 170, 171, 172,   # Mainline LDS variants
    458, 459, 460,                             # FLDS, LDS, Other LDS
    585, 586, 587, 588, 589, 590, 591, 592, 593, 594, 595, 596,  # Restorationist
)

# IDs that are Community of Christ (not mainline LDS — keep as-is)
COC_IDS = (167, 585, 586, 587, 588, 589, 590, 591, 592, 593, 594, 595, 596)

# IDs that are mainline LDS
MAINLINE_IDS = (166, 168, 169, 170, 171, 172, 17)

# IDs that are FLDS
FLDS_IDS = (458,)


def fix_apostrophes(s):
    """Normalize unicode apostrophes and quotes."""
    s = s.replace('\u2019', "'").replace('\u2018', "'").replace('\u201a', "'").replace('\u201b', "'")
    s = s.replace('\u00c6', "'").replace('\u00e6', "'")
    s = s.replace('\u00b4', "'").replace('\u02bc', "'")
    return s


def is_mainline_lds(taxonomy_id):
    """Check if taxonomy_id is mainline LDS (not Community of Christ, FLDS, etc.)."""
    return taxonomy_id in MAINLINE_IDS or taxonomy_id == 17


def normalize_name_pattern(name, has_city, hierarchy_info):
    """
    Determine the canonical form for one unique name pattern.
    
    Args:
        name: Current church name
        has_city: Whether the churches with this name have city values
        hierarchy_info: Dict with lds_type, lds_detail, and city/state/country if available
                        (populated from lds_hierarchy for entries that have it)
    
    Returns:
        (canonical_name, backfill_city_or_None)
    """
    orig = name
    name = fix_apostrophes(name)
    low = name.lower().strip()
    up = name.upper().strip()
    
    lds_type = hierarchy_info.get('lds_type')
    lds_detail = hierarchy_info.get('lds_detail')
    h_city = hierarchy_info.get('city')
    h_state = hierarchy_info.get('state')
    h_country = hierarchy_info.get('country')
    
    # ── Helpers ──
    def build_location(default_city=None):
        """Build a location string from available info."""
        parts = []
        city = default_city or h_city
        if city and city != 'None' and city.strip():
            parts.append(city.strip())
        if h_state and h_state != 'None' and h_state.strip():
            st = h_state.strip()
            if parts and st in parts[-1]:
                pass  # already included
            else:
                parts.append(st)
        if parts:
            return ', '.join(parts)
        if h_country and h_country != 'None':
            return h_country
        return None
    
    def extract_city_from_name(text, keywords_to_remove):
        """Extract a city/location prefix from the name."""
        for kw in keywords_to_remove:
            # Find keyword position (case-insensitive)
            idx = text.lower().find(kw.lower())
            if idx >= 0:
                prefix = text[:idx].strip().rstrip('- ,;:()\u2014').strip()
                # Clean up prefix
                prefix = re.sub(r'\b(LDS|MORMON|LATTER[\-\s]DAY|SAINTS?)\b', '', prefix, flags=re.IGNORECASE).strip()
                prefix = re.sub(r'[,\-:\s]+$', '', prefix).strip()
                prefix = re.sub(r'^[,\-:\s]+', '', prefix).strip()
                if prefix and len(prefix) > 1 and prefix.lower() not in ('the', 'a', 'an', 'of', 'in', 'at'):
                    return prefix
        return None
    
    # ── PHASE 1: FLDS — keep as-is ──
    if 'flds' in low or 'fundamentalist' in low:
        return name, None
    
    # ── PHASE 2: Community of Christ / RLDS / Restorationist — keep recognizable ──
    coc_patterns = [
        'community of christ', 'reorganized church', 'reorg',
        'remnant church', 'bickertonite', 'cutlerite', 'strangite',
        'temple lot', 'hedrickite', 'church of the firstborn',
        'righteous branch', 'centennial park', 'apostolic united brethren',
        'true and living church', 'independent fundamentalist',
        'restoration branch',
    ]
    is_coc = any(p in low for p in coc_patterns)
    if is_coc:
        # Still normalize capitalization
        if low.startswith('reorg ch of jesus christ lds'):
            return 'Reorganized Church of Jesus Christ of Latter Day Saints', None
        if low.startswith('community of christ'):
            return 'Community of Christ', None
        return name, None  # Keep as-is for restorationist groups
    
    # ── PHASE 3: Non-English translation ──
    
    # Spanish
    spanish_jesucristo = ('iglesia de jesucristo' in low or 
                          'la iglesia de jesucristo' in low)
    # Normalize accents for matching
    low_normalized = low.replace('\u00fa', 'u').replace('\u00ed', 'i').replace('\u00f3', 'o').replace('\u00e1', 'a').replace('\u00e9', 'e')
    spanish_sud = 'santos de los ultimos dias' in low_normalized
    
    if spanish_jesucristo and spanish_sud:
        # Extract city/location prefix if present
        prefix = None
        for marker in ['iglesia de jesucristo', 'la iglesia de jesucristo']:
            idx = low.find(marker)
            if idx > 0:
                prefix = name[:idx].strip().rstrip('- ,;:').strip()
                # Clean prefix — remove Spanish definite articles and church terms
                prefix = re.sub(r'^(iglesia|capilla|capella|centro|la|el|las|los)\s+', '', prefix, flags=re.IGNORECASE).strip()
                if prefix and len(prefix) > 1 and prefix.lower() not in ('la', 'el', 'las', 'los'):
                    break
                else:
                    prefix = None  # "La" is just the article, not a location
        
        canonical = 'La Iglesia de Jesucristo de los Santos de los Últimos Días'
        if prefix:
            return f'{canonical} — {prefix.title()}', prefix.title() if not has_city else None
        return canonical, None
    
    # "Iglesia Mormona" / "Templo Mormon" -> canonical
    if 'iglesia mormona' in low or 'templo mormon' in low or 'mormon' in low and 'iglesia' in low:
        return 'La Iglesia de Jesucristo de los Santos de los Últimos Días', None
    
    # Portuguese
    if 'igreja de jesus cristo' in low and ('santos' in low and 'ultimos' in low):
        return 'A Igreja de Jesus Cristo dos Santos dos Últimos Dias', None
    
    # French
    if ('église de jésus-christ' in low or 'eglise de jesus-christ' in low) and 'saints' in low:
        return "L'Église de Jésus-Christ des Saints des Derniers Jours", None
    
    # German
    if 'kirche jesu christi' in low and 'heiligen' in low:
        return 'Kirche Jesu Christi der Heiligen der Letzten Tage', None
    
    # Italian
    if 'chiesa di gesù cristo' in low and 'santi' in low:
        return 'La Chiesa di Gesù Cristo dei Santi degli Ultimi Giorni', None
    
    # ── PHASE 4: Type-specific patterns from hierarchy ──
    
    if lds_type == 'stake_house':
        # Extract stake name from "WOODS CROSS STAKE CENTER" → "LDS Stake Center — Woods Cross"
        stake_name = extract_city_from_name(name, ['stake center', 'stake centre', 'stake'])
        if not stake_name:
            stake_name = extract_city_from_name(name, ['the church of jesus christ'])
        if stake_name:
            stake_name = stake_name.strip().title()
            return f'LDS Stake Center — {stake_name}', None
        loc = build_location()
        if loc:
            return f'LDS Stake Center — {loc}', None
        return 'LDS Stake Center', None
    
    if lds_type == 'temple':
        # Already handled by _fix_lds_temple_names.py, but catch stragglers
        temple_loc = extract_city_from_name(name, ['temple', 'lds temple', 'mormon temple'])
        if temple_loc and len(temple_loc) > 2:
            temple_loc = temple_loc.strip().title()
            return f'LDS Temple — {temple_loc}', None
        loc = build_location()
        if loc:
            return f'LDS Temple — {loc}', None
        return name, None  # Can't determine location
    
    if lds_type == 'seminary':
        sem_name = extract_city_from_name(name, ['seminary', 'lds seminary'])
        if sem_name and len(sem_name) > 1:
            return f'LDS Seminary — {sem_name.strip().title()}', None
        loc = build_location()
        if loc:
            return f'LDS Seminary — {loc}', None
        return 'LDS Seminary', None
    
    if lds_type == 'institute':
        inst_name = extract_city_from_name(name, ['institute of religion', 'institute'])
        if inst_name and len(inst_name) > 1:
            return f'LDS Institute of Religion — {inst_name.strip().title()}', None
        loc = build_location()
        if loc:
            return f'LDS Institute of Religion — {loc}', None
        return 'LDS Institute of Religion', None
    
    if lds_type == 'employment_center':
        loc = extract_city_from_name(name, ['employment', 'latter-day saint employment', 
                                              'lds employment', 'employment resource'])
        if loc and len(loc) > 1:
            return f'LDS Employment Resource Center — {loc.strip().title()}', None
        loc = build_location()
        if loc:
            return f'LDS Employment Resource Center — {loc}', None
        return 'LDS Employment Resource Center', None
    
    if lds_type == 'family_history_center':
        loc = extract_city_from_name(name, ['family history', 'lds family'])
        if loc and len(loc) > 1:
            return f'LDS Family History Center — {loc.strip().title()}', None
        loc = build_location()
        if loc:
            return f'LDS Family History Center — {loc}', None
        return 'LDS Family History Center', None
    
    if lds_type == 'mission_office':
        mission_name = extract_city_from_name(name, ['mission office', 'mission'])
        if mission_name and len(mission_name) > 1:
            return f'LDS Mission Office — {mission_name.strip().title()}', None
        loc = build_location()
        if loc:
            return f'LDS Mission Office — {loc}', None
        return 'LDS Mission Office', None
    
    if lds_type == 'storehouse':
        loc = build_location()
        if loc:
            return f"LDS Bishops' Storehouse — {loc}", None
        return "LDS Bishops' Storehouse", None
    
    if lds_type == 'area_office':
        # Corporation of the Presiding Bishop
        return 'Corporation of the Presiding Bishop of The Church of Jesus Christ of Latter-day Saints', None
    
    if lds_type == 'hq':
        return 'LDS Church Headquarters', None
    
    # ── PHASE 5: Generic meetinghouse patterns ──
    
    # Canonical form
    CANONICAL = 'The Church of Jesus Christ of Latter-day Saints'
    
    # "Church of Jesus Christ of Latter-day Saints" (without "The") → add "The"
    if low == 'church of jesus christ of latter-day saints':
        return CANONICAL, None
    
    # Title Case variant: "Church Of Jesus Christ Of Latter-Day Saints"
    if low == 'church of jesus christ of latter-day saints':
        return CANONICAL, None  # Already handled above (with hyphen)
    
    # "CHURCH OF JESUS CHRIST OF LATTER-DAY SAINTS" → canonical
    if low == 'church of jesus christ of latter-day saints':
        return CANONICAL, None
    
    # "Church of Jesus Christ of Latter Day Saints" (missing hyphen)
    if low == 'church of jesus christ of latter day saints':
        return CANONICAL, None
    
    # "Church of Jesus Christ of Latter-Day Saints" (inconsistent hyphen)
    if low == 'church of jesus christ of latter-day saints':
        return CANONICAL, None
    
    # "CHURCH OF JESUS CHRIST OF LATTER DAY SAINTS" (UPPERCASE, no hyphen)
    if low == 'church of jesus christ of latter day saints':
        return CANONICAL, None
    
    # "Church Of Latter Day Saints" (missing "Jesus Christ")
    if low in ('church of latter day saints', 'church of latter-day saints'):
        return CANONICAL, None
    
    # "Church of Jesus Christ of Latter-day Saints Church" (redundant "Church")
    if low == 'church of jesus christ of latter-day saints church':
        return CANONICAL, None
    
    # "Church - Jesus Christ - Lds"
    if low == 'church - jesus christ - lds':
        return CANONICAL, None
    
    # "Mormon" standalone
    if low.strip() == 'mormon':
        return CANONICAL, None
    
    # "CHURCH OF JESUS CHRIST OF LDS" → canonical (LDS is redundant)
    if low == 'church of jesus christ of lds':
        return CANONICAL, None
    

    # "Church Of Jesus CHRIST-Lds" → canonical
    if low == 'church of jesus christ-lds':
        return CANONICAL, None
    
    # "Church of Jesus Christ" (too short — could be other denominations)
    # Only normalize if we know it's LDS (in hierarchy)
    if low == 'church of jesus christ' and hierarchy_info:
        return CANONICAL, None
    
    # "LDS Church" / "LDS CHURCH" / "Lds Church" → canonical
    if low in ('lds church', 'lds'):
        return CANONICAL, None
    
    # "Mormon Church" / "MORMON CHURCH" → canonical
    if low in ('mormon church', 'mormons', 'mormons church'):
        return CANONICAL, None
    
    # "CHAPEL" → canonical (generic chapel for LDS)
    if low == 'chapel':
        return CANONICAL, None
    
    # FAMILY SERVICES pattern
    if 'family services' in low and ('jesus christ' in low or 'latter-day' in low):
        return CANONICAL, None
    
    # MEETINGHOUSE pattern  
    if low.strip() == 'meetinghouse':
        return CANONICAL, None
    
    # Generic "LDS" → canonical
    if low.strip() == 'lds':
        return CANONICAL, None
    
    # "Mormon Church" with extra
    if 'mormon' in low and ('church' in low or 'iglesia' in low):
        return CANONICAL, None
    
    # "The Church of Jesus Christ of Latter-day Saints — [something]" → keep
    if low.startswith('the church of jesus christ of latter-day saints'):
        suffix = name[len('The Church of Jesus Christ of Latter-day Saints'):].strip().lstrip('-–—, ').strip()
        if suffix:
            return f'{CANONICAL} — {suffix}', None
        return CANONICAL, None
    
    # Catch any remaining all-caps or title-case variants of the canonical name
    # Normalize by checking if the lowercase is a known variant
    canonical_low = 'the church of jesus christ of latter-day saints'
    if low == canonical_low:
        return CANONICAL, None
    
    # Nothing matched — keep original
    return name, None


def main():
    dry_run = '--dry-run' in sys.argv
    
    db = sqlite3.connect(r'E:\grid\churches.db', timeout=120)
    db.execute("PRAGMA journal_mode=WAL")
    db.execute("PRAGMA busy_timeout=120000")
    c = db.cursor()
    
    print("=" * 60)
    print("LDS NAME NORMALIZER")
    print("=" * 60)
    
    # ── Build hierarchy lookup (church_id → hierarchy info) ──
    print("\nLoading LDS hierarchy info...")
    c.execute("""SELECT church_id, lds_type, lds_detail, city, state, country 
                 FROM lds_hierarchy WHERE church_id IS NOT NULL""")
    hier_map = {}
    for row in c.fetchall():
        hier_map[row[0]] = {
            'lds_type': row[1],
            'lds_detail': row[2],
            'city': row[3],
            'state': row[4],
            'country': row[5],
        }
    print(f"  Loaded {len(hier_map):,} hierarchy entries")
    
    # ── Query unique LDS name patterns ──
    print("\nQuerying unique LDS name patterns...")
    
    lds_placeholders = ','.join('?' for _ in LDS_TAXONOMY_IDS)
    c.execute(f"""
        SELECT name,
               COUNT(*) as cnt,
               MAX(CASE WHEN city IS NOT NULL AND city != '' AND city != 'None' THEN city ELSE NULL END) as sample_city,
               MAX(country) as sample_country
        FROM churches
        WHERE taxonomy_id IN ({lds_placeholders})
        GROUP BY name
        ORDER BY cnt DESC
    """, LDS_TAXONOMY_IDS)
    rows = c.fetchall()
    
    total_entries = sum(r[1] for r in rows)
    print(f"  Found {len(rows):,} unique patterns ({total_entries:,} entries)")
    
    # ── Compute canonical forms ──
    print("\nComputing canonical names...")
    
    # For each name pattern, get a sample hierarchy entry
    pattern_hier = {}
    for name, cnt, _, _ in rows:
        c.execute(f"""
            SELECT h.church_id, h.lds_type, h.lds_detail, h.city, h.state, h.country
            FROM lds_hierarchy h
            JOIN churches c2 ON h.church_id = c2.id
            WHERE c2.name = ? AND c2.taxonomy_id IN ({lds_placeholders})
            LIMIT 1
        """, [name] + list(LDS_TAXONOMY_IDS))
        hr = c.fetchone()
        if hr:
            pattern_hier[name] = {
                'lds_type': hr[1],
                'lds_detail': hr[2],
                'city': hr[3],
                'state': hr[4],
                'country': hr[5],
            }
    
    pattern_map = {}
    changes = 0
    unchanged = 0
    translated = 0
    city_found = 0
    typed_normalized = 0
    
    for name, cnt, sample_city, sample_country in rows:
        has_city = bool(sample_city and sample_city not in ('', 'None'))
        hier = pattern_hier.get(name, {})
        
        new_name, backfill_city = normalize_name_pattern(name, has_city, hier)
        
        if new_name != name:
            pattern_map[name] = (new_name, backfill_city)
            changes += cnt
            if backfill_city:
                city_found += cnt
            if hier.get('lds_type') and hier['lds_type'] != 'meetinghouse':
                typed_normalized += cnt
            # Detect non-English
            if bool(re.search(r'[^\x00-\x7f]', name)):
                translated += cnt
        else:
            unchanged += cnt
    
    print(f"\nSummary:")
    print(f"  {changes:,} entries will be changed ({len(pattern_map)} patterns)")
    print(f"  {unchanged:,} entries already canonical")
    print(f"  {translated:,} non-English translated")
    print(f"  {city_found:,} city names extracted")
    print(f"  {typed_normalized:,} typed entries normalized (stake/seminary/institute/etc.)")
    
    if dry_run:
        print("\n=== DRY RUN — no changes made ===")
        print("\nAll pattern changes (sorted by frequency):")
        for old_name, (new_name, bc) in sorted(pattern_map.items(), 
                                                 key=lambda x: -sum(1 for r in rows if r[0] == x[0])):
            matching = [r for r in rows if r[0] == old_name]
            cnt = matching[0][1] if matching else 0
            bc_str = f"  +city={bc}" if bc else ""
            print(f"  [{cnt:>6}] {old_name[:90]}")
            print(f"         -> {new_name[:90]}{bc_str}")
        
        # Show unchanged patterns too
        print(f"\n=== Top unchanged patterns ===")
        unchanged_patterns = [(name, sum(1 for r2 in rows if r2[0] == name and name not in pattern_map)) 
                              for name in set(r[0] for r in rows if r[0] not in pattern_map)]
        unchanged_patterns.sort(key=lambda x: -x[1])
        for name, cnt in unchanged_patterns[:30]:
            print(f"  [{cnt:>6}] {name[:100]}")
        
        return
    
    # ── Apply changes ──
    print("\nApplying changes...")
    c.execute("BEGIN TRANSACTION")
    applied = 0
    now = datetime.now().isoformat()
    
    for old_name, (new_name, backfill_city) in pattern_map.items():
        # Get church IDs with this name (LDS taxonomy only)
        c.execute(f"""
            SELECT id FROM churches 
            WHERE name = ? AND taxonomy_id IN ({lds_placeholders}) AND id IS NOT NULL
        """, [old_name] + list(LDS_TAXONOMY_IDS))
        ids = [r[0] for r in c.fetchall()]
        
        if not ids:
            continue
        
        if backfill_city:
            c.execute("""
                UPDATE churches
                SET name = ?,
                    city = COALESCE(NULLIF(NULLIF(city, ''), 'None'), ?)
                WHERE name = ? AND taxonomy_id IN (""" + lds_placeholders + """)
            """, [new_name, backfill_city, old_name] + list(LDS_TAXONOMY_IDS))
        else:
            c.execute(f"""
                UPDATE churches
                SET name = ?
                WHERE name = ? AND taxonomy_id IN ({lds_placeholders})
            """, [new_name, old_name] + list(LDS_TAXONOMY_IDS))
        
        rows_affected = c.execute("SELECT changes()").fetchone()[0]
        applied += rows_affected
        
        if len(pattern_map) <= 50 or rows_affected > 100:
            bc_str = f" +city={backfill_city}" if backfill_city else ""
            print(f"  [{rows_affected:>6}] {old_name[:70]}")
            print(f"         -> {new_name[:70]}{bc_str}")
    
    db.commit()
    print(f"\n  Applied {applied:,} changes across {len(pattern_map)} patterns")
    
    # ── Log enrichment_change_log (one per pattern, using first ID) ──
    print("\nLogging enrichment changes...")
    for old_name, (new_name, backfill_city) in pattern_map.items():
        c.execute(f"""
            SELECT id FROM churches 
            WHERE name = ? AND taxonomy_id IN ({lds_placeholders}) AND id IS NOT NULL
            LIMIT 1
        """, [new_name] + list(LDS_TAXONOMY_IDS))
        row = c.fetchone()
        if row:
            c.execute("""
                INSERT INTO enrichment_change_log (church_id, field_name, old_value, new_value, change_source, changed_at)
                VALUES (?, 'name', ?, ?, 'lds_name_normalizer', ?)
            """, (row[0], old_name, new_name, now))
    db.commit()
    print(f"  Enrichment changes logged for {len(pattern_map)} patterns")
    
    # ── Log provenance (one summary row) ──
    print("Logging provenance...")
    c.execute(f"""
        INSERT INTO provenance_log (source, script_name, started_at, completed_at,
                                     churches_updated, fields_populated, records_attempted, status)
        VALUES ('lds_name_normalizer', 'standardize_lds_names.py', ?, ?, ?, ?, ?, 'completed')
    """, (now, datetime.now().isoformat(), changes, 'name', total_entries))
    db.commit()
    print(f"  Provenance logged")
    
    # ── Final stats ──
    c.execute(f"""
        SELECT COUNT(DISTINCT name) FROM churches 
        WHERE taxonomy_id IN ({lds_placeholders})
    """, LDS_TAXONOMY_IDS)
    final_unique = c.fetchone()[0]
    print(f"\n  Before: {len(rows):,} unique name patterns")
    print(f"  After:  {final_unique:,} unique name patterns")
    
    db.close()
    print("\nDone. LDS name normalization complete.")


if __name__ == '__main__':
    main()
