#!/usr/bin/env python3
"""
Aggressive filtering of the theology master list.
Removes anything that's clearly NOT a grant-making foundation.

KEEP only:
- Foundations (family, private, community, corporate)
- Charitable trusts and endowments
- Grant-making organizations
- Philanthropic organizations

REMOVE:
- Seminaries, divinity schools, bible colleges (fund own students)
- Churches, congregations, parishes
- Museums, arts centers, libraries
- Hospitals, clinics, medical research
- Environmental/conservation groups
- Animal welfare organizations
- Sports/recreation organizations
- Individual scholarships for specific schools
- Government entities
- Civic/social clubs
- Organizations with no plausible theology connection
"""
import csv, os, re

base = os.path.dirname(os.path.abspath(__file__))

# === REMOVAL RULES ===

# NTEE codes that are clearly not theology-funding
NTEE_REMOVE = {
    # Arts & Culture
    'A': 'Arts/culture',
    'A20': 'Arts', 'A30': 'Media', 'A40': 'Museums', 'A50': 'Libraries',
    'A60': 'Performing arts', 'A70': 'Museums', 'A80': 'Historical',
    'A90': 'Arts services',
    # Education - schools (not grant-makers)
    'B': 'Education - skip schools',
    'B40': 'Primary/Secondary ed',
    'B41': 'Early childhood', 'B42': 'Elementary', 'B43': 'Secondary',
    # Environmental
    'C': 'Environmental',
    'C30': 'Pollution', 'C32': 'Waste', 'C34': 'Land conservation',
    'C36': 'Forests', 'C38': 'Watershed',
    # Animals
    'D': 'Animal related',
    'D20': 'Animal protection', 'D30': 'Wildlife', 'D31': 'Endangered',
    'D32': 'Bird', 'D33': 'Zoo', 'D34': 'Veterinary', 'D40': 'Animal services',
    # Health
    'E': 'Health',
    'E20': 'Hospitals', 'E21': 'Community health', 'E22': 'Hospital',
    'E24': 'Hospital', 'E30': 'Health treatment', 'E31': 'Clinics',
    'E40': 'Reproductive health', 'E50': 'Rehab', 'E60': 'Health support',
    'E70': 'Mental health', 'E80': 'Research', 'E86': 'Alzheimer',
    'E90': 'Nursing', 'E91': 'Nursing home', 'E92': 'Home health',
    'E99': 'Health NEC',
    # Mental Health
    'F': 'Mental health',
    # Diseases
    'G': 'Disease research',
    'G20': 'Cancer', 'G30': 'Heart', 'G40': 'Diabetes', 'G50': 'Kidney',
    'G60': 'Respiratory', 'G80': 'Alzheimer', 'G90': 'Medical research',
    # Medical Research
    'H': 'Medical research',
    # Crime/Legal
    'I': 'Crime/legal',
    'I20': 'Crime prevention', 'I21': 'Delinquency', 'I23': 'Corrections',
    'I30': 'Courts', 'I31': 'Legal services', 'I40': 'Rehabilitation',
    'I43': 'Sex offenses', 'I50': 'Substance abuse', 'I60': 'Victim services',
    'I70': 'Hate crimes', 'I71': 'Human trafficking', 'I72': 'Racial justice',
    'I73': 'Wrongful conviction', 'I80': 'Law enforcement',
    # Employment
    'J': 'Employment',
    # Food/Agriculture
    'K': 'Food/agriculture',
    'K20': 'Agriculture', 'K25': 'Farmland', 'K30': 'Food programs',
    'K31': 'Food pantries', 'K34': 'Aid distribution', 'K35': 'Food banks',
    'K36': 'Meals on wheels', 'K40': 'Nutrition',
    # Housing/Shelter
    'L': 'Housing/shelter',
    'L20': 'Housing development', 'L21': 'Low-income housing',
    'L22': 'Senior housing', 'L24': 'Homeless shelters', 'L25': 'Temp housing',
    'L30': 'Housing search', 'L40': 'Housing expense', 'L41': 'Rent assistance',
    'L50': 'Homeowners', 'L80': 'Housing support', 'L81': 'Home improvement',
    'L82': 'Housing counseling', 'L99': 'Housing NEC',
    # Public Safety
    'M': 'Public safety',
    'M20': 'Disaster preparedness', 'M23': 'Search/rescue',
    'M24': 'Fire prevention', 'M30': 'Emergency services',
    'M40': 'Safety education',
    # Recreation/Sports
    'N': 'Recreation/sports',
    'N20': 'Recreation', 'N30': 'Sports training', 'N31': 'Baseball',
    'N32': 'Basketball', 'N33': 'Football', 'N34': 'Soccer',
    'N35': 'Swimming', 'N36': 'Golf', 'N37': 'Tennis', 'N38': 'Olympics',
    'N40': 'Sports teams', 'N50': 'Recreation centers', 'N60': 'Amusement',
    'N61': 'Fairs', 'N62': 'Parks', 'N68': 'Winter sports', 'N70': 'Camping',
    'N71': 'Youth camps', 'N72': 'Scouting', 'N80': 'Sports clubs',
    'N99': 'Recreation NEC',
    # Youth Development (non-religious)
    'O': 'Youth development',
    'O20': 'Youth centers', 'O21': 'Boys & Girls clubs',
    'O22': 'Big Brothers/Sisters', 'O23': 'Youth mentoring',
    'O30': 'Adult/child matching', 'O31': 'Youth mentoring',
    'O40': 'Scouting', 'O50': 'Youth leadership', 'O51': 'Youth clubs',
    'O52': 'Youth development programs', 'O53': 'Youth service',
    'O54': 'Youth ministry', 'O55': 'Youth religious', 'O99': 'Youth NEC',
    # Human Services
    'P': 'Human services',
    'P20': 'Human service orgs', 'P21': 'United Way', 'P22': 'Community',
    'P24': 'Salvation Army', 'P26': 'Volunteer', 'P27': 'Community centers',
    'P28': 'Neighborhood centers', 'P29': 'Thrift stores', 'P30': 'Disabilities',
    'P31': 'Blind', 'P32': 'Deaf', 'P33': 'Developmentally disabled',
    'P40': 'Family services', 'P41': 'Adoption', 'P42': 'Child care',
    'P43': 'Family violence', 'P44': 'Runaway youth', 'P45': 'Pregnancy',
    'P46': 'Fatherhood', 'P47': 'Grandparents', 'P48': 'Child care',
    'P50': 'Personal services', 'P51': 'Financial counseling',
    'P52': 'Transportation', 'P60': 'Emergency assistance',
    'P61': 'Food banks', 'P62': 'Clothing', 'P63': 'Aid distribution',
    'P64': 'Utility assistance', 'P65': 'Disaster relief',
    'P70': 'Residential care', 'P71': 'Adult day care', 'P72': 'Hospice',
    'P73': 'Group homes', 'P74': 'Transitional care', 'P75': 'Senior centers',
    'P80': 'Family violence', 'P81': 'Child abuse', 'P82': 'Sexual assault',
    'P83': 'Elder abuse', 'P84': 'Stalking', 'P85': 'Trauma',
    'P86': 'Veterans services', 'P87': 'Military', 'P99': 'Human services NEC',
    # International
    'Q': 'International',
    'Q20': 'International development', 'Q21': 'International aid',
    'Q22': 'Disaster relief', 'Q23': 'Refugee assistance',
    'Q30': 'International affairs', 'Q31': 'Human rights',
    'Q32': 'Peace/security', 'Q33': 'Foreign policy', 'Q34': 'Diplomacy',
    'Q35': 'International orgs', 'Q36': 'International exchange',
    'Q38': 'International development', 'Q40': 'Development assistance',
    'Q41': 'Microfinance', 'Q42': 'International agriculture',
    'Q43': 'Water', 'Q44': 'Energy', 'Q45': 'Health programs',
    'Q46': 'Population', 'Q47': 'Economic development', 'Q48': 'Democracy',
    'Q50': 'International disaster', 'Q51': 'Emergency relief',
    'Q70': 'Humanitarian', 'Q71': 'International relief',
    'Q99': 'International NEC',
    # Civil Rights
    'R': 'Civil rights',
    'R12': 'Voting rights', 'R20': 'Civil liberties', 'R22': 'Women rights',
    'R23': 'Disability rights', 'R24': 'Elder rights', 'R25': 'LGBTQ rights',
    'R26': 'Veteran rights', 'R30': 'Intergroup relations',
    'R60': 'Racial justice', 'R61': 'Immigrant rights', 'R62': 'Youth rights',
    'R63': 'Family rights', 'R99': 'Civil rights NEC',
    # Community Improvement
    'S': 'Community improvement',
    'S20': 'Community development', 'S21': 'Community planning',
    'S22': 'Neighborhood centers', 'S23': 'Economic development',
    'S30': 'Business/industry', 'S31': 'Small business',
    'S32': 'Economic development', 'S40': 'Nonprofit management',
    'S41': 'Capacity building', 'S42': 'Technical assistance',
    'S43': 'Management support', 'S46': 'Boards training',
    'S47': 'Financial management', 'S50': 'Rural development',
    'S80': 'Leadership', 'S81': 'Community coalitions',
    'S82': 'Community engagement', 'S99': 'Community improvement NEC',
    # Science/Tech
    'U': 'Science/technology',
    'U20': 'General science', 'U21': 'Science research',
    'U30': 'Physical science', 'U31': 'Astronomy', 'U32': 'Chemistry',
    'U33': 'Physics', 'U34': 'Geology', 'U36': 'Oceanography',
    'U40': 'Engineering', 'U41': 'Computer science',
    'U42': 'Mathematics', 'U50': 'Biological sciences',
    'U99': 'Science NEC',
    # Social Science
    'V': 'Social science',
    'V20': 'General social science', 'V21': 'Anthropology',
    'V22': 'Economics', 'V23': 'Political science', 'V24': 'Sociology',
    'V25': 'Demography', 'V26': 'Law', 'V30': 'Interdisciplinary',
    'V31': 'Black studies', 'V32': 'Women studies', 'V33': 'Ethnic studies',
    'V34': 'Urban studies', 'V35': 'International studies',
    'V36': 'Gerontology', 'V37': 'Labor studies', 'V99': 'Social science NEC',
    # Animal-related
    'D20': 'Animal shelter', 'D21': 'Animal adoption', 'D22': 'Spay/neuter',
    'D30': 'Wildlife preservation', 'D31': 'Endangered species',
    'D32': 'Bird preservation', 'D33': 'Zoo/aquarium', 'D34': 'Veterinary',
    'D40': 'Animal training', 'D50': 'Animal research', 'D60': 'Animal services',
}

