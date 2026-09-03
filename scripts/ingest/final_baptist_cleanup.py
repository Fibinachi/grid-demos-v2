#!/usr/bin/env python3
"""
Clean Baptist locations aggressively and extract relationships.
"""
import sqlite3, re
from pathlib import Path

DB_PATH = Path("E:/grid/wpa.db")
CHURCHES_DB = Path("E:/grid/churches.db")

def clean_locations():
    """Parse CITY, COUNTY format and remove all OCR artifacts."""
    wpa = sqlite3.connect(str(DB_PATH))
    
    places = wpa.execute("SELECT id, place_name FROM wpa_baptist_places WHERE place_name IS NOT NULL").fetchall()
    
    cleaned = 0
    for pid, loc in places:
        if not loc:
            continue
        
        # Remove all OCR artifacts
        clean = loc.strip()
        clean = re.sub(r'\s*\.\s*\d+\s*$', '', clean)
        clean = re.sub(r'\s+\.\s+', ' ', clean)
        clean = re.sub(r'[>\*\-]', '', clean)
        clean = re.sub(r'\s+', ' ', clean).strip()
        
        parts = [p.strip() for p in clean.split(',')]
        city = parts[0] if parts else clean
        county = parts[1] if len(parts) > 1 else None
        
        wpa.execute("UPDATE wpa_baptist_places SET city = ?, county = ? WHERE id = ?",
            (city, county, pid))
        cleaned += 1
    
    wpa.commit()
    print(f"Cleaned {cleaned} locations")
    
    # Show sample
    sample = wpa.execute("SELECT place_name, city, county FROM wpa_baptist_places LIMIT 10").fetchall()
    print("\nSample cleaned:")
    for loc, city, county in sample:
        print(f"  {loc} -> {city}, {county}")
    
    wpa.close()

def geocode_cleaned():
    """Re-geocode with cleaned city names."""
    wpa = sqlite3.connect(str(DB_PATH))
    grid = sqlite3.connect(str(CHURCHES_DB))
    
    cities = grid.execute("SELECT city, state, AVG(latitude) as lat, AVG(longitude) as lon FROM churches WHERE latitude IS NOT NULL AND city IS NOT NULL GROUP BY city, state").fetchall()
    
    city_coords = {}
    for city, state, lat, lon in cities:
        if not state or not city:
            continue
        key = f"{city.strip().lower()}, {state.strip().upper()}"
        city_coords[key] = (lat, lon)
    
    places = wpa.execute("SELECT id, city, state FROM wpa_baptist_places WHERE latitude IS NULL AND city IS NOT NULL").fetchall()
    
    matched = 0
    for pid, city, state in places:
        if not city or not state:
            continue
        
        key = f"{city.lower()}, {state.upper()}"
        if key in city_coords:
            lat, lon = city_coords[key]
            wpa.execute("UPDATE wpa_baptist_places SET latitude=?, longitude=? WHERE id=?", (lat, lon, pid))
            matched += 1
    
    wpa.commit()
    print(f"Matched {matched} places via cleaned city lookup")
    
    wpa.execute("UPDATE wpa_baptist_churches SET latitude = (SELECT latitude FROM wpa_baptist_places WHERE place_name = wpa_baptist_churches.location), longitude = (SELECT longitude FROM wpa_baptist_places WHERE place_name = wpa_baptist_churches.location)")
    wpa.commit()
    
    c = wpa.execute("SELECT COUNT(*) FROM wpa_baptist_places WHERE latitude IS NOT NULL")
    print(f"Places with GPS: {c.fetchone()[0]}")
    
    c = wpa.execute("SELECT COUNT(*) FROM wpa_baptist_churches WHERE latitude IS NOT NULL")
    print(f"Churches with GPS: {c.fetchone()[0]}")
    
    wpa.close()
    grid.close()

def extract_relationships():
    """Extract pastor names and associations from raw text."""
    wpa = sqlite3.connect(str(DB_PATH))
    
    wpa.execute("""CREATE TABLE IF NOT EXISTS wpa_baptist_pastors (
        id INTEGER PRIMARY KEY, pastor_name TEXT, church_name TEXT, state TEXT
    )""")
    wpa.execute("DELETE FROM wpa_baptist_pastors")
    
    wpa.execute("""CREATE TABLE IF NOT EXISTS wpa_baptist_associations (
        id INTEGER PRIMARY KEY, association_name TEXT, state TEXT
    )""")
    wpa.execute("DELETE FROM wpa_baptist_associations")
    
    rows = wpa.execute("SELECT church_name, raw_text, notes FROM wpa_records WHERE volume_id=38").fetchall()
    
    pastors = []
    associations = set()
    
    for r in rows:
        combined = (r[0] or '') + ' ' + (r[1] or '') + ' ' + (r[2] or '')
        
        for m in re.finditer(r'(?:Pastor|Minister|Elder|Rev\.?)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)', combined):
            name = m.group(1).strip()
            if len(name) > 3 and name not in ['Pastor', 'Baptist', 'Church', 'Six', 'Principle']:
                pastors.append((name, r[0] or '', 'RI'))
        
        for m in re.finditer(r'([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\s+Association', combined):
            assoc = m.group(1).strip()
            if len(assoc) > 3 and assoc not in ['Baptist', 'Six', 'Principle']:
                associations.add(assoc)
    
    for name, church, state in pastors:
        wpa.execute("INSERT INTO wpa_baptist_pastors (pastor_name, church_name, state) VALUES (?,?,?)", (name, church, state))
    
    for assoc in associations:
        wpa.execute("INSERT INTO wpa_baptist_associations (association_name, state) VALUES (?,?)", (assoc, 'RI'))
    
    wpa.commit()
    
    print(f"\nExtracted {len(pastors)} pastor mentions")
    print(f"Extracted {len(associations)} associations")
    
    sample = wpa.execute("SELECT DISTINCT pastor_name FROM wpa_baptist_pastors LIMIT 10").fetchall()
    print("\nSample pastors:")
    for p in sample:
        print(f"  {p[0]}")
    
    wpa.close()

if __name__ == "__main__":
    clean_locations()
    geocode_cleaned()
    extract_relationships()