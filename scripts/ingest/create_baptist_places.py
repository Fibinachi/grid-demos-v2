#!/usr/bin/env python3
"""
Create people and places tables from Baptist inventory data.
Extract locations and prepare for geocoding.
"""
import re, sqlite3
from pathlib import Path

DB_PATH = Path("E:/grid/wpa.db")

def create_places_table():
    conn = sqlite3.connect(str(DB_PATH))
    
    # Create places table for unique locations
    conn.execute("""CREATE TABLE IF NOT EXISTS wpa_places (
        id INTEGER PRIMARY KEY,
        place_name TEXT UNIQUE,
        state TEXT,
        place_type TEXT DEFAULT 'town',
        latitude REAL,
        longitude REAL,
        geocode_status TEXT DEFAULT 'pending'
    )""")
    
    # Extract unique locations
    locations = set()
    tables = ['wpa_baptist_ri', 'wpa_baptist_nc_yancey', 'wpa_baptist_nc_brunswick',
              'wpa_baptist_nc_central', 'wpa_baptist_nc_flatriver', 'wpa_baptist_nc_stanly',
              'wpa_baptist_nc_alleghany', 'wpa_baptist_nc_state', 'wpa_baptist_nj_baptist', 
              'wpa_baptist_ms_baptist', 'wpa_baptist_va_baptist_3']
    
    table_to_state = lambda t: t.split('_')[-2] if 'nc' in t else t.split('_')[2] if '_' in t else 'RI'
    
    for tbl in tables:
        state_map = {'nc': 'NC', 'nj': 'NJ', 'ms': 'MS', 'va': 'VA', 'ri': 'RI'}
        state = 'RI'
        for k, v in state_map.items():
            if k in tbl:
                state = v
                break
        
        rows = conn.execute(f"SELECT location FROM {tbl}").fetchall()
        for r in rows:
            loc = r[0]
            if loc and loc.strip() and len(loc) > 2:
                locations.add((loc.strip(), state))
    
    # Insert places
    conn.execute("DELETE FROM wpa_places")
    for loc, state in list(locations)[:500]:  # Limit for now
        conn.execute("INSERT OR IGNORE INTO wpa_places (place_name, state) VALUES (?,?)", (loc, state))
    
    conn.commit()
    
    print(f"Created wpa_places with {len(locations)} unique locations")
    print("\nSample:")
    for r in conn.execute("SELECT * FROM wpa_places LIMIT 15").fetchall():
        print(f"  {r}")
    
    conn.close()

if __name__ == "__main__":
    create_places_table()