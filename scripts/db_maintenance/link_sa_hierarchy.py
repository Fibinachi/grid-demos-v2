"""
Link Salvation Army hierarchy — multi-level structural linking.

Hierarchy model:
  International HQ (#1459, London)
  ├── Territorial HQs (AU, KE, NG, PH, PK, ZM, ZW)
  │   ├── Divisional HQs (AU, FJ, IN, NG, PK, US, ZA)
  │   │   ├── Corps, Citadels, Temples, Halls, Chapels, Churches
  │   │   ├── Community Churches
  │   │   ├── Social Services
  │   │   ├── Schools
  │   │   └── Musical Groups
  │   └── Generic entries
  ├── Governing Council (CA — legal entity, 215 entries)
  ├── Countries without territorial HQ → closest match
  └── Social Services, Schools (parallel to corps hierarchy)

Usage:
    python scripts/db_maintenance/link_sa_hierarchy.py           # run for real
    python scripts/db_maintenance/link_sa_hierarchy.py --dry-run # preview
"""
import sqlite3, sys, os

CHUNK = 500
dry_run = '--dry-run' in sys.argv

# ── Known territorial HQs in DB by country ──
# (sa_hierarchy.id, country, name)
TERRITORIAL_HQS = {
    'AU': {'id': 390,  'name': 'Southern Territory'},        # Southern Territory
    'KE': {'id': 2056, 'name': 'Kenya East Territory'},      # Kenya East Territorial HQ
    'NG': {'id': 634,  'name': 'Nigeria Territory'},         # Territorial Headquarters
    'PH': {'id': 1005, 'name': 'Philippines Territory'},     # Territorial Headquarters
    'PK': {'id': 540,  'name': 'Pakistan Territory'},        # Territorial Headquarters Lahore
    'ZM': {'id': 2078, 'name': 'Zambia Territory'},          # Zambia Territory
    'ZW': {'id': 384,  'name': 'Zimbabwe Territory'},        # Harare West Division Zimbabwe Territory
}

# ── Known divisional HQs ──
# (sa_hierarchy.id, country)
DIVISIONAL_HQS = {
    # AU — under Southern Territory
    389: {'country': 'AU', 'territory': 'AU'},   # Salvation Army (duplicate, SA type generic)
    # Actually there's no clean divisional HQ in AU
    
    # FJ
    234: {'country': 'FJ', 'territory': None},  # Fiji Division
    
    # IN
    989: {'country': 'IN', 'territory': None},  # Divisional Headquarters
    1151: {'country': 'IN', 'territory': None},  # Thiruvalla Division
    
    # KE — under Kenya East Territory
    631: {'country': 'KE', 'territory': 'KE'},  # Headquarters, Kakamega
    
    # NG — under Nigeria Territory
    531: {'country': 'NG', 'territory': 'NG'},  # Anambra East Division
    
    # PK — under Pakistan Territory
    1165: {'country': 'PK', 'territory': 'PK'},  # Islamabad Division
    1944: {'country': 'PK', 'territory': 'PK'},  # Lahore HQ
    1946: {'country': 'PK', 'territory': 'PK'},  # Lahore HQ
    2143: {'country': 'PK', 'territory': 'PK'},  # Church Jhang Division
    
    # US — no territorial HQ in DB
    2587: {'country': 'US', 'territory': None},  # NEW JERSEY DHQ (NJ)
    2846: {'country': 'US', 'territory': None},  # Cascade Division (OR)
    2606: {'country': 'US', 'territory': None},  # Atlanta Temple & Southeastern HQ (GA)
    2824: {'country': 'US', 'territory': None},  # Southeast MI ARC HQ (MI)
    2458: {'country': 'US', 'territory': None},  # Nacaome HQ (ND — likely mis-tagged)
    
    # ZA — under Zimbabwe Territory or independent
    295: {'country': 'ZA', 'territory': None},   # Eastern Cape Division
    1169: {'country': 'ZA', 'territory': None},  # Limpopo Division
}

# ── US divisional HQs by state coverage ──
# Maps states to the best divisional HQ
US_DIVISION_STATES = {
    'NJ': 2587,  # NEW JERSEY DHQ
    'NY': 2587,  # New Jersey DHQ serves NY metro
    'PA': 2587,  # Eastern territory
    'DE': 2587,
    'MD': 2587,
    'DC': 2587,
    'VA': 2587,
    'WV': 2587,
    'OR': 2846,  # Cascade Division
    'WA': 2846,
    'ID': 2846,
    'MT': 2846,
    'AK': 2846,
    'GA': 2606,  # Atlanta Temple & Southeastern HQ
    'AL': 2606,
    'SC': 2606,
    'NC': 2606,
    'TN': 2606,
    'FL': 2606,
    'MS': 2606,
    'MI': 2824,  # Southeast MI ARC HQ
    'OH': 2824,
    'IN': 2824,
    'KY': 2824,
    'ND': 2458,  # Nacaome HQ (might be mis-tagged)
    'SD': 2458,
    'MN': 2458,
    'WI': 2458,
    'IA': 2458,
}

