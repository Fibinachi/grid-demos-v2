#!/usr/bin/env python3
"""Import unmatched Baptist churches into GRID."""
import sqlite3
from pathlib import Path

WPA_DB = Path("E:/grid/wpa.db")
CHURCHES_DB = Path("E:/grid/churches.db")

def import_unmatched():
    wpa = sqlite3.connect(str(WPA_DB))
    grid = sqlite3.connect(str(CHURCHES_DB))
    
    wpa.row_factory = sqlite3.Row
    
    churches = wpa.execute("""
        SELECT c.*, p.latitude as place_lat, p.longitude as place_lon 
        FROM wpa_baptist_churches c
        LEFT JOIN wpa_baptist_places p ON c.location = p.place_name
        WHERE c.id NOT IN (SELECT wpa_id FROM wpa_baptist_grid_links)
    """).fetchall()
    
    print(f"Unmatched churches: {len(churches)}")
    
    max_id = grid.execute("SELECT MAX(id) FROM churches").fetchone()[0]
    next_id = max_id + 1 if max_id else 5000000
    
    imported = 0
    for ch in churches:
        name = ch['church_name'] or ''
        location = ch['location'] or ''
        state = ch['state'] or ''
        
        if not state or not location:
            continue
        
        lat = ch['place_lat']
        lon = ch['place_lon']
        
        # Try city lookup if no GPS
        if not lat:
            city_match = grid.execute("SELECT AVG(latitude), AVG(longitude) FROM churches WHERE city = ? AND state = ?", (location, state)).fetchone()
            if city_match and city_match[0]:
                lat, lon = city_match[0], city_match[1]
        
        # Skip if still no location
        if not lat:
            continue
        
        grid.execute("""
            INSERT INTO churches (
                id, name, address, city, state, latitude, longitude,
                faith, tradition, source, landmark_type
            ) VALUES (?,?,?,?,?,?,?,'Christian','Baptist','wpa_baptist_inventory','church')
        """, (next_id, name[:200], location[:200], location[:100], state, lat, lon))
        next_id += 1
        imported += 1
    
    grid.commit()
    print(f"Imported {imported} churches to GRID")
    
    wpa.close()
    grid.close()

if __name__ == "__main__":
    import_unmatched()