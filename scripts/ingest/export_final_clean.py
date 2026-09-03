"""
Final export: Create clean, deduplicated CSV for all years.
"""
import csv, re, sqlite3
from pathlib import Path

CATH_DB = "E:/grid/data/catholic_directory.db"
OUTPUT_DIR = Path("E:/grid/data/denom")

def build_diocese_states():
    db = sqlite3.connect('E:/grid/churches.db')
    mapping = {}
    for r in db.execute('SELECT diocese, state FROM catholic_hierarchy').fetchall():
        if r[0] and r[1]:
            d = re.sub(r'^(?:arch|archdiocese|diocese)\s+of\s+', '', r[0], flags=re.I).strip().lower()
            mapping[d] = r[1].strip().upper()
    db.close()
    return mapping

def main():
    db = sqlite3.connect(CATH_DB)
    db.row_factory = sqlite3.Row
    
    mapping = build_diocese_states()
    
    # Export all entries with cleaned data
    rows = db.execute('''
        SELECT directory_year, name, city, state, diocese, grid_church_id
        FROM dir_entries
        WHERE name IS NOT NULL AND name != ''
        ORDER BY directory_year, diocese, name
    ''').fetchall()
    
    output = []
    for r in rows:
        diocese = r['diocese'] or ''
        state = r['state'] or ''
        
        # Clean diocese
        d_clean = re.sub(r'^.*(diocese|archdiocese)\s+of\s+', '', diocese, flags=re.I).strip()
        
        # Infer state if missing
        if not state or state not in 'AL,AK,AZ,AR,CA,CO,CT,DE,FL,GA,HI,ID,IL,IN,IA,KS,KY,LA,ME,MD,MA,MI,MN,MS,MO,MT,NE,NV,NH,NJ,NM,NY,NC,ND,OH,OK,OR,PA,RI,SC,SD,TN,TX,UT,VT,VA,WA,WV,WI,WY,DC,PR,QC'.split(','):
            state = mapping.get(d_clean.lower(), '')
        
        output.append({
            'year': r['directory_year'],
            'name': r['name'],
            'diocese': d_clean,
            'state': state,
            'city': r['city'] or '',
            'grid_church_id': r['grid_church_id'] or '',
        })
    
    # Deduplicate
    seen = set()
    final = []
    for r in output:
        key = (r['year'], r['diocese'], r['name'])
        if key not in seen:
            seen.add(key)
            final.append(r)
    
    # Write
    out_path = OUTPUT_DIR / 'catholic_directories_final_clean.csv'
    with open(out_path, 'w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=['year', 'name', 'diocese', 'state', 'city', 'grid_church_id'])
        w.writeheader()
        w.writerows(final)
    
    print(f"Exported {len(final):,} clean entries to {out_path}")
    
    # Stats
    matched = sum(1 for r in final if r['grid_church_id'])
    print(f"Matched: {matched:,} ({100*matched/len(final):.1f}%)")
    
    db.close()

if __name__ == '__main__':
    main()