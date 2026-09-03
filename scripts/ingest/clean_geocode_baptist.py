#!/usr/bin/env python3
"""Clean OCR artifacts from Baptist locations and re-geocode."""
import sqlite3
from pathlib import Path

DB_PATH = Path("E:/grid/wpa.db")
CHURCHES_DB = Path("E:/grid/churches.db")

def clean_and_geocode():
    wpa = sqlite3.connect(str(DB_PATH))
    grid = sqlite3.connect(str(CHURCHES_DB))
    
    # Clean locations
    places = wpa.execute("SELECT id, city FROM wpa_baptist_places WHERE city IS NOT NULL").fetchall()
    
    cleaned = 0
    for pid, city in places:
        if not city:
            continue
        # Remove dots, >, *, etc
        new_city = city.strip().replace('.', '').replace('>', '').replace('*', '').replace('  ', ' ').strip()
        if new_city != city:
            wpa.execute("UPDATE wpa_baptist_places SET city = ? WHERE id = ?", (new_city, pid))
            cleaned += 1
    
    wpa.commit()
    print(f"Cleaned {cleaned} locations")
    
    # Reload GRID cities
    cities = grid.execute("SELECT city, state, AVG(latitude) as lat, AVG(longitude) as lon FROM churches WHERE latitude IS NOT NULL AND city IS NOT NULL GROUP BY city, state").fetchall()
    
    city_coords = {}
    for city, state, lat, lon in cities:
        if not state or not city:
            continue
        key = f"{city.strip().lower()}, {state.strip().upper()}"
        city_coords[key] = (lat, lon)
    
    print(f"GRID cities: {len(city_coords)}")
    
    # Re-match
    places = wpa.execute("SELECT id, city, state FROM wpa_baptist_places WHERE latitude IS NULL").fetchall()
    
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
    
    # Re-update churches
    wpa.execute("UPDATE wpa_baptist_churches SET latitude = (SELECT latitude FROM wpa_baptist_places WHERE city = wpa_baptist_churches.city_clean), longitude = (SELECT longitude FROM wpa_baptist_places WHERE city = wpa_baptist_churches.city_clean)")
    wpa.commit()
    
    c = wpa.execute("SELECT COUNT(*) FROM wpa_baptist_places WHERE latitude IS NOT NULL")
    print(f"Places with GPS: {c.fetchone()[0]}")
    
    c = wpa.execute("SELECT COUNT(*) FROM wpa_baptist_churches WHERE latitude IS NOT NULL")
    print(f"Churches with GPS: {c.fetchone()[0]}")
    
    wpa.close()
    grid.close()

if __name__ == "__main__":
    clean_and_geocode()