# Name keywords that strongly indicate NOT a grant-making foundation
NAME_REMOVE_KEYWORDS = [
    # Schools/educational
    ' school ', ' elementary school', 'high school', 'middle school',
    'preschool', 'pre-school', 'kindergarten', 'head start',
    'parent-teacher', 'pta', 'ptsa', 'parent teacher',
    'university', 'college of', 'institute of technology',
    'academy', 'boarding school', 'charter school',
    
    # Medical
    'hospital', 'clinic', 'medical center', 'health center',
    'nursing home', 'hospice', 'assisted living', 'rehab',
    'dialysis', 'cancer center', 'heart institute',
    
    # Recreation
    'athletic', 'stadium', 'arena', 'sports club', 'golf',
    'swim club', 'tennis', 'baseball', 'soccer', 'football',
    'basketball', 'recreation center', 'playground',
    'youth sports', 'little league', 'pop warner',
    
    # Animal
    'animal shelter', 'humane society', 'spca', 'rescue',
    'veterinary', 'zoo', 'aquarium', 'wildlife',
    'cat rescue', 'dog rescue', 'animal welfare',
    
    # Local community
    'fire department', 'police', 'sheriff', 'volunteer fire',
    'neighborhood association', 'hoa ', 'homeowners',
    'civic association', 'community center',
    'senior center', 'library', 'museum of',
    
    # Arts
    'performing arts', 'theatre', 'theater', 'orchestra',
    'symphony', 'opera', 'ballet', 'dance', 'chorus',
    'choir', 'band boosters', 'art guild',
    
    # Environmental
    'conservation', 'nature preserve', 'land trust',
    'environmental', 'watershed', 'river cleanup',
    'park foundation', 'botanical garden', 'arboretum',
    
    # Professional associations
    'association of', 'chamber of commerce', 'bar association',
    'medical association', 'dental association',
    'realtors', 'alumni association',
    
    # Individual churches (not grant-making)
    ' church', ' chapel', 'cathedral', 'parish',
    'congregation of', 'ministries international',
    'evangelistic association', 'gospel mission',
    
    # Service clubs
    'rotary', 'kiwanis', 'lions club', 'elks',
    'moose lodge', 'vfw', 'american legion',
    'shriners', 'masonic',
    
    # Specific named foundations that fund only one institution
    ' of ', 'for the benefit of', 'solely for the',
]

