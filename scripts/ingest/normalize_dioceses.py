"""
Normalize OCR-corrupted diocese names and match.
"""
import sqlite3, re

CATH_DB = "E:/grid/data/catholic_directory.db"

# Common OCR corruptions
DIOCESE_FIXES = {
    'albalsy': 'ALBANY', 'bttown': 'BALTIMORE', 'brooklun': 'BROOKLYN',
    'burlinaton': 'BURLINGTON', 'burlington': 'BURLINGTON', 'bytown': 'OTTAWA',
    'charleston *': 'CHARLESTON', 'charleston.': 'CHARLESTON', 'charleston,n': 'CHARLESTON',
    'alton': 'ALTON', 'arichat': 'ARICHAT', 'charleston': 'CHARLESTON',
    'charlottetown': 'CHARLOTTETOWN', 'chicago': 'CHICAGO', 'buffalo': 'BUFFALO',
}

STATE_MAP = {
    'ALBANY': 'NY', 'BALTIMORE': 'MD', 'BROOKLYN': 'NY', 'BUFFALO': 'NY',
    'BURLINGTON': 'VT', 'CHARLESTON': 'SC', 'CHARLOTTETOWN': 'PE', 'CHICAGO': 'IL',
    'BOSTON': 'MA', 'NEW YORK': 'NY', 'PHILADELPHIA': 'PA', 'SAN FRANCISCO': 'CA',
}

def main():
    db = sqlite3.connect(CATH_DB)
    
    # Update corrupted diocese names and infer states
    updated = 0
    for r in db.execute('SELECT id, diocese FROM dir_entries WHERE grid_church_id IS NULL AND diocese IS NOT NULL').fetchall():
        d_orig = r[1]
        d_clean = d_orig.lower().strip()
        d_clean = re.sub(r'[^*\.]', '', d_clean)  # Remove garbage chars
        d_clean = re.sub(r'\s+', ' ', d_clean).strip()
        
        # Try fixes
        d_norm = DIOCESE_FIXES.get(d_clean, d_clean.upper())
        
        # Get state
        state = STATE_MAP.get(d_norm, '')
        
        if d_norm != d_orig or state:
            db.execute('UPDATE dir_entries SET diocese=?, state=? WHERE id=?', (d_norm, state, r[0]))
            updated += 1
    
    db.commit()
    print(f"Updated {updated:,} entries")
    
    db.close()

if __name__ == '__main__':
    main()