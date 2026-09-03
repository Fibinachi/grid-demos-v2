#!/usr/bin/env python3
"""
Re-parse 302 unmatched Baptist churches with corrupted city names.
Uses rule-based cleanup + DeepSeek for ambiguous cases.
"""
import sqlite3, re, os, json, time, requests
from pathlib import Path

WPA_DB = Path("E:/grid/wpa.db")
DEEPSEEK_KEY = os.environ.get("DEEPSEEK_API_KEY", "")

def rule_based_cleanup(city):
    """Clean obvious OCR artifacts from city names."""
    if not city:
        return None
    
    original = city
    
    # Remove trailing dots, spaces, and page numbers
    city = re.sub(r'\s*\.+\s*\d+\s*$', '', city)  # "Providence .... . 80" -> "Providence"
    city = re.sub(r'\s*\.+\s*$', '', city)          # "Crompton ." -> "Crompton"
    city = re.sub(r'\s+\d+\s*$', '', city)          # "Burrillville 35" -> "Burrillville"
    city = re.sub(r'[^\w\s\-\.]', '', city)         # Remove special chars like < > �
    city = re.sub(r'\s+', ' ', city).strip()        # Normalize whitespace
    
    # Common OCR corrections
    city = re.sub(r'Frovidence', 'Providence', city, flags=re.IGNORECASE)
    city = re.sub(r'Glocester', 'Gloucester', city, flags=re.IGNORECASE)
    city = re.sub(r'Pawtucket\.', 'Pawtucket', city)
    
    return city if city else None

def deepseek_cleanup(name, state, corrupted_city):
    """Use DeepSeek to extract clean city name from corrupted data."""
    prompt = f"""Extract the clean city/town name from this corrupted WPA Baptist church record.

Church: {name}
State: {state}
Corrupted location: {corrupted_city}

Return ONLY the clean city name, no explanation. If you cannot determine the city, return "UNKNOWN".

Examples:
- "Providence .... . 80" → "Providence"
- "Burrillville . . 35" → "Burrillville"
- "North Kingstown �������<" → "North Kingstown"
- "South" → "UNKNOWN" (too ambiguous)
- "" → "UNKNOWN"

Clean city name:"""

    try:
        r = requests.post(
            'https://api.deepseek.com/v1/chat/completions',
            json={'model': 'deepseek-chat', 'messages': [
                {'role': 'user', 'content': prompt}
            ], 'temperature': 0.0, 'max_tokens': 50},
            headers={'Authorization': f'Bearer {DEEPSEEK_KEY}', 'Content-Type': 'application/json'},
            timeout=30)
        if r.status_code == 200:
            result = r.json()['choices'][0]['message']['content'].strip()
            result = result.strip('"').strip("'")
            return result if result != "UNKNOWN" else None
    except Exception as e:
        print(f"  DeepSeek error: {e}")
    return None

def main():
    wpa = sqlite3.connect(str(WPA_DB))
    wpa.row_factory = sqlite3.Row
    
    # Get unmatched churches
    unmatched = wpa.execute("""
        SELECT c.id, c.church_name, c.state, c.location, c.city_clean
        FROM wpa_baptist_churches c
        LEFT JOIN wpa_baptist_grid_links g ON c.id = g.wpa_id
        WHERE g.wpa_id IS NULL
    """).fetchall()
    
    print(f"Unmatched churches: {len(unmatched)}")
    
    updated = 0
    deepseek_count = 0
    
    for ch in unmatched:
        church_id = ch['id']
        name = ch['church_name']
        state = ch['state']
        location = ch['location']
        city_clean = ch['city_clean']
        
        # Try rule-based cleanup first
        new_city = rule_based_cleanup(city_clean)
        
        # If rule-based failed and we have a corrupted city, try DeepSeek
        if not new_city and city_clean:
            new_city = deepseek_cleanup(name, state, city_clean)
            deepseek_count += 1
            time.sleep(0.2)  # Rate limit
        
        # If still no city but we have location, try cleaning that
        if not new_city and location:
            new_city = rule_based_cleanup(location)
        
        if new_city and new_city != city_clean:
            wpa.execute("UPDATE wpa_baptist_churches SET city_clean = ? WHERE id = ?", (new_city, church_id))
            updated += 1
            print(f"  [{church_id}] {name[:40]:40} | {city_clean[:30]:30} -> {new_city[:30]}")
    
    wpa.commit()
    print(f"\nUpdated {updated} city_clean values ({deepseek_count} via DeepSeek)")
    
    # Now re-run linking
    print("\nRe-running grid links...")
    wpa.execute("DELETE FROM wpa_baptist_grid_links")
    wpa.commit()
    
    # Re-link using the same logic as fast_baptist_final.py
    grid = sqlite3.connect(str(Path("E:/grid/churches.db")))
    grid.row_factory = sqlite3.Row
    
    churches = wpa.execute("SELECT id, church_name, location, state, city_clean FROM wpa_baptist_churches").fetchall()
    grid_churches = grid.execute("SELECT id, name, city, state FROM churches WHERE state IS NOT NULL").fetchall()
    
    state_index = {}
    for c in grid_churches:
        state = c['state'].upper()
        state_index.setdefault(state, []).append(c)
    
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
            
            name_words = set(name.split())
            grid_words = set(grid_name.split())
            overlap = len(name_words & grid_words)
            score = overlap
            
            # Also check city_clean
            city_clean = (ch['city_clean'] or '').lower()
            if city_clean and grid_city and (city_clean in grid_city or grid_city in city_clean):
                score += 2
            
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
    print(f"Re-linked {matches} churches to GRID")
    
    wpa.close()
    grid.close()

if __name__ == "__main__":
    main()
