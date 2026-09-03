"""
Identify years needing DeepSeek parsing and run the parser.
"""
import sqlite3
from pathlib import Path

CATH_DB = "E:/grid/data/catholic_directory.db"
DIR_DIR = Path("E:/grid/data/directories")

def main():
    cath = sqlite3.connect(CATH_DB)
    
    # Years in DB
    db_years = set(r[0] for r in cath.execute('SELECT DISTINCT directory_year FROM dir_entries').fetchall())
    
    # Years with formatted files available
    available = set()
    for f in DIR_DIR.glob('catholic_dir_*_formatted.txt'):
        try:
            year = int(f.stem.split('_')[2])
            available.add(year)
        except:
            pass
    
    # Years needing parsing (not in DB but files exist)
    need_parse = sorted(available - db_years)
    print(f"Years needing DeepSeek parsing: {len(need_parse)}")
    print(f"Missing: {need_parse}")
    
    cath.close()

if __name__ == '__main__':
    main()