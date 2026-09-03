#!/usr/bin/env python3
"""
Complete Baptist Inventory Processing:
1. Parse locations properly for geocoding
2. Match remaining entries to GRID
3. Extract pastor names for people table
"""
import sqlite3, re, json
from pathlib import Path

DB_PATH = Path("E:/grid/wpa.db")
CHURCHES_DB = Path("E:/grid/churches.db")

def clean_locations():
    """Extract clean city names from descriptive locations."""
    conn = sqlite3.connect(str(DB_PATH))
    
    # Get all Baptist locations
    locations = conn.execute("""
        SELECT DISTINCT location FROM wpa_baptist_churches 
        WHERE location IS NOT NULL AND location != ''
    """).fetchall()
    
    # Clean: extract city from "Kingston, South Kingstown" or "Cranston"
    cleaned = {}
    for (loc,) in locations:
        loc = loc.strip()
        if not loc:
            continue
        
        # Format: "CITY, COUNTY" or "CITY"
        parts = loc.split(',')
        city = parts[0].strip()
        
        # Remove parenthetical notes
        city = re.sub(r'\(.+?\)', '', city)
        
        cleaned[loc] = city
    
    # Update locations
    conn.execute("ALTER TABLE wpa_baptist_churches ADD COLUMN city_clean TEXT")
    
    for old, clean in cleaned.items():
        conn.execute("UPDATE wpa_baptist_churches SET city_clean = ? WHERE location = ?", (clean, old))
    
    conn.commit()
    print(f"Cleaned {len(cleaned)} locations")
    
    # Stats
    cities = conn.execute("SELECT city_clean, COUNT(*) as cnt FROM wpa_baptist_churches WHERE city_clean IS NOT NULL GROUP BY city_clean ORDER BY cnt DESC LIMIT 15").fetchall()
    print("\nTop cities:")
    for c in cities:
        print(f"  {c[0]}: {c[1]}")
    
    conn.close()

def match_by_city_name():
    """Match Baptist entries by city + name similarity."""
    wpa = sqlite3.connect(str(DB_PATH))
    grid = sqlite3.connect(str(CHURCHES_DB))
    
    wpa.execute("CREATE TABLE IF NOT EXISTS wpa_baptist_matches (wpa_id INTEGER, grid_id INTEGER, method TEXT)")
    
    # Get unmatched entries
    wpa_rows = wpa.execute("""
        SELECT id, church_name, city_clean, state, founding_year 
        FROM wpa_baptist_churches 
        WHERE id NOT IN (SELECT wpa_id FROM wpa_baptist_grid_links)
    """).fetchall()
    
    print(f"\nUnmatched entries: {len(wpa_rows)}")
    
    # Get grid churches indexed by state+city
    grid_churches = grid.execute("SELECT id, name, city, state FROM churches WHERE faith='Christian' AND state IS NOT NULL").fetchall()
    
    state_index = {}
    for c in grid_churches:
        st = (c[3] or '').upper()
        city = (c[2] or '').upper()
        state_index.setdefault((st, city), []).append(c)
    
    matches = 0
    for wpa_id, name, city, state, year in wpa_rows:
        if not city or not state:
            continue
        
        key = (state.upper(), city.upper())
        if key in state_index:
            for grid_church in state_index[key]:
                # Name similarity
                wpa_words = set(name.lower().replace('-', ' ').split()[:3])
                grid_words = set(grid_church[1].lower().split()[:3])
                overlap = len(wpa_words & grid_words)
                
                if overlap >= 2:
                    wpa.execute("INSERT INTO wpa_baptist_matches (wpa_id, grid_id, method) VALUES (?,?,?)",
                        (wpa_id, grid_church[0], f"name_overlap_{overlap}"))
                    matches += 1
                    break
    
    wpa.commit()
    print(f"Matched {matches} additional entries")
    
    wpa.close()
    grid.close()

def extract_pastor_patterns():
    """Look for pastor mentions in raw wpa_records."""
    conn = sqlite3.connect(str(DB_PATH))
    
    # Find pastor names in Baptist volume records
    rows = conn.execute("""
        SELECT church_name, raw_text, notes 
        FROM wpa_records 
        WHERE volume_id=38  -- RI Baptist
        AND (raw_text LIKE '%Pastor%' OR raw_text LIKE '%Minister%' OR raw_text LIKE '%Elder%' 
             OR church_name LIKE '%Pastor%' OR church_name LIKE '%minister%')
    """).fetchall()
    
    print(f"\nPastor mentions found in {len(rows)} records")
    
    pastors = set()
    for r in rows:
        combined = (r[0] or '') + ' ' + (r[1] or '') + ' ' + (r[2] or '')
        # Look for name patterns after "Pastor", "Minister", "Elder"
        for m in re.finditer(r'(?:Pastor|Minister|Elder|Rev\.?)\s+([A-Z][a-z]{2,20}(?:\s+[A-Z][a-z]{2,20})?)', combined):
            pastors.add(m.group(1))
    
    print(f"Unique pastor names: {len(pastors)}")
    for p in list(pastors)[:20]:
        print(f"  {p}")
    
    conn.close()

if __name__ == "__main__":
    clean_locations()
    match_by_city_name()
    extract_pastor_patterns()