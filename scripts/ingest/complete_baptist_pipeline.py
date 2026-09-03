#!/usr/bin/env python3
"""
WPA Baptist Inventory - Complete Processing Pipeline.
Geocode, link, build relationships, import to GRID.
"""
import sqlite3, re, json, requests, time, math
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

WPA_DB = Path("E:/grid/wpa.db")
CHURCHES_DB = Path("E:/grid/churches.db")
NOMINATIM_URL = "http://localhost:8080/search"

def geocode_via_nominatim():
    """Geocode all places with no GPS via Nominatim."""
    wpa = sqlite3.connect(str(WPA_DB))
    wpa.row_factory = sqlite3.Row
    
    places = wpa.execute("""
        SELECT id, place_name, state FROM wpa_baptist_places 
        WHERE latitude IS NULL AND place_name IS NOT NULL AND place_name != ''
    """).fetchall()
    
    print(f"Geocoding {len(places)} places via Nominatim...")
    
    def geocode_one(place):
        pid = place['id']
        name = place['place_name']
        state = place['state'] or ''
        
        # Clean name
        clean = re.sub(r'[.,*\->]', '', name).strip()
        clean = re.sub(r'\s+', ' ', clean)
        
        # Try with state
        query = f"{clean}, {state}, USA" if state else f"{clean}, USA"
        
        try:
            r = requests.get(NOMINATIM_URL, params={
                'q': query,
                'format': 'json',
                'limit': 1
            }, timeout=10)
            if r.status_code == 200 and r.json():
                result = r.json()[0]
                return (pid, float(result['lat']), float(result['lon']))
        except:
            pass
        
        # Try without state
        try:
            r = requests.get(NOMINATIM_URL, params={
                'q': f"{clean}, USA",
                'format': 'json',
                'limit': 1
            }, timeout=10)
            if r.status_code == 200 and r.json():
                result = r.json()[0]
                return (pid, float(result['lat']), float(result['lon']))
        except:
            pass
        
        return None
    
    results = []
    with ThreadPoolExecutor(max_workers=4) as executor:
        futures = {executor.submit(geocode_one, p): p for p in places}
        for i, future in enumerate(as_completed(futures), 1):
            result = future.result()
            if result:
                results.append(result)
            if i % 50 == 0:
                print(f"  Progress: {i}/{len(places)}")
    
    # Update database
    for pid, lat, lon in results:
        wpa.execute("UPDATE wpa_baptist_places SET latitude=?, longitude=? WHERE id=?",
                   (lat, lon, pid))
    
    wpa.commit()
    print(f"Geocoded {len(results)} places")
    
    # Update churches with GPS from places
    wpa.execute("""
        UPDATE wpa_baptist_churches 
        SET latitude = (SELECT latitude FROM wpa_baptist_places WHERE place_name = wpa_baptist_churches.location),
            longitude = (SELECT longitude FROM wpa_baptist_places WHERE place_name = wpa_baptist_churches.location)
        WHERE latitude IS NULL
    """)
    wpa.commit()
    
    c = wpa.execute("SELECT COUNT(*) FROM wpa_baptist_churches WHERE latitude IS NOT NULL").fetchone()[0]
    print(f"Churches with GPS: {c}")
    
    wpa.close()

def link_to_grid():
    """Link all Baptist churches to GRID by name+state+city."""
    wpa = sqlite3.connect(str(WPA_DB))
    grid = sqlite3.connect(str(CHURCHES_DB))
    
    wpa.row_factory = sqlite3.Row
    grid.row_factory = sqlite3.Row
    
    # Get all Baptist churches
    churches = wpa.execute("SELECT id, church_name, location, state FROM wpa_baptist_churches").fetchall()
    
    # Get GRID churches indexed by state
    grid_churches = grid.execute("""
        SELECT id, name, city, state, latitude, longitude 
        FROM churches WHERE state IS NOT NULL
    """).fetchall()
    
    state_index = {}
    for c in grid_churches:
        state = c['state'].upper()
        state_index.setdefault(state, []).append(c)
    
    print(f"Linking {len(churches)} Baptist churches to GRID...")
    
    wpa.execute("DELETE FROM wpa_baptist_grid_links")
    
    matches = 0
    for ch in churches:
        wpa_id = ch['id']
        name = (ch['church_name'] or '').lower()
        location = (ch['location'] or '').lower()
        state = (ch['state'] or '').upper()
        
        if not state or state not in state_index:
            continue
        
        best_match = None
        best_score = 0
        
        for grid_ch in state_index[state]:
            grid_name = grid_ch['name'].lower()
            grid_city = (grid_ch['city'] or '').lower()
            
            # Name similarity
            name_words = set(name.split())
            grid_words = set(grid_name.split())
            overlap = len(name_words & grid_words)
            score = overlap
            
            # City bonus
            if location and grid_city and location in grid_city:
                score += 2
            
            if score > best_score and score >= 3:
                best_score = score
                best_match = grid_ch
        
        if best_match:
            wpa.execute("""
                INSERT INTO wpa_baptist_grid_links (wpa_id, grid_church_id, match_method, match_score, notes)
                VALUES (?, ?, 'name_city', ?, ?)
            """, (wpa_id, best_match['id'], best_score, f"Score: {best_score}"))
            matches += 1
    
    wpa.commit()
    print(f"Linked {matches} churches to GRID")
    
    wpa.close()
    grid.close()

