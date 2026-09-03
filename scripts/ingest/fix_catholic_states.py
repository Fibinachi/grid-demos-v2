"""
Fix OCR state errors in Catholic directory using diocese-to-state mapping, then match to GRID.
"""
import sqlite3

CATH_DB = "E:/grid/data/catholic_directory.db"
GRID_DB = "E:/grid/churches.db"

# Known US diocese to state mappings
DIOCESE_STATES = {
    # New York
    'Albany': 'NY', 'Buffalo': 'NY', 'Rochester': 'NY', 'New York': 'NY', 
    'Rockville Centre': 'NY', 'Syracuse': 'NY', 'Ogdensburg': 'NY', 'Rochester': 'NY',
    'Brooklyn': 'NY', 'Baltimore': 'MD', 'Washington': 'DC',
    # Pennsylvania  
    'Erie': 'PA', 'Pittsburgh': 'PA', 'Philadelphia': 'PA', 'Scranton': 'PA',
    'Harrisburg': 'PA', 'Allentown': 'PA',
    # Illinois
    'Chicago': 'IL', 'Milwaukee': 'WI',
    # California
    'San Francisco': 'CA', 'Los Angeles': 'CA', 'San Diego': 'CA', 
    'Sacramento': 'CA', 'San Jose': 'CA',
    # Texas
    'San Antonio': 'TX', 'Houston': 'TX', 'Dallas': 'TX', 'Austin': 'TX',
    'El Paso': 'TX',
    # Other states
    'New Orleans': 'LA', 'Miami': 'FL', 'Atlanta': 'GA', 'Cheyenne': 'WY',
    'San Juan': 'PR', 'Caguas': 'PR', 'Mayaguez': 'PR', 'Ponce': 'PR',
    'Colorado Springs': 'CO', 'Portland': 'OR', 'Seattle': 'WA',
    'Springfield': 'IL', 'Saginaw': 'MI', 'Grand Rapids': 'MI', 'Detroit': 'MI',
}

def main():
    cath = sqlite3.connect(CATH_DB)
    cath.row_factory = sqlite3.Row
    
    # Get invalid states
    bad_states = cath.execute('''
        SELECT DISTINCT state, diocese FROM dir_entries 
        WHERE state NOT IN ('AL','AK','AZ','AR','CA','CO','CT','DE','FL','GA','HI','ID','IL','IN','IA','KS','KY','LA','ME','MD','MA','MI','MN','MS','MO','MT','NE','NV','NH','NJ','NM','NY','NC','ND','OH','OK','OR','PA','RI','SC','SD','TN','TX','UT','VT','VA','WA','WV','WI','WY','DC','PR','QC')
    ''').fetchall()
    
    print(f"Fixing {len(bad_states)} OCR state errors...")
    
    for bad_state, diocese in bad_states:
        if not diocese:
            continue
        # Clean diocese name (remove OCR artifacts)
        clean_diocese = diocese.strip().rstrip(' who').rstrip(';').rstrip(',').strip()
        
        # Get state from mapping
        real_state = DIOCESE_STATES.get(clean_diocese)
        if real_state:
            print(f"  {bad_state} -> {real_state}: {clean_diocese}")
            cath.execute('UPDATE dir_entries SET state=? WHERE state=? AND diocese=?', (real_state, bad_state, diocese))
            cath.commit()
    
    # Count remaining invalid
    remaining = cath.execute('''
        SELECT COUNT(*) FROM dir_entries 
        WHERE state NOT IN ('AL','AK','AZ','AR','CA','CO','CT','DE','FL','GA','HI','ID','IL','IN','IA','KS','KY','LA','ME','MD','MA','MI','MN','MS','MO','MT','NE','NV','NH','NJ','NM','NY','NC','ND','OH','OK','OR','PA','RI','SC','SD','TN','TX','UT','VT','VA','WA','WV','WI','WY','DC','PR','QC')
    ''').fetchone()[0]
    print(f"\nRemaining invalid state count: {remaining}")
    
    cath.close()

if __name__ == '__main__':
    main()