# ── Country-to-territory mapping for countries without their own HQ ──
# These countries don't have a territorial HQ in our DB, so we map them
# to the nearest territorial HQ or to International HQ
COUNTRY_TERRITORY = {
    # Countries belonging to existing territories
    'PG': 'AU',   # Papua New Guinea → Australia Southern Territory
    'NZ': 'AU',   # New Zealand → Australia Southern Territory
    'FJ': 'AU',   # Fiji → Australia Southern Territory
    'UG': 'KE',   # Uganda → Kenya East Territory
    'TZ': 'KE',   # Tanzania → Kenya East Territory
    'RW': 'KE',   # Rwanda → Kenya East Territory
    'CD': 'KE',   # Congo → Kenya East Territory
    'GH': 'NG',   # Ghana → Nigeria Territory
    'LR': 'NG',   # Liberia → Nigeria Territory
    'SL': 'NG',   # Sierra Leone → Nigeria Territory
    'JM': 'PH',   # Jamaica → Philippines Territory (SA structure: Caribbean)
    'BM': 'PH',   # Bermuda
    'BB': 'PH',
    'TT': 'PH',
    'BS': 'PH',
    'BZ': 'PH',
    'GY': 'PH',
    'HT': 'PH',
    'KN': 'PH',
    'DO': 'PH',
    'PR': 'PH',
    'MZ': 'ZW',   # Mozambique → Zimbabwe Territory
    'ZM': 'ZW',   # Zambia → Zimbabwe Territory (has own HQ too)
    'BW': 'ZW',   # Botswana → Zimbabwe Territory
    'NA': 'ZW',   # Namibia → Zimbabwe Territory
    'LS': 'ZW',   # Lesotho → Zimbabwe Territory
    'ZA': 'ZW',   # South Africa → Zimbabwe Territory
    'KE': 'KE',   # Kenya
    'NG': 'NG',   # Nigeria
    'PH': 'PH',   # Philippines
    'PK': 'PK',   # Pakistan
    'AU': 'AU',   # Australia
    'ZW': 'ZW',   # Zimbabwe
}

INTERNATIONAL_HQ_ID = 1459


def progress_bar(current, total, label=''):
    if total == 0:
        return
    bar_len = 40
    filled = int(bar_len * current / total)
    bar = '█' * filled + '░' * (bar_len - filled)
    pct = current * 100 // total
    sys.stdout.write(f'\r  {bar} {pct}% | {label} [{current}/{total}]')
    sys.stdout.flush()
    if current >= total:
        sys.stdout.write('\n')


