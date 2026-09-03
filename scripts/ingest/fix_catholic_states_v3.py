"""
Final cleanup of Catholic directory states - fix full state names and international codes.
"""
import sqlite3

CATH_DB = "E:/grid/data/catholic_directory.db"

def fix_state_full(val):
    """Convert full state/province names to proper codes."""
    m = {
        'ALBERTA': 'AB', 'ONTARIO': 'ON', 'QUEBEC': 'QC', 'BRITISH COLUMBIA': 'BC', 'MANITOBA': 'MB',
        'TEXAS': 'TX', 'OHIO': 'OH', 'CONNECTICUT': 'CT', 'NEW MEXICO': 'NM', 'COLORADO': 'CO',
        'MONTANA': 'MT', 'INDIANA': 'IN', 'TENNESSEE': 'TN', 'KENTUCKY': 'KY',
    }
    val_upper = val.upper().strip() if val else val
    return m.get(val_upper, val)

def main():
    cath = sqlite3.connect(CATH_DB)
    
    # Fix full state names
    print("Fixing full state names...")
    
    # Get all distinctive invalid values
    invalid = cath.execute('''
        SELECT DISTINCT state FROM dir_entries 
        WHERE state NOT IN (SELECT DISTINCT state FROM dir_entries WHERE state IN ('AL','AK','AZ','AR','CA','CO','CT','DE','FL','GA','HI','ID','IL','IN','IA','KS','KY','LA','ME','MD','MA','MI','MN','MS','MO','MT','NE','NV','NH','NJ','NM','NY','NC','ND','OH','OK','OR','PA','RI','SC','SD','TN','TX','UT','VT','VA','WA','WV','WI','WY','DC','PR','QC','AB','ON','BC'))
    ''').fetchall()
    
    fixed = 0
    for (s,) in invalid:
        if not s:
            continue
        new_s = fix_state_full(s)
        if new_s != s:
            cnt = cath.execute('UPDATE dir_entries SET state=? WHERE state=?', (new_s, s)).rowcount
            fixed += cnt
    
    cath.commit()
    print(f"Fixed {fixed} full state names")
    
    # Remaining check
    remaining = cath.execute('''
        SELECT COUNT(*) FROM dir_entries 
        WHERE state NOT IN ('AL','AK','AZ','AR','CA','CO','CT','DE','FL','GA','HI','ID','IL','IN','IA','KS','KY','LA','ME','MD','MA','MI','MN','MS','MO','MT','NE','NV','NH','NJ','NM','NY','NC','ND','OH','OK','OR','PA','RI','SC','SD','TN','TX','UT','VT','VA','WA','WV','WI','WY','DC','PR','QC','AB','ON','BC')
    ''').fetchone()[0]
    print(f"Remaining invalid: {remaining}")
    
    # Show what's left
    left = cath.execute('''
        SELECT DISTINCT state, diocese FROM dir_entries 
        WHERE state NOT IN ('AL','AK','AZ','AR','CA','CO','CT','DE','FL','GA','HI','ID','IL','IN','IA','KS','KY','LA','ME','MD','MA','MI','MN','MS','MO','MT','NE','NV','NH','NJ','NM','NY','NC','ND','OH','OK','OR','PA','RI','SC','SD','TN','TX','UT','VT','VA','WA','WV','WI','WY','DC','PR','QC','AB','ON','BC')
        LIMIT 20
    ''').fetchall()
    print("Sample remaining:")
    for s, d in left:
        print(f"  {s}: {d}")
    
    cath.close()

if __name__ == '__main__':
    main()