#!/usr/bin/env python3
"""Geocode Baptist places via GRID city averages."""
import sqlite3, json
from pathlib import Path

DB_PATH = Path("E:/grid/wpa.db")
CHURCHES_DB = Path("E:/grid/churches.db")

def geocode_via_grid():
    wpa = sqlite3.connect(str(DB_PATH))
    grid = sqlite3.connect(str(CHURCHES_DB))
    
    cities = grid.execute("""
        SELECT city, state, AVG(latitude) as lat, AVG(longitude) as lon, COUNT(*) as cnt
        FROM churches WHERE latitude IS NOT NULL AND city IS NOT NULL
        GROUP BY city, state ORDER BY cnt DESC
    """).fetchall()
    
    city_coords = {}
    for city, state, lat, lon, cnt in cities:
        if not state or not city:
            continue
        key = f"{city.lower().strip()}, {state.upper().strip()}"
        city_coords[key] = (lat, lon, cnt)
    
    print(f"Loaded {len(city_coords)} city coordinates from GRID")
    
    wpa.execute("ALTER TABLE wpa_baptist_places ADD COLUMN latitude REAL")
    wpa.execute("ALTER TABLE wpa_baptist_places ADD COLUMN longitude REAL")
    
    places = wpa.execute("SELECT id, place_name, state, city FROM wpa_baptist_places").fetchall()
    
    matched = 0
    for pid, place_name, state, city in places:
        if not state or not city:
            continue
        key = f"{city.lower().strip()}, {state.upper().strip()}"
        if key in city_coords:
            lat, lon, cnt = city_coords[key]
            wpa.execute("UPDATE wpa_baptist_places SET latitude=?, longitude=? WHERE id=?", (lat, lon, pid))
            matched += 1
    
    wpa.commit()
    print(f"Matched {matched} places via city lookup")
    
    wpa.execute("ALTER TABLE wpa_baptist_churches ADD COLUMN latitude REAL")
    wpa.execute("ALTER TABLE wpa_baptist_churches ADD COLUMN longitude REAL")
    
    wpa.execute("""
        UPDATE wpa_baptist_churches 
        SET latitude = (SELECT latitude FROM wpa_baptist_places WHERE place_name = wpa_baptist_churches.location),
            longitude = (SELECT longitude FROM wpa_baptist_places WHERE place_name = wpa_baptist_churches.location)
    """)
    
    wpa.commit()
    
    c = wpa.execute("SELECT COUNT(*) FROM wpa_baptist_churches WHERE latitude IS NOT NULL")
    print(f"Churches with GPS: {c.fetchone()[0]}")
    
    wpa.close()
    grid.close()

if __name__ == "__main__":
    geocode_via_grid()