"""
Aggressively clean diocese names and infer state.
"""
import sqlite3, re

CATH_DB = "E:/grid/data/catholic_directory.db"
GRID_DB = "E:/grid/churches.db"

# Known diocese patterns -> state
DIOCESE_PATTERNS = {
    r'ALBANY|ERIE|BUFFALO|ROCHESTER': 'NY',
    r'BALTIMORE': 'MD',
    r'PHILADELPHIA|PITTSBURGH|ERIE': 'PA',
    r'CHICAGO|MILWAUKEE': 'IL',
    r'LOS ANGELES|SAN FRANCISCO|SAN DIEGO': 'CA',
    r'BOSTON|SPRINGFIELD|FALL RIVER': 'MA',
    r'DETROIT|GRAND RAPIDS': 'MI',
    r'SAN ANTONIO|HOUSTON|DALLAS|FORT WORTH': 'TX',
    r'MIAMI|ORLANDO|TAMPA': 'FL',
    r'ATLANTA|SAVANNAH': 'GA',
    r'NEW ORLEANS|BATON ROUGE|SHREVEPORT': 'LA',
    r'LOUISVILLE|LEXINGTON': 'KY',
    r'NASHVILLE|KNOXVILLE|MEMPHIS': 'TN',
    r'SAINT LOUIS|KANSAS CITY': 'MO',
    r'SALT LAKE CITY': 'UT',
    r'MINNEAPOLIS|ST PAUL': 'MN',
    r'KANSAS CITY': 'KS',
    r'WASHINGTON': 'DC',
    r'DENVER|COLORADO SPRINGS': 'CO',
    r'PORTLAND|SEATTLE|SALT LAKE': 'UT',
}

def clean_diocese(d):
    """Clean OCR garbage from diocese name."""
    if not d:
        return d
    # Remove OCR artifacts
    d = re.sub(r'[0-9]+\s*T\.?\s*', '', d, flags=re.I)  # "6T. TAUL" -> "TAUL"
    d = re.sub(r'[.,;|]\s*[0-9,\s]+$', '', d)  # "ALTON. 147" -> "ALTON"
    d = re.sub(r'\s*[<>^]+\s*', ' ', d)  # remove stray chars
    d = d.strip('.,;:').strip()
    # Common misspellings
    fixes = {
        'CHICOUTIMI': 'QUEBEC', 'BYTOWN': 'OTTAWA', 'AVllEELING': 'ALEXANDRIA',
    }
    return fixes.get(d.upper(), d)

def main():
    cath = sqlite3.connect(CATH_DB)
    
    entries = cath.execute('''
        SELECT id, diocese, state FROM dir_entries 
        WHERE (state IS NULL OR state = '') AND diocese IS NOT NULL AND diocese != ''
    ''').fetchall()
    
    print(f"Processing {len(entries):,} entries...")
    
    fixed = 0
    for eid, diocese, state in entries:
        clean = clean_diocese(diocese)
        for pattern, st in DIOCESE_PATTERNS.items():
            if re.search(pattern, clean, re.I):
                cath.execute('UPDATE dir_entries SET state=? WHERE id=?', (st, eid))
                fixed += 1
                break
    
    cath.commit()
    print(f"Fixed {fixed:,} entries")
    
    remaining = cath.execute('SELECT COUNT(*) FROM dir_entries WHERE state IS NULL').fetchone()[0]
    print(f"Still missing state: {remaining}")
    
    cath.close()

if __name__ == '__main__':
    main()