# Names that are clearly not grant-makers for external students
NAME_REMOVE_EXACT_PATTERNS = [
    r'\b(church|chapel|cathedral|parish|congregation)\b.*\b(foundation|fund)\b',
    r'\b(foundation|fund)\b.*\bfor the benefit of\b',
    r'\b(support|friends of|auxiliary)\b.*\b(foundation)\b',
    r'\b(museum|library|hospital|clinic)\b.*\b(foundation)\b',
]

# Organizations to keep even if they match removal rules (override)
KEEP_OVERRIDE = [
    'foundation for theological education',
    'foundation for reformed theology',
    'fund for theological education',
    'christian missionary scholarship foundation',
    'lanier theological library foundation',
    'biblical studies foundation',
    'woerner foundation for world missions',
    'christian scholarships missions and projects foundation',
    'covenant christian foundation',
    'tulsa christian foundation',
    'christian legacy foundation',
    'lawrence christian ministry foundation',
    'kingdom advancement foundation',
    'global interfaith foundation',
    'kbl mission foundation',
    'msk mission foundation',
    'speak the word ministry foundation',
    'find me faithful foundation',
    'jmb hope foundation',
    'faith hope and love foundation',
    'grace k and wesley s alpert charitable foundation',
    'mission increase foundation',
    'skyline foundation',
    'jubilee foundation',
    'the lynd and foster friess family foundation',
    'gil charitable foundation',
    'james l and mary d macfarlane charitable foundation',
    'koonce family foundation',
    'fundet foundation',
    'ronald and vicki canakaris family foundation',
    'presbyterian village north foundation',
    'blue cloud foundation',
    'marian wayside shrine foundation',
    'farms for life foundation',
    'religious society of friends foundation for the aging',
    'foundation for theological education in southeast asia',
    'leonard gigowski catholic education foundation',
    'trinity foundation',
    'raskob foundation for catholic activities',
    'siebert lutheran foundation',
    'grace farms foundation',
    'sikh spirit foundation',
    'beloved in christ foundation',
    'i am mercy foundation',
    'luckyday foundation',
    'hagan scholarship foundation',
    'minnie patton scholarship foundation',
    'lilly endowment',
    'templeton foundation',
    'anglican foundation of canada',
    'united church of canada foundation',
    'mcconnell family foundation',
    'catherine donnelly foundation',
]