def build_pastor_relationships():
    """Build pastor-to-church relationships from raw text."""
    wpa = sqlite3.connect(str(WPA_DB))
    wpa.row_factory = sqlite3.Row
    
    # Get all pastor mentions with context
    rows = wpa.execute("""
        SELECT id, church_name, raw_text, notes 
        FROM wpa_records 
        WHERE volume_id IN (38, 13, 14, 15, 21, 22, 24, 25, 35, 36, 42, 43, 44)
    """).fetchall()
    
    print(f"Extracting pastor relationships from {len(rows)} records...")
    
    wpa.execute("""
        CREATE TABLE IF NOT EXISTS wpa_baptist_pastor_church (
            pastor_id INTEGER,
            church_id INTEGER,
            role TEXT,
            years TEXT
        )
    """)
    wpa.execute("DELETE FROM wpa_baptist_pastor_church")
    
    relationships = []
    
    for row in rows:
        text = f"{row['church_name'] or ''} {row['raw_text'] or ''} {row['notes'] or ''}"
        
        # Pattern: "Pastor Name" or "Rev. Name" or "Elder Name"
        for m in re.finditer(r'(?:Pastor|Rev\.?|Elder)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)', text):
            pastor_name = m.group(1).strip()
            
            # Find church name in context
            church_match = re.search(r'([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\s+(?:Baptist\s+)?Church', text)
            if church_match:
                church_name = church_match.group(1).strip()
                
                # Find years
                years_match = re.search(r'(\d{4}(?:\s*-\s*\d{4})?)', text[m.end():m.end()+50])
                years = years_match.group(1) if years_match else None
                
                relationships.append((pastor_name, church_name, 'pastor', years))
    
    # Insert relationships
    for pastor, church, role, years in relationships:
        wpa.execute("""
            INSERT INTO wpa_baptist_pastor_church (pastor_id, church_id, role, years)
            SELECT p.id, c.id, ?, ?
            FROM wpa_baptist_pastors p, wpa_baptist_churches c
            WHERE p.pastor_name = ? AND c.church_name LIKE ?
        """, (role, years, pastor, f"%{church}%"))
    
    wpa.commit()
    c = wpa.execute("SELECT COUNT(*) FROM wpa_baptist_pastor_church").fetchone()[0]
    print(f"Built {c} pastor-church relationships")
    
    wpa.close()

def build_association_relationships():
    """Build association-to-church relationships."""
    wpa = sqlite3.connect(str(WPA_DB))
    wpa.row_factory = sqlite3.Row
    
    # Get all records with association mentions
    rows = wpa.execute("""
        SELECT id, church_name, raw_text, notes 
        FROM wpa_records 
        WHERE volume_id IN (38, 13, 14, 15, 21, 22, 24, 25, 35, 36, 42, 43, 44)
        AND (raw_text LIKE '%Association%' OR notes LIKE '%Association%')
    """).fetchall()
    
    print(f"Extracting association relationships from {len(rows)} records...")
    
    wpa.execute("""
        CREATE TABLE IF NOT EXISTS wpa_baptist_church_association (
            church_id INTEGER,
            association_id INTEGER,
            years TEXT
        )
    """)
    wpa.execute("DELETE FROM wpa_baptist_church_association")
    
    relationships = []
    
    for row in rows:
        text = f"{row['church_name'] or ''} {row['raw_text'] or ''} {row['notes'] or ''}"
        
        # Find association name
        assoc_match = re.search(r'([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\s+Association', text)
        if assoc_match:
            assoc_name = assoc_match.group(1).strip() + " Association"
            
            # Find church name
            church_match = re.search(r'([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\s+(?:Baptist\s+)?Church', text)
            if church_match:
                church_name = church_match.group(1).strip()
                
                # Find years
                years_match = re.search(r'(\d{4}(?:\s*-\s*\d{4})?)', text)
                years = years_match.group(1) if years_match else None
                
                relationships.append((church_name, assoc_name, years))
    
    # Insert relationships
    for church, assoc, years in relationships:
        wpa.execute("""
            INSERT INTO wpa_baptist_church_association (church_id, association_id, years)
            SELECT c.id, a.id, ?
            FROM wpa_baptist_churches c, wpa_baptist_associations a
            WHERE c.church_name LIKE ? AND a.association_name = ?
        """, (years, f"%{church}%", assoc))
    
    wpa.commit()
    c = wpa.execute("SELECT COUNT(*) FROM wpa_baptist_church_association").fetchone()[0]
    print(f"Built {c} church-association relationships")
    
    wpa.close()

