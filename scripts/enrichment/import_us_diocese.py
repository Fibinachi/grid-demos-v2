"""
import_us_diocese.py — Import US Catholic diocese assignments into GRID
=======================================================================
Source: Kenneth Burchfiel's US Diocese Mapper
  https://github.com/kburchfiel/us_diocese_mapper
  counties_by_diocese.csv, diocese_province_list.csv — Public Domain

Strategy:
  1. The diocese mapper maps every US county -> Catholic diocese (176 dioceses)
  2. GRID has fips (county FIPS) on ~235K US churches -> direct match via GEOID
  3. For state-only matches, assign based on single-diocese states
  4. Assign diocese and province to church_enrichment table
  5. Log all provenance

Counts:
  - 235,044 US churches have FIPS codes -> direct match
  - 790,993 US churches have state codes
  - 1,047,719 total US churches
  - 75,474 already have diocese assigned
"""

import sqlite3
import csv
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from gw_db import connect, Provenance, log_change

# ── Paths ──
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
CSV_PATH = os.path.join(BASE_DIR, 'data', 'diocese_mapper', 'counties_by_diocese.csv')
PROVINCE_CSV = os.path.join(BASE_DIR, 'data', 'diocese_mapper', 'diocese_province_list.csv')
FIPS_CSV = os.path.join(BASE_DIR, 'data', 'diocese_mapper', 'state_fips_codes.csv')