# Load master list (filtered version - already had schools removed)
master_path = os.path.join(base, 'theology_foundations_only.csv')
with open(master_path, 'r') as f:
    rows = list(csv.DictReader(f))

print(f"Loaded {len(rows)} entries")
print(f"HIGH: {len([r for r in rows if r['PRIORITY']=='HIGH'])}")
print(f"MEDIUM: {len([r for r in rows if r['PRIORITY']=='MEDIUM'])}")

# Apply aggressive filtering
kept = []
removed = {'ntee': 0, 'name_keyword': 0, 'pattern': 0}

for r in rows:
    name = r['NAME'].lower().strip()
    ntee = r.get('NTEE', '').strip().upper()
    score = int(r.get('THEOLOGY_SCORE', '0'))
    priority = r['PRIORITY']
    
    # Check override list first
    is_override = any(kw in name for kw in KEEP_OVERRIDE)
    if is_override:
        kept.append(r)
        continue
    
    # Check NTEE removal
    removed_by_ntee = False
    if ntee:
        for code, reason in NTEE_REMOVE.items():
            if ntee.startswith(code):
                removed['ntee'] += 1
                removed_by_ntee = True
                break
    if removed_by_ntee:
        continue
    
    # Check name keyword removal
    removed_by_keyword = False
    for kw in NAME_REMOVE_KEYWORDS:
        if kw in name:
            removed['name_keyword'] += 1
            removed_by_keyword = True
            break
    if removed_by_keyword:
        continue
    
    # Check regex patterns
    removed_by_pattern = False
    for pat in NAME_REMOVE_EXACT_PATTERNS:
        if re.search(pat, name):
            removed['name_keyword'] += 1
            removed_by_pattern = True
            break
    if removed_by_pattern:
        continue
    
    kept.append(r)