def create_unified_table():
    """Create final unified table with all data."""
    wpa = sqlite3.connect(str(WPA_DB))
    wpa.row_factory = sqlite3.Row
    
    print("Creating unified table...")
    
    wpa.execute("DROP TABLE IF EXISTS wpa_baptist_unified")
    wpa.execute("""
        CREATE TABLE wpa_baptist_unified AS
        SELECT 
            c.id as church_id,
            c.church_name,
            c.dates,
            c.founding_year,
            c.closing_year,
            c.location,
            c.latitude,
            c.longitude,
            c.state,
            p.place_name,
            p.county,
            gl.grid_church_id,
            gl.match_score,
            (SELECT COUNT(*) FROM wpa_baptist_pastor_church pc WHERE pc.church_id = c.id) as pastor_count,
            (SELECT COUNT(*) FROM wpa_baptist_church_association ca WHERE ca.church_id = c.id) as association_count
        FROM wpa_baptist_churches c
        LEFT JOIN wpa_baptist_places p ON c.location = p.place_name
        LEFT JOIN wpa_baptist_grid_links gl ON c.id = gl.wpa_id
    """)
    
    wpa.commit()
    
    c = wpa.execute("SELECT COUNT(*) FROM wpa_baptist_unified").fetchone()[0]
    gps = wpa.execute("SELECT COUNT(*) FROM wpa_baptist_unified WHERE latitude IS NOT NULL").fetchone()[0]
    linked = wpa.execute("SELECT COUNT(*) FROM wpa_baptist_unified WHERE grid_church_id IS NOT NULL").fetchone()[0]
    
    print(f"Unified table: {c} churches")
    print(f"  With GPS: {gps}")
    print(f"  Linked to GRID: {linked}")
    
    wpa.close()

def import_to_grid():
    """Import unmatched Baptist churches into churches.db."""
    wpa = sqlite3.connect(str(WPA_DB))
    grid = sqlite3.connect(str(CHURCHES_DB))
    
    wpa.row_factory = sqlite3.Row
    grid.row_factory = sqlite3.Row
    
    # Get unmatched churches with GPS
    churches = wpa.execute("""
        SELECT * FROM wpa_baptist_unified 
        WHERE grid_church_id IS NULL AND latitude IS NOT NULL
    """).fetchall()
    
    print(f"Importing {len(churches)} new churches to GRID...")
    
    # Get max ID
    max_id = grid.execute("SELECT MAX(id) FROM churches").fetchone()[0]
    next_id = max_id + 1
    
    imported = 0
    for ch in churches:
        grid.execute("""
            INSERT INTO churches (id, name, address, city, state, latitude, longitude, faith, tradition, source)
            VALUES (?, ?, ?, ?, ?, ?, ?, 'Christian', 'Baptist', 'wpa_baptist_inventory')
        """, (
            next_id,
            ch['church_name'],
            ch['location'],
            ch['place_name'],
            ch['state'],
            ch['latitude'],
            ch['longitude']
        ))
        next_id += 1
        imported += 1
    
    grid.commit()
    print(f"Imported {imported} churches to GRID")
    
    wpa.close()
    grid.close()

def main():
    print("=" * 60)
    print("WPA Baptist Inventory - Complete Processing")
    print("=" * 60)
    
    print("\n1. Geocoding places...")
    geocode_via_nominatim()
    
    print("\n2. Linking to GRID...")
    link_to_grid()
    
    print("\n3. Building pastor relationships...")
    build_pastor_relationships()
    
    print("\n4. Building association relationships...")
    build_association_relationships()
    
    print("\n5. Creating unified table...")
    create_unified_table()
    
    print("\n6. Importing to GRID...")
    import_to_grid()
    
    print("\n" + "=" * 60)
    print("COMPLETE")
    print("=" * 60)

if __name__ == "__main__":
    main()