def main():
    conn = connect()
    
    # ── Load diocese mapper data ──
    print("Loading county->diocese mapping...")
    fips_lookup = {}    # key: fips_code (5-digit string) -> {diocese, province, diocese_detail, province_detail}
    state_diocese_map = {}  # key: state_code -> set of dioceses
    
    with open(CSV_PATH, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            state_code = row.get('State_Code', '').strip()
            geo_id = row.get('GEOID', '').strip()
            diocese = row.get('Diocese', '').strip()
            diocese_detail = row.get('Diocese_Detail', '').strip()
            province_detail = row.get('Province_Detail', '').strip()
            province = row.get('Province', '').strip()
            
            if not diocese:
                continue
            
            if geo_id:
                fips_lookup[geo_id] = {
                    'diocese': diocese,
                    'province': province,
                    'diocese_detail': diocese_detail,
                    'province_detail': province_detail,
                }
            
            if state_code not in state_diocese_map:
                state_diocese_map[state_code] = set()
            state_diocese_map[state_code].add(diocese)
    
    # Find single-diocese states
    single_diocese_states = {st: list(ds)[0] for st, ds in state_diocese_map.items() if len(ds) == 1}
    
    print(f"  Loaded {len(fips_lookup):,} FIPS->diocese mappings")
    print(f"  Single-diocese states: {len(single_diocese_states)}")
    
    # ── Count current state ──
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM church_enrichment WHERE diocese IS NOT NULL AND diocese != ''")
    before_diocese = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM churches WHERE country='US'")
    total_us = c.fetchone()[0]
    c.execute("""
        SELECT COUNT(*) FROM churches WHERE country='US' 
        AND (LOWER(denomination) LIKE '%catholic%' OR LOWER(denomination) LIKE '%roman%')
    """)
    catholic_us = c.fetchone()[0]
    print(f"\nCurrent US diocese coverage: {before_diocese:,} / {catholic_us:,} Catholic ({100*before_diocese/catholic_us:.1f}%)")
    print(f"  Total US churches: {total_us:,}, Catholic subset: {catholic_us:,}")
    
    # ── Ensure enrichment rows exist ──
    print("\nEnsuring church_enrichment rows exist for US churches...")
    c.execute("""
        INSERT OR IGNORE INTO church_enrichment (church_id)
        SELECT id FROM churches WHERE country='US'
    """)
    conn.commit()
    
    # ── FIPS-based match (Catholic churches only) ──
    print("\n=== FIPS-based matching (Catholic only) ===")
    c.execute("""
        SELECT ch.id, ch.fips, ch.state, ch.name,
               ce.diocese as existing_diocese
        FROM churches ch
        LEFT JOIN church_enrichment ce ON ce.church_id = ch.id
        WHERE ch.country='US' 
          AND ch.fips IS NOT NULL AND ch.fips != ''
          AND (LOWER(ch.denomination) LIKE '%catholic%' OR LOWER(ch.denomination) LIKE '%roman%')
          AND (ce.diocese IS NULL OR ce.diocese = '')
    """)
    
    fips_updates = []
    fips_no_match = 0
    for row in c.fetchall():
        church_id, fips, state, name, existing = row
        geo_id = str(fips).strip().zfill(5)[:5]
        
        if geo_id in fips_lookup:
            m = fips_lookup[geo_id]
            fips_updates.append((m['diocese'], m['diocese_detail'], m['province'], m['province_detail'], church_id))
        else:
            fips_no_match += 1
    
    print(f"  FIPS matches: {len(fips_updates):,}")
    print(f"  FIPS no-match: {fips_no_match:,}")
    
    # ── State-level match for single-diocese states (Catholic only) ──
    print("\n=== State-level matching (Catholic single-diocese states) ===")
    c.execute("""
        SELECT ch.id, ch.state, ch.name,
               ce.diocese as existing_diocese
        FROM churches ch
        LEFT JOIN church_enrichment ce ON ce.church_id = ch.id
        WHERE ch.country='US' 
          AND ch.state IS NOT NULL AND ch.state != ''
          AND (ch.fips IS NULL OR ch.fips = '')
          AND (LOWER(ch.denomination) LIKE '%catholic%' OR LOWER(ch.denomination) LIKE '%roman%')
          AND (ce.diocese IS NULL OR ce.diocese = '')
    """)
    
    state_updates = []
    state_no_match = 0
    for row in c.fetchall():
        church_id, state, name, existing = row
        state_upper = state.upper().strip()
        
        if state_upper in single_diocese_states:
            diocese = single_diocese_states[state_upper]
            # Get the first matching entry from fips_lookup for province info
            province = None
            diocese_detail = None
            province_detail = None
            for k, v in fips_lookup.items():
                if v['diocese'] == diocese:
                    province = v['province']
                    diocese_detail = v['diocese_detail']
                    province_detail = v['province_detail']
                    break
            
            state_updates.append((diocese, diocese_detail or '', province or '', province_detail or '', church_id))
        else:
            state_no_match += 1
    
    print(f"  State-level matches: {len(state_updates):,}")
    print(f"  State-level no-match: {state_no_match:,}")
    
    # ── Apply all updates ──
    all_updates = fips_updates + state_updates
    total_assigned = len(all_updates)
    
    if all_updates:
        print(f"\nApplying {total_assigned:,} diocese assignments...")
        with Provenance(conn, "import_us_diocese.py", source="us_diocese_mapper",
                        action="enriched", fields="diocese,diocese_detail,province,province_detail"):
            c.executemany("""
                UPDATE church_enrichment 
                SET diocese = ?, diocese_detail = ?, province = ?, province_detail = ?
                WHERE church_id = ?
            """, all_updates)
            conn.commit()
        
        # ── Verify ──
        c.execute("SELECT COUNT(*) FROM church_enrichment WHERE diocese IS NOT NULL AND diocese != ''")
        after_diocese = c.fetchone()[0]
        newly_assigned = after_diocese - before_diocese
        pct = 100 * after_diocese / total_us if total_us > 0 else 0
        print(f"\n=== RESULTS ===")
        print(f"Before: {before_diocese:,} / {total_us:,} ({100*before_diocese/total_us:.1f}%)")
        print(f"After:  {after_diocese:,} / {total_us:,} ({pct:.1f}%)")
        print(f"Newly assigned: {newly_assigned:,}")
        
        # Show diocese distribution
        print("\nTop 20 dioceses assigned:")
        for row in c.execute("""
            SELECT ce.diocese, COUNT(*) as cnt
            FROM church_enrichment ce
            JOIN churches ch ON ch.id = ce.church_id
            WHERE ch.country='US' AND ce.diocese IS NOT NULL AND ce.diocese != ''
            GROUP BY ce.diocese
            ORDER BY cnt DESC
            LIMIT 20
        """):
            print(f"  {row[0]:30s} {row[1]:>8,}")
    else:
        print("\nNo updates to apply.")
    
    conn.close()

if __name__ == '__main__':
    main()
    c.execute("""
        SELECT ch.id, ch.fips, ch.state, ch.city, ch.name, 
               ce.diocese as existing_diocese
        FROM churches ch
        LEFT JOIN church_enrichment ce ON ce.church_id = ch.id
        WHERE ch.country='US' 
          AND (ce.diocese IS NULL OR ce.diocese = '')
    """)
    
    updates = []
    for row in c.fetchall():
        church_id, fips, state, city, name, existing = row
        
        match = None
        
        # Try FIPS match first
        if fips and len(str(fips)) >= 5:
            geo_id = str(fips).zfill(5)[:5]
            if geo_id in fips_lookup:
                match = fips_lookup[geo_id]
        
        # Try state+county from fips
        if not match and fips and len(str(fips)) >= 5:
            state_fips_code = str(fips).zfill(5)[:2]
            if state_fips_code in state_fips_map:
                st = state_fips_map[state_fips_code]
                # Try to match by fips directly (already tried above)
                pass
        
        # Try state only (for single-diocese states)
        if not match and state:
            state_upper = state.upper()
            # Check if this state only has one diocese
            state_matches = [v for k, v in county_lookup.items() if k[0] == state_upper]
            unique_dioceses = set(m['diocese'] for m in state_matches)
            if len(state_matches) > 0 and len(unique_dioceses) == 1:
                match = state_matches[0]
        
        if match:
            updates.append((match['diocese'], match['diocese_detail'], match['province'], match['province_detail'], church_id))
            assigned += 1
        else:
            no_match += 1
        
        if assigned % 5000 == 0 and assigned > 0:
            print(f"  Assigned: {assigned:,}, No match: {no_match:,}")
    
    print(f"  Total assigned: {assigned:,}")
    print(f"  No match: {no_match:,}")
    
    # ── Apply updates in batches ──
    if updates:
        print(f"\nApplying {len(updates):,} diocese assignments...")
        with Provenance(conn, "import_us_diocese.py", source="us_diocese_mapper",
                        action="enriched", fields="diocese,diocese_detail,province,province_detail"):
            c.executemany("""
                UPDATE church_enrichment 
                SET diocese = ?, diocese_detail = ?, province = ?, province_detail = ?
                WHERE church_id = ?
            """, updates)
            conn.commit()
        
        # Verify
        c.execute("SELECT COUNT(*) FROM church_enrichment WHERE diocese IS NOT NULL AND diocese != ''")
        after_diocese = c.fetchone()[0]
        print(f"\nFinal US diocese coverage: {after_diocese:,} / {total_us:,} ({100*after_diocese/total_us:.1f}%)")
        print(f"Newly assigned: {after_diocese - before_diocese:,}")
    else:
        print("\nNo updates to apply.")
    
    conn.close()

if __name__ == '__main__':
    main()
