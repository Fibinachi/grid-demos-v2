"""Export Catholic directory data from both databases to CSV files."""
import sqlite3
import csv
from pathlib import Path

OUTPUT_DIR = Path("E:/grid/data/denom")

def export_dir_entries():
    """Export dir_entries from catholic_directory.db to CSV."""
    db = sqlite3.connect('E:/grid/data/catholic_directory.db')
    db.row_factory = sqlite3.Row
    
    cols = [c[1] for c in db.execute('PRAGMA table_info(dir_entries)').fetchall()]
    
    rows = db.execute('SELECT * FROM dir_entries ORDER BY directory_year, id').fetchall()
    
    csv_path = OUTPUT_DIR / "catholic_directories_all_years.csv"
    with open(csv_path, 'w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        for row in rows:
            w.writerow(dict(row))
    
    print(f"Exported {len(rows):,} entries to {csv_path}")
    db.close()

def export_catholic_clergy():
    """Export catholic_clergy from churches.db to CSV."""
    db = sqlite3.connect('E:/grid/churches.db')
    
    rows = db.execute('''
        SELECT year, diocese, city, parish, priest_name, title, religious_order, role, 
               source_file, source_line
        FROM catholic_clergy 
        ORDER BY year, id
    ''').fetchall()
    
    cols = ['year', 'diocese', 'city', 'parish', 'priest_name', 'title', 'religious_order', 'role', 'source_file', 'source_line']
    
    csv_path = OUTPUT_DIR / "catholic_clergy_1839_1946.csv"
    with open(csv_path, 'w', newline='', encoding='utf-8') as f:
        w = csv.writer(f)
        w.writerow(cols)
        for row in rows:
            w.writerow(row)
    
    print(f"Exported {len(rows):,} assignments to {csv_path}")
    db.close()

if __name__ == '__main__':
    export_dir_entries()
    export_catholic_clergy()
    print("\nDone. Both CSV files exported to E:/grid/data/denom/")