def main():
    db = sqlite3.connect(r'E:\grid\churches.db', timeout=30)
    db.execute("PRAGMA journal_mode=WAL")
    db.execute("PRAGMA busy_timeout=60000")
    c = db.cursor()
    
    print("=" * 60)
    print("Salvation Army Hierarchy Linking")
    if dry_run:
        print("  *** DRY RUN — no changes will be made ***")
    print("=" * 60)
    
    # ── Verify International HQ exists ──
    ihq = c.execute("SELECT id, name FROM sa_hierarchy WHERE id = ?", (INTERNATIONAL_HQ_ID,)).fetchone()
    if not ihq:
        print(f"\n❌ International HQ (#{INTERNATIONAL_HQ_ID}) not found in sa_hierarchy!")
        db.close()
        return
    print(f"\n✓ International HQ: #{ihq[0]} {ihq[1]}")
    
    # ── Count current state ──
    total = c.execute("SELECT COUNT(*) FROM sa_hierarchy").fetchone()[0]
    linked_before = c.execute("SELECT COUNT(*) FROM sa_hierarchy WHERE parent_id IS NOT NULL").fetchone()[0]
    print(f"  Total entries: {total}")
    print(f"  Already linked: {linked_before}")
    print(f"  To link: {total - linked_before}")
    
    # ────────────────────────────────────────────
    # PASS 1: Link territorial HQs → International HQ
    # ────────────────────────────────────────────
    print(f"\n{'─' * 60}")
    print("PASS 1: Territorial HQs → International HQ")
    print(f"{'─' * 60}")
    
    pass1_linked = 0
    for country_code, info in sorted(TERRITORIAL_HQS.items()):
        thq_id = info['id']
        thq = c.execute("SELECT id, name, parent_id FROM sa_hierarchy WHERE id = ?", (thq_id,)).fetchone()
        if not thq:
            print(f"  ⚠ #{thq_id} ({country_code}) not found in sa_hierarchy!")
            continue
        if thq[2] == INTERNATIONAL_HQ_ID:
            print(f"  ✓ #{thq_id} {thq[1]:60s} already linked to Int'l HQ")
            pass1_linked += 1
        else:
            if not dry_run:
                c.execute("""
                    UPDATE sa_hierarchy SET parent_id = ?, parent_sa_type = 'hq',
                        relationship = 'headquartered_in',
                        notes = 'Territorial HQ → International HQ'
                    WHERE id = ?
                """, (INTERNATIONAL_HQ_ID, thq_id))
            print(f"  → #{thq_id} {thq[1]:60s} → International HQ")
            pass1_linked += 1
    
    if not dry_run:
        db.commit()
    print(f"  Pass 1: {pass1_linked} territorial HQs linked")
    
    # ────────────────────────────────────────────
    # PASS 2: Link divisional HQs → territorial HQs
    # ────────────────────────────────────────────
    print(f"\n{'─' * 60}")
    print("PASS 2: Divisional HQs → Territorial HQs")
    print(f"{'─' * 60}")
    
    pass2_linked = 0
    for div_id, info in sorted(DIVISIONAL_HQS.items()):
        div_hq = c.execute("SELECT id, name, parent_id FROM sa_hierarchy WHERE id = ?", (div_id,)).fetchone()
        if not div_hq:
            print(f"  ⚠ #{div_id} not found in sa_hierarchy!")
            continue
        
        territory_code = info.get('territory')
        if territory_code and territory_code in TERRITORIAL_HQS:
            parent_id = TERRITORIAL_HQS[territory_code]['id']
            if div_hq[2] == parent_id:
                print(f"  ✓ #{div_id} {div_hq[1]:60s} already linked")
                pass2_linked += 1
            else:
                if not dry_run:
                    c.execute("""
                        UPDATE sa_hierarchy SET parent_id = ?, parent_sa_type = 'hq',
                            relationship = 'part_of',
                            notes = 'Divisional HQ → Territorial HQ'
                        WHERE id = ?
                    """, (parent_id, div_id))
                print(f"  → #{div_id} {div_hq[1]:60s} → Territorial HQ ({territory_code})")
                pass2_linked += 1
        else:
            # No territorial parent — link to International HQ
            if div_hq[2] == INTERNATIONAL_HQ_ID:
                print(f"  ✓ #{div_id} {div_hq[1]:60s} already linked to Int'l HQ")
            else:
                if not dry_run:
                    c.execute("""
                        UPDATE sa_hierarchy SET parent_id = ?, parent_sa_type = 'hq',
                            relationship = 'belongs_to_territory',
                            notes = 'Divisional HQ → International HQ (no territorial HQ in DB)'
                        WHERE id = ?
                    """, (INTERNATIONAL_HQ_ID, div_id))
                print(f"  → #{div_id} {div_hq[1]:60s} → International HQ (no territorial HQ)")
            pass2_linked += 1
    
    if not dry_run:
        db.commit()
    print(f"  Pass 2: {pass2_linked} divisional HQs linked")
    
    # ────────────────────────────────────────────
    # PASS 3: Link local entries to HQs
    # ────────────────────────────────────────────
    print(f"\n{'─' * 60}")
    print("PASS 3: Local entries → HQs")
    print(f"{'─' * 60}")
    
    # Get all unlinked non-HQ entries
    entries = c.execute("""
        SELECT id, church_id, name, sa_type, sa_detail, city, state, country,
               lat, lon
        FROM sa_hierarchy
        WHERE parent_id IS NULL
          AND sa_type NOT IN ('hq')
        ORDER BY country, city
    """).fetchall()
    print(f"  Unlinked local entries: {len(entries)}")
    
    # Build HQ lookup by country (territorial HQs + their IDs)
    hq_by_country = {}  # country_code → (hq_id, name)
    for cc, info in TERRITORIAL_HQS.items():
        hq_by_country[cc] = (info['id'], info['name'])
    
    pass3_counts = {
        'territorial_hq': 0,
        'intl_hq_fallback': 0,
        'us_divisional': 0,
        'ca_governing': 0,
        'unmatched': 0,
    }
    pass3_details = {'territorial': [], 'intl': [], 'us_div': [], 'ca_gov': [], 'unmatched': []}
    
    for entry in entries:
        eid = entry[0]
        country = entry[7] or ''
        
        # CASE 1: Country has a territorial HQ in DB
        if country in hq_by_country:
            parent_id = hq_by_country[country][0]
            if not dry_run:
                c.execute("""
                    UPDATE sa_hierarchy SET parent_id = ?, parent_sa_type = 'hq',
                        relationship = 'belongs_to_territory',
                        notes = 'Linked to territorial HQ by country'
                    WHERE id = ?
                """, (parent_id, eid))
            pass3_counts['territorial_hq'] += 1
            pass3_details['territorial'].append(eid)
        
        # CASE 2: Canada — link to Governing Council entries by city
        elif country == 'CA':
            city = (entry[5] or '').strip().upper()
            state = (entry[6] or '').strip().upper()
            
            # Find matching governing council entry by city
            gc_entry = c.execute("""
                SELECT id FROM sa_hierarchy
                WHERE sa_type = 'governing_council' AND country = 'CA'
                AND UPPER(city) = ?
                LIMIT 1
            """, (city,)).fetchone()
            
            if gc_entry:
                if not dry_run:
                    c.execute("""
                        UPDATE sa_hierarchy SET parent_id = ?, parent_sa_type = 'governing_council',
                            relationship = 'part_of',
                            notes = 'Linked to Governing Council by city'
                        WHERE id = ?
                    """, (gc_entry[0], eid))
                pass3_counts['ca_governing'] += 1
                pass3_details['ca_gov'].append(eid)
            else:
                # Fallback: link to International HQ
                if not dry_run:
                    c.execute("""
                        UPDATE sa_hierarchy SET parent_id = ?, parent_sa_type = 'hq',
                            relationship = 'belongs_to_territory',
                            notes = 'Linked to International HQ (no CA territorial/GC match)'
                        WHERE id = ?
                    """, (INTERNATIONAL_HQ_ID, eid))
                pass3_counts['intl_hq_fallback'] += 1
                pass3_details['intl'].append(eid)
        
        # CASE 3: United States — link to divisional HQs by state
        elif country == 'US':
            state = entry[6] or ''
            div_id = US_DIVISION_STATES.get(state)
            
            if div_id:
                if not dry_run:
                    c.execute("""
                        UPDATE sa_hierarchy SET parent_id = ?, parent_sa_type = 'hq',
                            relationship = 'part_of',
                            notes = 'Linked to US divisional HQ by state'
                        WHERE id = ?
                    """, (div_id, eid))
                pass3_counts['us_divisional'] += 1
                pass3_details['us_div'].append(eid)
            else:
                # Fallback: International HQ
                if not dry_run:
                    c.execute("""
                        UPDATE sa_hierarchy SET parent_id = ?, parent_sa_type = 'hq',
                            relationship = 'belongs_to_territory',
                            notes = 'Linked to International HQ (no US divisional HQ for state)'
                        WHERE id = ?
                    """, (INTERNATIONAL_HQ_ID, eid))
                pass3_counts['intl_hq_fallback'] += 1
                pass3_details['intl'].append(eid)
        
        # CASE 4: GB — link to International HQ (same country)
        elif country == 'GB':
            if not dry_run:
                c.execute("""
                    UPDATE sa_hierarchy SET parent_id = ?, parent_sa_type = 'hq',
                        relationship = 'belongs_to_territory',
                        notes = 'Linked to International HQ (same country)'
                    WHERE id = ?
                """, (INTERNATIONAL_HQ_ID, eid))
            pass3_counts['intl_hq_fallback'] += 1
            pass3_details['intl'].append(eid)
        
        # CASE 5: Others — try country→territory mapping, fallback to Int'l HQ
        else:
            territory_code = COUNTRY_TERRITORY.get(country)
            if territory_code and territory_code in hq_by_country:
                parent_id = hq_by_country[territory_code][0]
                if not dry_run:
                    c.execute("""
                        UPDATE sa_hierarchy SET parent_id = ?, parent_sa_type = 'hq',
                            relationship = 'belongs_to_territory',
                            notes = 'Linked via country→territory mapping'
                        WHERE id = ?
                    """, (parent_id, eid))
                pass3_counts['territorial_hq'] += 1
                pass3_details['territorial'].append(eid)
            else:
                # Ultimate fallback: International HQ
                if not dry_run:
                    c.execute("""
                        UPDATE sa_hierarchy SET parent_id = ?, parent_sa_type = 'hq',
                            relationship = 'belongs_to_territory',
                            notes = 'Linked to International HQ (no territorial match)'
                        WHERE id = ?
                    """, (INTERNATIONAL_HQ_ID, eid))
                pass3_counts['intl_hq_fallback'] += 1
                pass3_details['intl'].append(eid)
        
        progress_bar(len(pass3_details['territorial']) + len(pass3_details['intl']) +
                     len(pass3_details['us_div']) + len(pass3_details['ca_gov']),
                     len(entries), 'Linking entries')
    
    if not dry_run:
        db.commit()
    
    print(f"\n  Pass 3 results:")
    print(f"    Linked to territorial HQ: {pass3_counts['territorial_hq']}")
    print(f"    Linked to US divisional HQ: {pass3_counts['us_divisional']}")
    print(f"    Linked to Canada Governing Council: {pass3_counts['ca_governing']}")
    print(f"    Linked to International HQ (fallback): {pass3_counts['intl_hq_fallback']}")
    
    # ────────────────────────────────────────────
    # SUMMARY
    # ────────────────────────────────────────────
    print(f"\n{'=' * 60}")
    print("SUMMARY")
    print(f"{'=' * 60}")
    
    if not dry_run:
        linked_after = c.execute("SELECT COUNT(*) FROM sa_hierarchy WHERE parent_id IS NOT NULL").fetchone()[0]
        unlinked_after = c.execute("SELECT COUNT(*) FROM sa_hierarchy WHERE parent_id IS NULL").fetchone()[0]
        print(f"\n  Before: {linked_before} linked")
        print(f"  After:  {linked_after} linked")
        print(f"  Still unlinked: {unlinked_after}")
        print(f"  New links: {linked_after - linked_before}")
        
        # Show hierarchy levels
        print(f"\n  Hierarchy levels:")
        # Level 0: International HQ
        ihq_links = c.execute(
            "SELECT COUNT(*) FROM sa_hierarchy WHERE parent_id = ?", (INTERNATIONAL_HQ_ID,)
        ).fetchone()[0]
        print(f"    Level 0: International HQ (#{INTERNATIONAL_HQ_ID})")
        print(f"    Level 1: {ihq_links} entries directly under Int'l HQ")
        
        # Level 1: territorial HQs
        for cc, info in sorted(TERRITORIAL_HQS.items()):
            thq_id = info['id']
            sub_count = c.execute(
                "SELECT COUNT(*) FROM sa_hierarchy WHERE parent_id = ?", (thq_id,)
            ).fetchone()[0]
            if sub_count > 0:
                print(f"      #{thq_id} {info['name']:30s} ({cc}): {sub_count} subordinates")
        
        # Governing council
        gc_count = c.execute(
            "SELECT COUNT(*) FROM sa_hierarchy WHERE parent_id IN (SELECT id FROM sa_hierarchy WHERE sa_type='governing_council')"
        ).fetchone()[0]
        if gc_count > 0:
            print(f"      Governing Council (CA): {gc_count} subordinates")
        
        # US divisional
        for div_id in sorted(US_DIVISION_STATES.values()):
            sub_count = c.execute(
                "SELECT COUNT(*) FROM sa_hierarchy WHERE parent_id = ?", (div_id,)
            ).fetchone()[0]
            if sub_count > 0:
                div_name = c.execute("SELECT name FROM sa_hierarchy WHERE id = ?", (div_id,)).fetchone()
                if div_name:
                    print(f"      #{div_id} {div_name[0][:45]:45s}: {sub_count} subordinates")
        
        # Relationship type usage
        print(f"\n  Relationship types:")
        rels = c.execute("""
            SELECT relationship, COUNT(*) FROM sa_hierarchy
            WHERE relationship IS NOT NULL GROUP BY relationship
            ORDER BY COUNT(*) DESC
        """).fetchall()
        for r, cnt in rels:
            print(f"    {r}: {cnt}")
        
        # Sample links
        print(f"\n  Sample links (first 10):")
        samples = c.execute("""
            SELECT ch.name, ch2.name, sh.relationship
            FROM sa_hierarchy sh
            JOIN sa_hierarchy sh2 ON sh.parent_id = sh2.id
            JOIN churches ch ON sh.church_id = ch.id
            JOIN churches ch2 ON sh2.church_id = ch2.id
            LIMIT 10
        """).fetchall()
        for child, parent, rel in samples:
            print(f"    {child[:50]:50s} → {parent[:50]:50s} ({rel})")
    else:
        would_link = total - linked_before
        print(f"\n  Would link {would_link} entries")
        for k, v in pass3_counts.items():
            print(f"    {k}: {v}")
    
    db.close()
    print(f"\n{'=' * 60}")
    print("Done.")


if __name__ == '__main__':
    main()
