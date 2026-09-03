#!/usr/bin/env python3
"""
Merge all Baptist inventory tables into unified wpa_baptist_churches.
Handles different schemas (some have entry_number, some don't).
"""
import re, sqlite3
from pathlib import Path

DB_PATH = Path("E:/grid/wpa.db")

def merge_baptist_tables():
    conn = sqlite3.connect(str(DB_PATH))
    
    # Create unified table
    conn.execute("""CREATE TABLE IF NOT EXISTS wpa_baptist_churches (
        id INTEGER PRIMARY KEY,
        source_volume TEXT,
        entry_number INTEGER,
        church_name TEXT,
        dates TEXT,
        location TEXT,
        founding_year INTEGER,
        closing_year INTEGER,
        state TEXT
    )""")
    conn.execute("DELETE FROM wpa_baptist_churches")
    
    # Get all Baptist tables
    tables = [r[0] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name LIKE 'wpa_baptist%' AND name != 'wpa_baptist_churches'"
    ).fetchall()]
    
    total = 0
    for tbl in tables:
        state = 'RI'
        if 'nc' in tbl:
            state = 'NC'
        elif 'nj' in tbl:
            state = 'NJ'
        elif 'ms' in tbl:
            state = 'MS'
        elif 'va' in tbl:
            state = 'VA'
        
        # Check schema
        cols = [r[1] for r in conn.execute(f"PRAGMA table_info({tbl})").fetchall()]
        has_entry_num = 'entry_number' in cols
        
        if has_entry_num:
            rows = conn.execute(f"SELECT entry_number, church_name, dates, location, founding_year, closing_year FROM {tbl}").fetchall()
            for r in rows:
                conn.execute("""INSERT INTO wpa_baptist_churches 
                    (source_volume, entry_number, church_name, dates, location, founding_year, closing_year, state)
                    VALUES (?,?,?,?,?,?,?,?)""",
                    (tbl, r[0], r[1], r[2], r[3], r[4], r[5], state))
        else:
            # ri_export schema
            rows = conn.execute(f"SELECT church_name, dates, location, founding_year, closing_year FROM {tbl}").fetchall()
            for r in rows:
                conn.execute("""INSERT INTO wpa_baptist_churches 
                    (source_volume, entry_number, church_name, dates, location, founding_year, closing_year, state)
                    VALUES (?,?,?,?,?,?,?,?)""",
                    (tbl, None, r[0], r[1], r[2], r[3], r[4], state))
        
        print(f"{tbl}: {len(rows)} rows")
        total += len(rows)
    
    conn.commit()
    print(f"\nTotal merged: {total} entries")
    
    # Stats by state
    print("\nBy state:")
    for r in conn.execute("SELECT state, COUNT(*) FROM wpa_baptist_churches GROUP BY state").fetchall():
        print(f"  {r[0]}: {r[1]}")
    
    # Stats with founding years
    print("\nWith founding years:")
    for r in conn.execute("SELECT state, COUNT(*) FROM wpa_baptist_churches WHERE founding_year IS NOT NULL GROUP BY state").fetchall():
        print(f"  {r[0]}: {r[1]}")
    
    # Sample
    print("\nSample entries:")
    for r in conn.execute("SELECT * FROM wpa_baptist_churches ORDER BY founding_year LIMIT 10").fetchall():
        print(f"  {r[2]}: {r[3]} [{r[4]}] - {r[5]}")
    
    conn.close()

if __name__ == "__main__":
    merge_baptist_tables()