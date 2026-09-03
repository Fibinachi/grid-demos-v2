#!/usr/bin/env python3
"""Quick fix: add missing area codes and geocode LOC churches."""
import json, sys, re
from pathlib import Path

# ── Add missing area codes ──
MORE_AREA_CODES = {
    # Alabama
    ('Alabama', 'Bessemer'): '205',
    ('Alabama', 'Gardendale'): '205',
    ('Alabama', 'New Hope'): '256',
    ('Alabama', 'Sylacauga'): '256',
    ('Alabama', 'Talladega'): '256',
    ('Alabama', 'Russellville'): '256',
    ('Alabama', 'Flat Rock'): '256',
    # Alaska  
    ('Alaska', 'Annette Island'): '907',
    # Arizona
    ('Arizona', 'Benson'): '520',
    ('Arizona', 'Bisbee'): '520',
    ('Arizona', 'Douglas'): '520',
    ('Arizona', 'Flagstaff'): '928',
    ('Arizona', 'Hayden'): '520',
    ('Arizona', 'Nogales'): '520',
    ('Arizona', 'Yuma'): '928',
    ('Arizona', 'Casa Grande'): '520',
    ('Arizona', 'Coolidge'): '520',
    ('Arizona', 'Globe'): '928',
    # Arkansas
    ('Arkansas', 'Camden'): '870',
    ('Arkansas', 'Clarksville'): '479',
    ('Arkansas', 'El Dorado'): '870',
    ('Arkansas', 'Fayetteville'): '479',
    ('Arkansas', 'Fort Smith'): '479',
    ('Arkansas', 'Hope'): '870',
    ('Arkansas', 'Hot Springs'): '501',
    ('Arkansas', 'Jonesboro'): '870',
    ('Arkansas', 'Magnolia'): '870',
    ('Arkansas', 'Pine Bluff'): '870',
    ('Arkansas', 'Russellville'): '479',
    ('Arkansas', 'Searcy'): '501',
    ('Arkansas', 'Texarkana'): '870',
}

_PHONE_KEYPAD = str.maketrans('ABCDEFGHIJKLMNOPQRSTUVWXYZ',
                               '22233344455566677778889999')

def fix_area_code(entry):
    state = entry.get('state', '')
    city = entry.get('city', '')
    phone = entry.get('phone', '')
    
    if entry.get('area_code'):
        return  # Already has one
    
    if not phone:
        return
    
    # Try exact match
    key = (state, city)
    if key in MORE_AREA_CODES:
        ac = MORE_AREA_CODES[key]
    else:
        # Try first word match
        first = city.split()[0] if city else ''
        for (s, c), a in MORE_AREA_CODES.items():
            if s == state and c.startswith(first):
                ac = a
                break
        else:
            return  # Can't find
    
    # Re-modernize with area code
    m = re.match(r'([A-Z]{2,8})\s+(\d)[-–](\d{4})', phone, re.IGNORECASE)
    if m:
        exchange = m.group(1).upper().translate(_PHONE_KEYPAD)
        digit = m.group(2)
        number = m.group(3)
        entry['phone_modern'] = f'({ac}) {exchange}{digit}-{number}'
        entry['area_code'] = ac
        entry['phone_is_full'] = True
        return
    
    m = re.match(r'(\d{1,2})[-–](\d{4})$', phone)
    if m:
        entry['phone_modern'] = f'({ac}) {m.group(1)}-{m.group(2)}'
        entry['area_code'] = ac

# ── Main ──
in_file = Path('E:/grid/data/loc_phone_dirs/results/loc_churches_matched_20260709_094416.json')
out_file = Path('E:/grid/data/loc_phone_dirs/results/loc_churches_fixed.json')

data = json.loads(in_file.read_text(encoding='utf-8'))

filled = 0
for entry in data:
    if entry.get('phone') and not entry.get('area_code'):
        fix_area_code(entry)
        if entry.get('area_code'):
            filled += 1

print(f'Area codes filled: {filled}')
print(f'Total with area code now: {sum(1 for c in data if c.get("area_code"))}')

# Save
out_file.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding='utf-8')
print(f'Saved: {out_file}')

# ── Geocode summary ──
geocodable = [c for c in data if c.get('address') and c.get('city') and c.get('state')]
print(f'\nGeocodable entries: {len(geocodable)}')

# Show sample
for c in geocodable[:5]:
    addr = f"{c['address']}, {c['city']}, {c['state']}"
    print(f'  {c["name"][:50]} | {addr}')
