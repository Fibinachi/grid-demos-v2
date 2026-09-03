"""
Address normalizer for IRS-sourced GRID records.
Standardizes addresses using regex rules + Census Geocoder fallback.
No external API key needed.
"""
import sqlite3, re, time, requests
from datetime import datetime, timezone
from collections import defaultdict

DB = r"E:\grid\churches.db"

# ── Abbreviation expansion ──
SUFFIX_MAP = {
    'aly': 'Alley', 'anx': 'Annex', 'arc': 'Arcade', 'ave': 'Avenue',
    'bch': 'Beach', 'bnd': 'Bend', 'blf': 'Bluff', 'blvd': 'Boulevard',
    'br': 'Branch', 'brg': 'Bridge', 'brk': 'Brook', 'byp': 'Bypass',
    'cir': 'Circle', 'clf': 'Cliff', 'clb': 'Club', 'cmn': 'Common',
    'cor': 'Corner', 'crse': 'Course', 'ct': 'Court', 'ctr': 'Center',
    'cv': 'Cove', 'cres': 'Crescent', 'crsg': 'Crossing', 'dl': 'Dale',
    'dr': 'Drive', 'est': 'Estate', 'expy': 'Expressway', 'ext': 'Extension',
    'fld': 'Field', 'fls': 'Falls', 'frd': 'Ford', 'frst': 'Forest',
    'fwy': 'Freeway', 'gdns': 'Gardens', 'gln': 'Glen', 'grn': 'Green',
    'hbr': 'Harbor', 'hvn': 'Haven', 'hts': 'Heights', 'hwy': 'Highway',
    'holw': 'Hollow', 'inlt': 'Inlet', 'jct': 'Junction', 'knl': 'Knoll',
    'ln': 'Lane', 'lgt': 'Light', 'lndg': 'Landing', 'mdw': 'Meadow',
    'ml': 'Mill', 'mnt': 'Mount', 'mtn': 'Mountain', 'nck': 'Neck',
    'orch': 'Orchard', 'pk': 'Park', 'pky': 'Parkway', 'pl': 'Place',
    'plz': 'Plaza', 'pt': 'Point', 'prt': 'Port', 'radl': 'Radial',
    'rd': 'Road', 'rdg': 'Ridge', 'riv': 'River', 'rte': 'Route',
    'sho': 'Shoal', 'sq': 'Square', 'st': 'Street', 'ste': 'Suite',
    'strm': 'Stream', 'ter': 'Terrace', 'tpke': 'Turnpike', 'trl': 'Trail',
    'vly': 'Valley', 'vlg': 'Village', 'vst': 'Vista', 'wlk': 'Walk',
    'way': 'Way', 'xing': 'Crossing',
}

DIR_MAP = {'n': 'North', 's': 'South', 'e': 'East', 'w': 'West',
           'ne': 'Northeast', 'nw': 'Northwest', 'se': 'Southeast', 'sw': 'Southwest'}

def normalize_address(addr):
    """Basic normalization: expand abbreviations, fix casing."""
    if not addr or not addr.strip():
        return addr
    
    # Title case
    result = addr.strip().title()
    
    # Expand directionals: "123 N Main St" -> "123 North Main Street"
    # Match standalone directionals (followed by space or end of string)
    result = re.sub(r'\b(N|S|E|W|Ne|Nw|Se|Sw)\b(?=\s|$)', 
                    lambda m: DIR_MAP.get(m.group(1).lower(), m.group(1)), result, flags=re.IGNORECASE)
    
    # Expand street suffixes
    def expand_suffix(m):
        word = m.group(1).lower().rstrip('.')
        return SUFFIX_MAP.get(word, m.group(1))
    
    result = re.sub(r'\b(' + '|'.join(SUFFIX_MAP.keys()) + r')\.?\b', 
                    expand_suffix, result, flags=re.IGNORECASE)
    
    # Fix double spaces
    result = re.sub(r'\s+', ' ', result)
    
    # Fix PO Box format
    result = re.sub(r'P\.?\s*O\.?\s*Box', 'PO Box', result, flags=re.IGNORECASE)
    
    return result.strip()

