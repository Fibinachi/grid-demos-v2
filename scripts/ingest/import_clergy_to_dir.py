"""
Import catholic_clergy assignments from churches.db into catholic_directory.db.
This fills in years 1839-1946 with proper clergy data.
"""
import sqlite3, csv

CATH_DB = "E:/grid/data/catholic_directory.db"
GRID_DB = "E:/grid/churches.db"

def main():
    cath = sqlite3.connect(CATH_DB)
    grid = sqlite3.connect(GRID_DB)
    grid.row_factory = sqlite3.Row
    
    # Get years already in catholic_directory.db (excluding clergy years which are 1839-1946)
    existing = set(r[0] for r in cath.execute(
        'SELECT DISTINCT directory_year FROM dir_entries'
    ).fetchall())
    
    print(f"Existing years in DB: {sorted(existing)[:10]}...")
    
    # Load clergy assignments
    clergy_rows = grid.execute('''
        SELECT id, year, diocese, city, parish, priest_name, title, religious_order, role, source_file, source_line
        FROM catholic_clergy
        ORDER BY year, id
    ''').fetchall()
    
    print(f"Loading {len(clergy_rows):,} clergy assignments...")
    
    # Group by parish (unique entries)
    seen = set()
    added = 0
    
    for row in clergy_rows:
        rid, year, diocese, city_raw, parish, priest_name, title, religious_order, role, source_file, source_line = row
        
        # Skip years already in DB (those were parsed via DeepSeek)
        if year in existing:
            continue
        
        # Extract city/state from city field
        city = city_raw or ''
        state = None
        if ',' in city:
            parts = city.rsplit(',', 1)
            city = parts[0].strip()
            state = parts[1].strip()[:2].upper()
        
        key = (year, diocese, city, parish)
        if key in seen:
            continue
        seen.add(key)
        
        cath.execute('''
            INSERT INTO dir_entries (directory_year, source_entry_id, name, city, state, diocese, entity_type, notes)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (year, f"clergy_{rid}", parish,
              city, state, diocese, 'parish',
              f"[Catholic Directory {year}] Clergy: {priest_name}" + (f" {title}" if title else "")))
        
        added += 1
    
    cath.commit()
    print(f"Added {added:,} clergy-based entries")
    
    # Verify
    years = cath.execute('SELECT directory_year, COUNT(*) FROM dir_entries GROUP BY directory_year ORDER BY directory_year').fetchall()
    print(f"\nTotal years in DB: {len(years)}")
    print("First 10 years:")
    for y, c in years[:10]:
        print(f"  {y}: {c:,}")
    
    cath.close()
    grid.close()

if __name__ == '__main__':
    main()