#!/usr/bin/env python3
"""
Filter out seminaries/educational institutions from theology master list.
Keep only actual grant-making foundations.
"""
import csv, os, re

base = os.path.dirname(os.path.abspath(__file__))

# Keywords that identify educational institutions (not grant-makers)
EDUCATION_KEYWORDS = [
    'seminary', 'divinity school', 'theological seminary', 'bible college',
    'school of theology', 'school of divinity', 'graduate school',
    'college', 'university', 'institute of ', 'academy',
    'theology academy', 'theology school',
]

# Keywords that identify actual grant-makers  
FOUNDATION_KEYWORDS = [
    'foundation', 'fund', 'trust', 'endowment', 'charitable',
    'philanthropic', 'foundation for', 'foundation inc',
    'family foundation', 'foundation tr',
]

# Specific names known to be grant-makers (not schools)
KNOWN_GRANTMAKERS = [
    'lilly endowment', 'templeton foundation', 'ford foundation',
    'mcconnell foundation', 'anglican foundation of canada',
    'united church of canada foundation', 'laidlaw foundation',
    'atkinson foundation', 'ontario trillium foundation',
    'catherine donnelly foundation', 'vancouver foundation',
    'calgary foundation', 'edmonton community foundation',
    'winnipeg foundation', 'max bell foundation',
    'gordon foundation', 'canadian bible society',
]

# Names known to be schools (not grant-makers)
KNOWN_SCHOOLS = [
    'reformed theological seminary', 'covenant theological seminary',
    'calvin theological seminary', 'asbury theological seminary',
    'fuller theological seminary', 'dallas theological seminary',
    'union theological seminary', 'eden theological seminary',
    'hood theological seminary', 'auburn theological seminary',
    'winebrenner theological seminary', 'bangor theological seminary',
    'gettysburg seminary', 'trinity evangelical divinity school',
    'berkeley divinity school', 'episcopal divinity school',
    'colgate rochester divinity school', 'brite divinity school',
    'charlotte divinity school', 'sophia divinity school',
    'all paths divinity school', 'theocracy school of divinity',
    'church divinity school of the pacific',
    'grace school of theology', 'faith school of theology',
    'new york theological education center',
    'international theological seminary',
    'westminster theological seminary',
    'knox theological seminary', 'heidelberg theological seminary',
    'northwind theological seminary', 'urbana theological seminary',
    'indianapolis theological seminary',
    'ecumenical theological seminary',
    'birmingham theological seminary',
    'pacific theological seminary', 'truth theological seminary',
    'chafer theological seminary',
    # Seminary FOUNDATIONS that exist solely to fund their own institution
    'puritan reformed theological seminary foundation',
    'ashland theological seminary foundation',
    'covenant theological seminary foundation',
    'dallas seminary foundation',
    'luther seminary foundation',
    'new orleans baptist seminary foundation',
    'wartburg seminary foundation',
    'stegall seminary scholarshipendowment foundation',
    'michigan lutheran seminary foundation',
    'gets theological seminary foundation',
    'southwestern seminary foundation',
    'shepherds seminary foundation',
    'united lutheran seminary endowment foundation',
    'luther rice seminary foundation',
    'apostolic church int seminary foundation',
    'st joseph seminary of hanoi foundation',
    'baptist seminary of madagascar foundation',
    'cedar valley seminary foundation',
    'logos evangelical seminary foundation',
    'stevens seminary foundation',
    'omaha presbyterian seminary foundation',
    'romanian baptist seminary foundation',
    'dallas seminary foundation vision fund',
    'new york evangelical seminary fund',
]

# Load master list
master_path = os.path.join(base, 'theology_master_list.csv')
with open(master_path, 'r') as f:
    rows = list(csv.DictReader(f))

print(f"Loaded {len(rows)} entries from master list")
print(f"Before: {len([r for r in rows if r['PRIORITY']=='HIGH'])} HIGH, {len([r for r in rows if r['PRIORITY']=='MEDIUM'])} MEDIUM")

# Filter
kept = []
removed_schools = 0
removed_generic = 0

for r in rows:
    name = r['NAME'].lower().strip()
    tier = r.get('TIER', '')
    
    # Check if it's a known school
    is_school = False
    for school in KNOWN_SCHOOLS:
        if school == name or name.startswith(school) or school.startswith(name):
            is_school = True
            break
    
    if not is_school:
        # Check name for education keywords (only if not a foundation)
        has_foundation_kw = any(kw in name for kw in FOUNDATION_KEYWORDS)
        has_education_kw = any(kw in name for kw in EDUCATION_KEYWORDS)
        
        if has_education_kw and not has_foundation_kw:
            is_school = True
    
    if is_school:
        removed_schools += 1
        continue
    
    kept.append(r)

print(f"After: {len(kept)} entries")
print(f"Removed schools: {removed_schools}")

# Save filtered list
filtered_path = os.path.join(base, 'theology_foundations_only.csv')
with open(filtered_path, 'w', newline='', encoding='utf-8') as f:
    w = csv.DictWriter(f, fieldnames=rows[0].keys() if rows else [])
    w.writeheader()
    w.writerows(kept)

# Build ready-to-send from filtered
high_ready = [r for r in kept if r['PRIORITY'] == 'HIGH' and r['HAS_EMAIL'] == 'YES']
high_need = [r for r in kept if r['PRIORITY'] == 'HIGH' and r['HAS_EMAIL'] == 'NEED SCRAPING']

send_path = os.path.join(base, 'theology_foundations_ready.csv')
with open(send_path, 'w', newline='', encoding='utf-8') as f:
    w = csv.DictWriter(f, fieldnames=rows[0].keys() if rows else [])
    w.writeheader()
    w.writerows(high_ready)

print(f"\nReady to send (HIGH, have email): {len(high_ready)} -> {send_path}")
print(f"Still need email (HIGH): {len(high_need)}")

# Print top 20
print(f"\n=== TOP FOUNDATIONS (filtered, no seminaries) ===")
for r in kept[:25]:
    email = '✓' if r['HAS_EMAIL'] == 'YES' else '✗'
    print(f"  [{r['PRIORITY']:6s}] [{r['THEOLOGY_SCORE']:>3s}] {email} {r['NAME'][:55]} ({r['CITY']}, {r['STATE']})")
