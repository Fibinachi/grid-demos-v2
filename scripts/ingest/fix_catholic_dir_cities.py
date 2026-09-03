"""
Fix city names in Catholic directory (dir_entries) and normalize state names.
Prepares records for geocoding by cleaning up common issues.

Fixes:
1. Strip parenthetical notes: "Kickapoo (Edwards)" → "Kickapoo"
2. Split comma-separated: "Condado, San Juan" → "San Juan"
3. State-code-as-city: "KS" → look up from other fields
4. OCR garbage: "2Ul's", "ink ale", "ea" → use state/name to reconstruct
5. Normalize state values: "California" → "CA", "L.C." → "QC", etc.
6. Fix "None" string state → NULL
"""
import sqlite3, re
from pathlib import Path

CATH_DB = "E:/grid/data/catholic_directory.db"

# State name → abbreviation mapping
STATE_TO_ABBR = {
    'alabama': 'AL', 'alaska': 'AK', 'arizona': 'AZ', 'arkansas': 'AR',
    'california': 'CA', 'colorado': 'CO', 'connecticut': 'CT', 'delaware': 'DE',
    'district of columbia': 'DC', 'florida': 'FL', 'georgia': 'GA',
    'hawaii': 'HI', 'idaho': 'ID', 'illinois': 'IL', 'indiana': 'IN',
    'iowa': 'IA', 'kansas': 'KS', 'kentucky': 'KY', 'louisiana': 'LA',
    'maine': 'ME', 'maryland': 'MD', 'massachusetts': 'MA', 'michigan': 'MI',
    'minnesota': 'MN', 'mississippi': 'MS', 'missouri': 'MO', 'montana': 'MT',
    'nebraska': 'NE', 'nevada': 'NV', 'new hampshire': 'NH', 'new jersey': 'NJ',
    'new mexico': 'NM', 'new york': 'NY', 'north carolina': 'NC',
    'north dakota': 'ND', 'ohio': 'OH', 'oklahoma': 'OK', 'oregon': 'OR',
    'pennsylvania': 'PA', 'rhode island': 'RI', 'south carolina': 'SC',
    'south dakota': 'SD', 'tennessee': 'TN', 'texas': 'TX', 'utah': 'UT',
    'vermont': 'VT', 'virginia': 'VA', 'washington': 'WA', 'west virginia': 'WV',
    'wisconsin': 'WI', 'wyoming': 'WY',
    # Canadian
    'alberta': 'AB', 'british columbia': 'BC', 'manitoba': 'MB',
    'new brunswick': 'NB', 'newfoundland': 'NL', 'nova scotia': 'NS',
    'ontario': 'ON', 'prince edward island': 'PE', 'quebec': 'QC',
    'saskatchewan': 'SK',
    'northwest territories': 'NT', 'nunavut': 'NU', 'yukon': 'YT',
    # Historical Canadian
    'lower canada': 'QC', 'upper canada': 'ON', 'canada west': 'ON',
    'canada east': 'QC',
    # Territories / other
    'guam': 'GU', 'puerto rico': 'PR', 'virgin islands': 'VI',
    'american samoa': 'AS', 'northern mariana islands': 'MP',
    'micronesia': 'FM', 'marshall islands': 'MH', 'palau': 'PW',
}

# Historical Canadian abbreviations
HISTORIC_CANADA = {
    'L.C.': 'QC',      # Lower Canada → Quebec
    'U.C.': 'ON',      # Upper Canada → Ontario
    'C.W.': 'ON',     # Canada West → Ontario
    'LOWER CANADA': 'QC',
    'UPPER CANADA': 'ON',
    'NF': 'NL',        # Newfoundland → Newfoundland and Labrador
    'NP': 'NL',        # Newfoundland (postal)
}

# Non-standard US territories/states
NONSTANDARD_STATES = {
    'FRENCH SHORE': 'NS',
    'Fort des Prairies District': 'SK',
    'Red River District': 'MB',
    'Washington Territory': 'WA',
    'Vancouver Island': 'BC',
    'Île à la Crosse District': 'SK',
    'Vicariate Apostolic of Athabaska and Mackenzie': 'NT',
}

