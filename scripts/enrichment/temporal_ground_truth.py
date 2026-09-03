"""
temporal_ground_truth.py — Extract founding/earliest-attested dates from city directories
============================================================================================

When a church appears in a city directory, we know it existed in that year.
This script:
  1. Finds each church's earliest attested year across all city directories
  2. Backfills the year to churches.enrichment data
  3. Identifies churches with directory-only evidence (not in GRID)
  4. Computes "last seen" years for potential closure detection

Usage:
  python temporal_ground_truth.py           # Full analysis + backfill
  python temporal_ground_truth.py --report  # Report only, no writes
"""

import sqlite3, re, sys
from collections import defaultdict
from datetime import datetime, timezone

DB = 'e:/grid/churches.db'
NOW = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')


def main(dry_run=False):
    db = sqlite3.connect(DB)
    db.execute('PRAGMA journal_mode=WAL')
    db.row_factory = sqlite3.Row
    
    # ── 1. Per-church temporal profiles ───────────────────────────────
    print('=== TEMPORAL PROFILES ===\n')
    
    # A. Matched churches: first/last seen, consecutive years
    matched = db.execute('''
        SELECT cdc.matched_church_id as church_id, c.name, c.city, c.state,
               MIN(cdc.directory_year) as first_year,
               MAX(cdc.directory_year) as last_year,
               COUNT(DISTINCT directory_id) as n_directories,
               COUNT(*) as n_entries
        FROM city_directory_churches cdc
        JOIN churches c ON c.id = cdc.matched_church_id
        WHERE cdc.matched_church_id IS NOT NULL
        GROUP BY cdc.matched_church_id
        ORDER BY first_year, last_year
    ''').fetchall()
    
    print(f'Matched churches with temporal data: {len(matched)}')
    
    # Age distribution
    age_dist = defaultdict(int)
    for m in matched:
        span = m['last_year'] - m['first_year']
        age_dist[span] += 1
    
    print('Age span distribution (years attested):')
    for span in sorted(age_dist):
        bar = '█' * min(age_dist[span], 40)
        print(f'  {span:3d}yr: {age_dist[span]:4d} {bar}')
    
    # Earliest attestation by city
    print('\nEarliest attestation by city:')
    city_first = defaultdict(list)
    for m in matched:
        city_first[m['city']].append(m['first_year'])
    for city in sorted(city_first):
        years = city_first[city]
        print(f'  {city:20s}: earliest={min(years)}, median={sorted(years)[len(years)//2]}, n={len(years)}')
    
    # B. Unmatched churches — these are directory-only evidence
    unmatched = db.execute('''
        SELECT raw_name, directory_city, directory_state,
               MIN(directory_year) as first_year,
               MAX(directory_year) as last_year,
               COUNT(DISTINCT directory_id) as n_directories
        FROM city_directory_churches
        WHERE matched_church_id IS NULL
        GROUP BY raw_name, directory_city
        ORDER BY n_directories DESC, first_year
    ''').fetchall()
    
    print(f'\nUnmatched churches (directory-only): {len(unmatched)}')
    
    # Show top unmatched by persistence
    print('\nMost persistent unmatched churches (appear in most directories):')
    for u in unmatched[:15]:
        span = u['last_year'] - u['first_year']
        print(f'  {u["raw_name"][:55]:55s} {u["directory_city"]:15s} '
              f'{u["first_year"]}-{u["last_year"]} ({span}yr, {u["n_directories"]} dirs)')
    
    # ── 2. First-appearance analysis ──────────────────────────────────
    print(f'\n=== FIRST APPEARANCE ANALYSIS ===\n')
    
    # Churches that first appear in the earliest directory year (1960)
    # vs. churches that appear later (potentially founded after 1960)
    first_years = defaultdict(list)
    for m in matched:
        first_years[m['first_year']].append(m['name'])
    
    print('Churches by first-appearance year (matched):')
    for yr in sorted(first_years):
        print(f'  {yr}: {len(first_years[yr])} churches newly attested')
    
    # ── 3. Gap/closure candidates ────────────────────────────────────
    print(f'\n=== POTENTIAL CLOSURES ===\n')
    
    # Churches seen in early directories but NOT in later years
    # (could indicate closure, or just missing from later directories)
    gaps = db.execute('''
        SELECT cdc.matched_church_id, c.name, c.city,
               MIN(cdc.directory_year) as first,
               MAX(cdc.directory_year) as last,
               MAX(cdc.directory_year) - MIN(cdc.directory_year) as span
        FROM city_directory_churches cdc
        JOIN churches c ON c.id = cdc.matched_church_id
        WHERE cdc.matched_church_id IS NOT NULL
        GROUP BY cdc.matched_church_id
        HAVING span <= 3 AND MAX(cdc.directory_year) < 1965
        ORDER BY last, first
    ''').fetchall()
    
    print(f'Short-lived churches (span ≤ 3yr, last seen < 1965): {len(gaps)}')
    for g in gaps[:15]:
        print(f'  {g["name"][:55]:55s} {g["city"]:15s} {g["first"]}-{g["last"]}')
    
    # ── 4. Backfill to GRID ──────────────────────────────────────────
    if not dry_run:
        print(f'\n=== BACKFILLING TO CHURCHES ===\n')
        
        # Check if churches has year_founded column
        cols = [r[1] for r in db.execute('PRAGMA table_info(churches)')]
        target_col = 'year_founded' if 'year_founded' in cols else None
        
        if target_col:
            backfilled = 0
            for m in matched:
                # Only backfill if GRID doesn't have a year_founded or our year is earlier
                existing = db.execute(
                    f'SELECT {target_col} FROM churches WHERE id=?', (m['church_id'],)
                ).fetchone()
                
                existing_year = existing[0] if existing and existing[0] else 0
                
                if not existing_year or m['first_year'] < existing_year:
                    db.execute(
                        f'UPDATE churches SET {target_col}=? WHERE id=?',
                        (m['first_year'], m['church_id'])
                    )
                    backfilled += 1
            
            db.commit()
            print(f'  Backfilled year_founded for {backfilled} churches')
        else:
            print('  No year_founded column found — storing in enrichment_change_log')
            
            # Store as enrichment data
            backfilled = 0
            for m in matched:
                db.execute('''
                    INSERT INTO enrichment_change_log 
                    (church_id, field_name, old_value, new_value, change_source, changed_at)
                    VALUES (?, 'earliest_attested_city_directory', '', ?, 'city_directory_temporal', ?)
                ''', (m['church_id'], str(m['first_year']), NOW))
                backfilled += 1
            
            db.commit()
            print(f'  Logged earliest_attested for {backfilled} churches in enrichment_change_log')
    
    # ── 5. Summary ────────────────────────────────────────────────────
    print(f'\n{"="*60}')
    print(f'TEMPORAL GROUND TRUTH SUMMARY')
    print(f'  {len(matched):,} churches with time-series data (matched to GRID)')
    print(f'  {len(unmatched):,} churches attested only in directories (not in GRID)')
    
    earliest = min(m['first_year'] for m in matched) if matched else 'N/A'
    latest = max(m['last_year'] for m in matched) if matched else 'N/A'
    print(f'  Date range: {earliest} — {latest}')
    print(f'  {"="*60}')
    
    db.close()


if __name__ == '__main__':
    dry_run = '--report' in sys.argv or '--dry-run' in sys.argv
    main(dry_run=dry_run)
