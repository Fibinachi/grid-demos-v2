#!/usr/bin/env python3
"""
Create final Baptist data structure:
- wpa_baptist_people: pastor names with church references
- wpa_baptist_places: clean geographic locations  
- wpa_baptist_churches: unified church records with GRID links
"""
import sqlite3, re, json
from pathlib import Path

DB_PATH = Path("E:/grid/wpa.db")

def create_final_schema():
    conn = sqlite3.connect(str(DB_PATH))
    
    # People table
    conn.execute("""CREATE TABLE IF NOT EXISTS wpa_baptist_people (
        id INTEGER PRIMARY KEY,
        person_name TEXT,
        role TEXT DEFAULT 'pastor',
        church_reference TEXT,
        state TEXT
    )""")
    conn.execute("DELETE FROM wpa_baptist_people")
    
    # Extract proper pastor names from raw records
    # Look for patterns like "Dr. Arthur W. Cleaves, pastor of..."
    rows = conn.execute("""
        SELECT raw_text, church_name, notes FROM wpa_records WHERE volume_id=38
        AND (raw_text LIKE '%Pastor%' OR church_name LIKE '%Pastor%' OR notes LIKE '%Pastor%')
    """).fetchall()
    
    people = set()
    for r in rows:
        combined = (r[0] or '') + ' ' + (r[1] or '') + ' ' + (r[2] or '')
        for m in re.finditer(r'(?:Dr\.|Rev\.?|Pastor|Elder)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)', combined):
            name = m.group(1).strip()
            if len(name) > 3 and name not in ['Pastor', 'Baptist', 'Church']:
                people.add(name)
    
    for p in people:
        conn.execute("INSERT INTO wpa_baptist_people (person_name, state) VALUES (?,?)", (p, 'RI'))
    
    print(f"Extracted {len(people)} unique pastor names")
    
    # Places table with proper schema
    conn.execute("""CREATE TABLE IF NOT EXISTS wpa_baptist_places (
        id INTEGER PRIMARY KEY,
        place_name TEXT UNIQUE,
        state TEXT,
        city TEXT,
        county TEXT
    )""")
    conn.execute("DELETE FROM wpa_baptist_places")
    
    # Extract unique locations
    locs = conn.execute("SELECT DISTINCT location, state FROM wpa_baptist_churches WHERE location IS NOT NULL").fetchall()
    
    for loc, state in locs:
        loc = loc.strip()
        parts = loc.split(',')
        city = parts[0].strip() if parts else loc
        county = parts[1].strip() if len(parts) > 1 else None
        
        conn.execute("INSERT OR IGNORE INTO wpa_baptist_places (place_name, state, city, county) VALUES (?,?,?,?)",
            (loc, state or 'RI', city, county))
    
    conn.commit()
    
    # Stats
    c = conn.execute("SELECT COUNT(*) FROM wpa_baptist_places")
    print(f"Places: {c.fetchone()[0]}")
    
    c = conn.execute("SELECT COUNT(*) FROM wpa_baptist_churches")
    print(f"Churches: {c.fetchone()[0]}")
    
    c = conn.execute("SELECT COUNT(*) FROM wpa_baptist_grid_links")
    print(f"GRID matches: {c.fetchone()[0]}")
    
    c = conn.execute("SELECT COUNT(*) FROM wpa_baptist_matches")
    print(f"Additional matches: {c.fetchone()[0]}")
    
    conn.close()

if __name__ == "__main__":
    create_final_schema()