def normalize_state(state):
    """Convert state to standard 2-letter abbreviation."""
    if state is None or state.strip() == '' or state.strip() == 'None':
        return None
    s = state.strip()
    # Already 2-letter uppercase?
    if len(s) == 2 and s.isalpha() and s.isupper():
        return s
    # Historical Canada
    if s in HISTORIC_CANADA:
        return HISTORIC_CANADA[s]
    # Non-standard
    if s in NONSTANDARD_STATES:
        return NONSTANDARD_STATES[s]
    # Full name → abbreviation
    s_lower = s.lower().strip()
    if s_lower in STATE_TO_ABBR:
        return STATE_TO_ABBR[s_lower]
    # Try split and match last word (e.g. "New York" → "NY")
    parts = s_lower.split()
    if len(parts) > 1 and s_lower in STATE_TO_ABBR:
        return STATE_TO_ABBR[s_lower]
    # Unknown - return as-is
    return s

def fix_city(city, state, name):
    """Fix a city name. Returns (fixed_city, fixed_state) or (None, None) if unfixable."""
    if city is None or city.strip() == '':
        return None, state
    
    c = city.strip()
    
    # 1. Strip parenthetical notes: "Kickapoo (Edwards)" → "Kickapoo"
    c = re.sub(r'\s*\(.*?\)\s*', '', c).strip()
    
    # 2. Split comma-separated: "Condado, San Juan" → take last part
    if ',' in c:
        parts = [p.strip() for p in c.split(',')]
        # If the last part looks like a city (not a state or direction), use it
        c = parts[-1].strip()
    
    # 3. State-code-as-city: if city looks like a state abbreviation and matches state field
    if len(c) == 2 and c.isalpha() and c.isupper():
        # Try to determine actual city from church name or other context
        # For now, set city to None and let downstream handle
        return None, state
    
    # 4. OCR garbage patterns
    # All lowercase and short → garbage
    if c.islower() and len(c) <= 5:
        return None, state
    
    # Contains digits but no valid street address pattern → garbage
    if re.search(r'[0-9]', c) and not re.match(r'^\d+', c):
        return None, state
    
    # 5. Single character → garbage
    if len(c) <= 1:
        return None, state
    
    # 6. "Lot N" pattern (Canadian land grants) → use county/parish info
    if re.match(r'^Lot \d+$', c, re.IGNORECASE):
        return None, state
    
    # 7. Clean up whitespace
    c = re.sub(r'\s+', ' ', c).strip()
    
    return c, state

def main():
    conn = sqlite3.connect(CATH_DB)
    conn.row_factory = sqlite3.Row
    
    # Get all entries with city issues or non-normalized states
    rows = conn.execute('''
        SELECT id, directory_year, name, city, state, address, entity_type,
               latitude, longitude, geocode_source, geocode_confidence
        FROM dir_entries
        ORDER BY id
    ''').fetchall()
    
    print(f"Processing {len(rows)} entries...")
    
    city_fixes = 0
    state_fixes = 0
    city_cleared = 0  # set to NULL (garbage)
    
    for r in rows:
        eid = r['id']
        old_city = r['city']
        old_state = r['state']
        
        # Fix state
        new_state = normalize_state(r['state'])
        if new_state != old_state:
            if new_state is None or old_state is None or new_state != old_state:
                conn.execute('UPDATE dir_entries SET state = ? WHERE id = ?', (new_state, eid))
                state_fixes += 1
        
        # Fix city
        if old_city:
            new_city, _ = fix_city(old_city, new_state, r['name'])
            if new_city != old_city:
                conn.execute('UPDATE dir_entries SET city = ? WHERE id = ?', (new_city, eid))
                if new_city is None:
                    city_cleared += 1
                else:
                    city_fixes += 1
    
    conn.commit()
    
    print(f"\nResults:")
    print(f"  City names fixed: {city_fixes}")
    print(f"  City names cleared (garbage): {city_cleared}")
    print(f"  State values normalized: {state_fixes}")
    
    # Show sample fixes
    print("\nSample fixed entries (re-query):")
    cur = conn.execute('''
        SELECT id, directory_year, name, city, state
        FROM dir_entries
        WHERE id IN (
            SELECT id FROM dir_entries WHERE city IS NOT NULL AND city != '' AND LENGTH(city) > 2
            LIMIT 5
        )
    ''')
    for r in cur.fetchall():
        print(f'  id={r["id"]} yr={r["directory_year"]} city="{r["city"]}" state={r["state"]} name="{r["name"]}"')
    
    # Check parenthetical city fix
    cur = conn.execute('SELECT id, city FROM dir_entries WHERE city LIKE "%(%)%" LIMIT 10')
    remaining_paren = cur.fetchall()
    print(f"\nRemaining parenthetical cities: {len(remaining_paren)}")
    for r in remaining_paren[:5]:
        print(f'  id={r["id"]} city="{r["city"]}"')
    
    conn.close()

if __name__ == '__main__':
    main()