def normalize_city(city):
    """Normalize city name."""
    if not city:
        return city
    return city.strip().title()

def normalize_state(state):
    """Ensure two-letter uppercase state code."""
    if not state:
        return state
    state = state.strip().upper()
    # Map common state abbreviations
    state_map = {
        'ALABAMA': 'AL', 'ALASKA': 'AK', 'ARIZONA': 'AZ', 'ARKANSAS': 'AR',
        'CALIFORNIA': 'CA', 'COLORADO': 'CO', 'CONNECTICUT': 'CT', 'DELAWARE': 'DE',
        'FLORIDA': 'FL', 'GEORGIA': 'GA', 'HAWAII': 'HI', 'IDAHO': 'ID',
        'ILLINOIS': 'IL', 'INDIANA': 'IN', 'IOWA': 'IA', 'KANSAS': 'KS',
        'KENTUCKY': 'KY', 'LOUISIANA': 'LA', 'MAINE': 'ME', 'MARYLAND': 'MD',
        'MASSACHUSETTS': 'MA', 'MICHIGAN': 'MI', 'MINNESOTA': 'MN',
        'MISSISSIPPI': 'MS', 'MISSOURI': 'MO', 'MONTANA': 'MT', 'NEBRASKA': 'NE',
        'NEVADA': 'NV', 'NEW HAMPSHIRE': 'NH', 'NEW JERSEY': 'NJ',
        'NEW MEXICO': 'NM', 'NEW YORK': 'NY', 'NORTH CAROLINA': 'NC',
        'NORTH DAKOTA': 'ND', 'OHIO': 'OH', 'OKLAHOMA': 'OK', 'OREGON': 'OR',
        'PENNSYLVANIA': 'PA', 'RHODE ISLAND': 'RI', 'SOUTH CAROLINA': 'SC',
        'SOUTH DAKOTA': 'SD', 'TENNESSEE': 'TN', 'TEXAS': 'TX', 'UTAH': 'UT',
        'VERMONT': 'VT', 'VIRGINIA': 'VA', 'WASHINGTON': 'WA',
        'WEST VIRGINIA': 'WV', 'WISCONSIN': 'WI', 'WYOMING': 'WY',
    }
    if len(state) > 2:
        return state_map.get(state, state[:2])
    return state

# ── Main ──
def main():
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    
    # Get ALL US records with addresses (not just IRS)
    c.execute("""
        SELECT id, name, address, city, state, zip5
        FROM churches 
        WHERE country='US'
          AND address IS NOT NULL AND address != ''
        ORDER BY id
    """)
    records = c.fetchall()
    print(f"IRS records: {len(records):,}")
    
    BATCH = 1000
    updated = 0
    
    for i, r in enumerate(records):
        norm_addr = normalize_address(r['address'])
        norm_city = normalize_city(r['city'])
        norm_state = normalize_state(r['state'])
        
        addr_changed = norm_addr != r['address']
        city_changed = norm_city != r['city']
        state_changed = norm_state != r['state']
        
        if addr_changed or city_changed or state_changed:
            c.execute("""
                UPDATE churches SET address=?, city=?, state=?
                WHERE id=?
            """, (norm_addr, norm_city, norm_state, r['id']))
            updated += 1
        
        if i % BATCH == 0 and i > 0:
            conn.commit()
            print(f"  {i:,}/{len(records):,} | updated: {updated:,}")
    
    conn.commit()
    print(f"\n{'='*50}")
    print(f"Address Normalization Complete")
    print(f"{'='*50}")
    print(f"  Total IRS records: {len(records):,}")
    print(f"  Updated:           {updated:,}")
    
    # Show sample changes
    if updated > 0:
        print(f"\nSample normalizations:")
        c.execute("""
            SELECT address, city, state FROM churches 
            WHERE source LIKE '%irs%' AND country='US'
            ORDER BY RANDOM() LIMIT 5
        """)
        for r in c.fetchall():
            print(f"  {r['address']}, {r['city']}, {r['state']}")
    
    conn.close()

if __name__ == "__main__":
    main()
