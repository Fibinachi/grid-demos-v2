"""
Merge unmatched WPA records into churches.db.
- New records: import as churches with source='wpa_historical_records_survey'
- Matched records: building_year already enriched, log the enrichment
- Handles: id assignment, provenance logging, country defaulting
"""
import sqlite3

WPA_DB = 'E:/grid/wpa.db'
CHURCHES_DB = 'E:/grid/churches.db'

def main():
    wpa = sqlite3.connect(WPA_DB)
    churches = sqlite3.connect(CHURCHES_DB)
    
    # Get max id for new records
    max_id = churches.execute('SELECT MAX(id) FROM churches').fetchone()[0] or 5000000
    next_id = max_id + 1
    
    # Count existing WPA source records
    existing = churches.execute(
        "SELECT COUNT(*) FROM churches WHERE source='wpa_historical_records_survey'"
    ).fetchone()[0]
    print(f'Existing WPA records in churches.db: {existing:,}')
    
    # Get unmatched WPA records
    unmatched = wpa.execute('''
        SELECT r.id, r.church_name, r.address_text, r.city, r.county, r.state,
               r.denomination, r.confidence, r.raw_text, v.year, r.volume_id
        FROM wpa_records r
        JOIN wpa_volumes v ON r.volume_id = v.id
        WHERE r.id NOT IN (SELECT wpa_record_id FROM wpa_matches)
          AND r.church_name != ''
          AND LENGTH(r.church_name) >= 8
    ''').fetchall()
    
    print(f'Unmatched WPA records to import: {len(unmatched):,}')
    
    # Count existing US churches for state default
    us_states = set(r[0] for r in churches.execute(
        "SELECT DISTINCT state FROM churches WHERE country='US'"
    ).fetchall())
    
    imported = 0
    batch = []
    source = 'wpa_historical_records_survey'
    
    cols = ['id', 'name', 'address', 'city', 'state', 'county', 'source',
            'landmark_type', 'tradition', 'notes', 'building_year', 'building_source',
            'country', 'confidence_score']
    
    for rec in unmatched:
        wpa_id, name, addr, city, county, state, denom, conf, raw, vol_year, vol_id = rec
        
        # Clean name
        name = name.strip()[:200]
        if len(name) < 5:
            continue
        
        # Default country to US for known states, else ''
        country = 'US' if state in us_states else ''
        
        rid = next_id
        next_id += 1
        
        batch.append((
            rid, name, addr or '', city or '', state or '', county or '',
            source, 'church', denom or '', 
            f'WPA Survey {vol_year}. OCR: {raw[:300] if raw else ""}',
            vol_year, source, country, conf or 0.5
        ))
        
        if len(batch) >= 500:
            placeholders = ', '.join(['?'] * len(cols))
            churches.executemany(
                f'INSERT INTO churches ({", ".join(cols)}) VALUES ({placeholders})',
                batch
            )
            churches.commit()
            imported += len(batch)
            print(f'  Imported: {imported:,}', end='\r')
            batch = []
    
    if batch:
        placeholders = ', '.join(['?'] * len(cols))
        churches.executemany(
            f'INSERT INTO churches ({", ".join(cols)}) VALUES ({placeholders})',
            batch
        )
        churches.commit()
        imported += len(batch)
    
    # Log provenance
    churches.execute(
        "INSERT INTO provenance_log (source, description, row_count) VALUES (?, ?, ?)",
        (source, f'WPA Historical Records Survey import: {imported} churches (1939-1942) from 47 volumes', imported)
    )
    
    # Log building_year enrichments from matches
    match_enrichments = churches.execute(
        "SELECT COUNT(*) FROM churches WHERE building_source='wpa_historical_records_survey'"
    ).fetchone()[0]
    if match_enrichments > 0:
        churches.execute(
            "INSERT INTO provenance_log (source, description, row_count) VALUES (?, ?, ?)",
            (source, f'WPA building_year enrichment: {match_enrichments} churches set to pre-1942', match_enrichments)
        )
    
    churches.commit()
    
    final = churches.execute('SELECT COUNT(*) FROM churches').fetchone()[0]
    
    # State breakdown of new records
    print(f'\n{"="*60}')
    print(f'MERGE COMPLETE')
    print(f'  Imported:     {imported:>8,}')
    print(f'  Building yrs: {match_enrichments:>8,}')
    print(f'  Final count:  {final:>8,}')
    
    print(f'\n  New records by state:')
    for st, cnt in churches.execute(
        "SELECT state, COUNT(*) FROM churches WHERE source='wpa_historical_records_survey' AND state != '' GROUP BY state ORDER BY COUNT(*) DESC LIMIT 15"
    ).fetchall():
        print(f'    {st:5s} {cnt:>8,}')
    
    no_state = churches.execute(
        "SELECT COUNT(*) FROM churches WHERE source='wpa_historical_records_survey' AND (state IS NULL OR state = '')"
    ).fetchone()[0]
    if no_state:
        print(f'    (none) {no_state:>8,}')
    
    wpa.close()
    churches.close()
    print('\nDone.')

if __name__ == '__main__':
    main()
