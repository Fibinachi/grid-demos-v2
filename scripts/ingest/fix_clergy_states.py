"""
Infer state from diocese for imported clergy entries.
Uses known diocese->state mapping.
"""
import sqlite3

CATH_DB = "E:/grid/data/catholic_directory.db"

# Diocese to state mapping (for historical US dioceses)
DIOCESE_STATES = {
    'BALTIMORE': 'MD', 'BALTIMORE': 'MD',
    'NEW YORK': 'NY', 'BROOKLYN': 'NY', 'ROCKVILLE CENTRE': 'NY',
    'SAINT LOUIS': 'MO', 'KANSAS CITY': 'MO',
    'PHILADELPHIA': 'PA', 'ERIE': 'PA', 'PITTSBURGH': 'PA',
    'CHICAGO': 'IL', 'MILWAUKEE': 'WI',
    'LOS ANGELES': 'CA', 'SAN FRANCISCO': 'CA', 'SAN DIEGO': 'CA',
    'BOSTON': 'MA', 'SPRINGFIELD': 'MA', 'FALL RIVER': 'MA',
    'DETROIT': 'MI', 'GRAND RAPIDS': 'MI',
    'SAN ANTONIO': 'TX', 'HOUSTON': 'TX', 'DALLAS': 'TX',
    'MIAMI': 'FL', 'ORLANDO': 'FL',
    'ATLANTA': 'GA', 'SAVANNAH': 'GA',
    'ALBANY': 'NY', 'BUFFALO': 'NY', 'ROCHESTER': 'NY', 'SYRACUSE': 'NY',
    'WASHINGTON': 'DC',
    'NEW ORLEANS': 'LA', 'BATON ROUGE': 'LA',
    'LOUISVILLE': 'KY',
    'NASHVILLE': 'TN',
    'INDIANAPOLIS': 'IN',
    'DENVER': 'CO', 'COLORADO SPRINGS': 'CO',
    'PORTLAND': 'OR', 'SEATTLE': 'WA',
    'SALT LAKE CITY': 'UT',
    'CHICAGO': 'IL',
    'ST. PAUL': 'MN', 'MINNEAPOLIS': 'MN',
    'KANSAS CITY': 'KS', 'WICHITA': 'KS',
}

def main():
    cath = sqlite3.connect(CATH_DB)
    
    # Get entries with no state
    entries = cath.execute('''
        SELECT id, diocese FROM dir_entries 
        WHERE state IS NULL AND diocese IS NOT NULL
    ''').fetchall()
    
    print(f"Fixing {len(entries):,} entries with missing state...")
    
    fixed = 0
    for eid, diocese in entries:
        if diocese and diocese in DIOCESE_STATES:
            state = DIOCESE_STATES[diocese]
            cath.execute('UPDATE dir_entries SET state=? WHERE id=?', (state, eid))
            fixed += 1
    
    cath.commit()
    print(f"Fixed {fixed:,} entries")
    
    # Check remaining
    remaining = cath.execute('''
        SELECT COUNT(*) FROM dir_entries WHERE state IS NULL
    ''').fetchone()[0]
    print(f"Still missing state: {remaining}")
    
    cath.close()

if __name__ == '__main__':
    main()