print(f"\nAfter filtering: {len(kept)} entries")
print(f"Removed by NTEE code: {removed['ntee']}")
print(f"Removed by name keyword: {removed['name_keyword']}")
print(f"Removed by pattern: {removed['pattern']}")

high = [r for r in kept if r['PRIORITY'] == 'HIGH']
med = [r for r in kept if r['PRIORITY'] == 'MEDIUM']
print(f"HIGH: {len(high)}, MEDIUM: {len(med)}")

# Save filtered
filtered_path = os.path.join(base, 'theology_foundations_only.csv')
with open(filtered_path, 'w', newline='', encoding='utf-8') as f:
    w = csv.DictWriter(f, fieldnames=rows[0].keys() if rows else [])
    w.writeheader()
    w.writerows(kept)

# Rebuild ready-to-send
high_ready = [r for r in kept if r['PRIORITY'] == 'HIGH' and r['HAS_EMAIL'] == 'YES']
med_ready = [r for r in kept if r['PRIORITY'] == 'MEDIUM' and r['HAS_EMAIL'] == 'YES']

send_path = os.path.join(base, 'theology_foundations_ready.csv')
with open(send_path, 'w', newline='', encoding='utf-8') as f:
    w = csv.DictWriter(f, fieldnames=rows[0].keys() if rows else [])
    w.writeheader()
    w.writerows(high_ready + med_ready)

print(f"\nReady to send: {len(high_ready)} HIGH + {len(med_ready)} MEDIUM = {len(high_ready)+len(med_ready)} total")
print(f"Still need email: {len([r for r in kept if r['HAS_EMAIL']=='NEED SCRAPING'])}")

# Print top
print(f"\n=== TOP 30 FILTERED FOUNDATIONS ===")
for r in (high_ready + [r for r in kept if r['HAS_EMAIL']=='NEED SCRAPING' and r['PRIORITY']=='HIGH'])[:30]:
    email = '✓' if r['HAS_EMAIL'] == 'YES' else '✗'
    print(f"  [{r['PRIORITY']:6s}] [{r['THEOLOGY_SCORE']:>3s}] {email} {r['NAME'][:55]} ({r['CITY']}, {r['STATE']})")
