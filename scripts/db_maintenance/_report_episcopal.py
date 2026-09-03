"""Generate clean Episcopal food insecurity report with:
1. AME/CME/AME Zion exclusion (methodist episcopal but keep protestant episcopal)
2. Legal name cleanup (strip diocese prefix from church names)
3. Grouping by diocese
"""
from google.cloud import bigquery
from datetime import datetime
import re, sys

# Import county→diocese mapping for multi-diocese states
sys.path.insert(0, 'data')
from tec_county_diocese import STATE_COUNTY_DIOCESE

client = bigquery.Client(project='american-rel-infra')
DATASET = 'american-rel-infra.American_Religious_Infrastructure'

# ═══ Clean Episcopal filter ═══
# PRIMARY: denomination column (precise, no name-guessing needed for AME/CME/Zion/etc.)
# SECONDARY: congregation-level filters (remove foundations, schools, diocese offices, etc.)
CLEAN_FILTER = """\
    denomination = 'Episcopal Church'
    -- Must contain a congregation indicator word
    AND (LOWER(name) LIKE '%church%' OR LOWER(name) LIKE '%parish%' 
         OR LOWER(name) LIKE '%cathedral%' OR LOWER(name) LIKE '%chapel%'
         OR LOWER(name) LIKE '%congregation%')
    -- Exclude non-congregational entities
    AND NOT (LOWER(name) LIKE '%foundation%' OR LOWER(name) LIKE '%endowment%' OR LOWER(name) LIKE '% trust%')
    AND NOT (LOWER(name) LIKE '%school%' OR LOWER(name) LIKE '%academy%')
    -- Diocese-level entities (even if "church" appears in denominational name)
    AND NOT (LOWER(name) LIKE 'diocese of % protestant episcopal church%')
    AND NOT (LOWER(name) LIKE 'diocese of the % anglican episcopal church%')
    AND NOT (LOWER(name) LIKE 'diocese of the % reformed episcopal church%')
    AND NOT (LOWER(name) LIKE 'episcopal church diocese of %')
    AND NOT (LOWER(name) LIKE '%protestant episcopal church in the diocese of%')
    AND NOT (LOWER(name) LIKE '%protestant episcopal church diocese of%')
    -- Diocese offices that aren't congregations
    AND NOT (
      LOWER(name) LIKE '%diocese%' 
      AND NOT (LOWER(name) LIKE '%church%' OR LOWER(name) LIKE '%parish%' 
               OR LOWER(name) LIKE '%cathedral%' OR LOWER(name) LIKE '%chapel%'
               OR LOWER(name) LIKE '%mission%' OR LOWER(name) LIKE '%congregation%')
    )
    -- Non-TEC denominations mislabeled as Episcopal Church in the DB
    AND NOT (LOWER(name) LIKE '%methodist episcopal%' AND NOT LOWER(name) LIKE '%protestant episcopal%')
    AND NOT (LOWER(name) LIKE '%methodistepiscopal%')
    AND NOT (LOWER(name) LIKE '%reformed episcopal%')
    AND NOT (LOWER(name) LIKE '%charismatic episcopal%')
    AND NOT (LOWER(name) LIKE '%independent episcopal%')
    AND NOT (LOWER(name) LIKE '%independnet episcopal%')  -- misspelling of Independent
    AND NOT (LOWER(name) LIKE '%united episcopal church%')
    AND NOT (LOWER(name) LIKE '%christian episcopal church%')
    AND NOT (LOWER(name) LIKE '%union methodist episcopal%')
    AND NOT (LOWER(name) LIKE '%union american methodist episcopal%')
    AND NOT (LOWER(name) LIKE '%wesleyan methodist episcopal%')
    AND NOT (LOWER(name) LIKE '%african methodist episcopal%')
    AND NOT (LOWER(name) LIKE '%african medhodist episcopal%')  -- misspelling
    AND NOT (LOWER(name) LIKE '%african metholdist episcopal%')  -- misspelling
    AND NOT (LOWER(name) LIKE '%african medethodist episcopal%') -- misspelling
    AND NOT (LOWER(name) LIKE '%episcopal zion%')
    AND NOT (LOWER(name) LIKE '%pentecostal episcopal%')
    AND NOT (LOWER(name) LIKE '%pentacostal episcopal%')
    -- Additional cleanups
    AND NOT (LOWER(name) LIKE '%retirement%' OR LOWER(name) LIKE '%housing%')
    AND NOT (LOWER(name) LIKE '%bishop%')
    AND NOT (LOWER(name) LIKE '%convention%')
    AND NOT (LOWER(name) LIKE '%rector and vestry%')
    AND NOT (LOWER(name) LIKE '%rector wardens vestry%')  -- legal holding entity
    AND NOT (LOWER(name) LIKE '%wardens vestrymen%')  -- legal holding entity
    AND NOT (LOWER(name) LIKE '%proprietors of%')  -- legal holding entity
    AND NOT (LOWER(name) LIKE '% fund for % episcopal%')  -- fund LLC subentity
    AND NOT (LOWER(name) LIKE '% fund of % episcopal%')  -- fund LLC subentity
    AND NOT (LOWER(name) LIKE '%trustees of donations to the protestant episcopal%')
    AND NOT (LOWER(name) LIKE '%igbo%')
    AND NOT (LOWER(name) LIKE '%ministries inc%')
    AND NOT (LOWER(name) LIKE '%episcopal mission%')
    AND NOT (LOWER(name) LIKE 'protestant episcopal church in the united states of a%')
    AND NOT (LOWER(name) LIKE 'protestant episcopal church in the us%')  -- national body, not congregation
    AND NOT (LOWER(name) LIKE '%the protestant episcopal church in the usa%')  -- national body variant
    AND NOT (LOWER(name) LIKE '%south sudanese%episcopal%')  -- separate Anglican province, not TEC
    AND NOT (LOWER(name) LIKE '%episcopal church in the united states of %')
    AND NOT (LOWER(name) LIKE '%church women%')
    AND NOT (LOWER(name) LIKE '%church home%')
    AND NOT (LOWER(name) LIKE '%seminary%')
    AND NOT (LOWER(name) LIKE '%communion of episcopal%')
    AND NOT (LOWER(name) LIKE '%episcopal church council%')  -- governance body, not congregation
"""

# ═══ Name cleanup ═══
# Strip diocese legal prefix: "DIOCESE OF X INC Church Name" -> "Church Name"
DIOCESE_PREFIX_RE = re.compile(
    r'^(?:EPISCOPAL\s+)?DIOCESE(?:S)?\s+(?:OF\s+)?'
    r'([A-Z\s]+?)(?:\s+INC)?\s+'
    r'(?=(?:ST\.?\s|SAINT\s|ALL\s|CHRIST\s|TRINITY\s|GRACE\s|CALVARY\s|EMMANUEL\s|EPIPHANY\s|HOLY\s|GOOD\s|ASCENSION\s|CHURCH\s|ST\s))',
    re.IGNORECASE
)

DIOCESE_ABBREV = {
    'SE FL': 'Southeast Florida', 'SOUTHEAST FL': 'Southeast Florida',
    'SOUTHEAST FLORIDA': 'Southeast Florida', 'SW FL': 'Southwest Florida',
    'SW FLORIDA': 'Southwest Florida', 'NW TX': 'Northwest Texas',
    'W TX': 'West Texas', 'W TENNESSEE': 'West Tennessee',
    'E TENNESSEE': 'East Tennessee', 'W MICHIGAN': 'Western Michigan',
    'E MICHIGAN': 'Eastern Michigan', 'N MICHIGAN': 'Northern Michigan',
    'W NEW YORK': 'Western New York', 'W NORTH CAROLINA': 'Western North Carolina',
    'E CAROLINA': 'East Carolina', 'W MASSACHUSETTS': 'Western Massachusetts',
    'W LOUISIANA': 'Western Louisiana', 'N CALIFORNIA': 'Northern California',
    'S VIRGINIA': 'Southern Virginia', 'SW VIRGINIA': 'Southwest Virginia',
    'W VIRGINIA': 'West Virginia', 'N INDIANA': 'Northern Indiana',
    'MISS': 'Mississippi',
}

# ═══ State → Diocese lookup (from Wikipedia: Ecclesiastical provinces and dioceses of the Episcopal Church) ═══
# Single-diocese states: direct mapping
# Multi-diocese states: county-level would be ideal, but for now use most likely based on county_fips
STATE_DIOCESE = {
    # Single-diocese states
    'AK': ['Alaska'],
    'AZ': ['Arizona'],
    'CO': ['Colorado'],
    'CT': ['Connecticut'],
    'DE': ['Delaware'],
    'GA': ['Georgia', 'Atlanta'],  # GA has Diocese of Georgia (Savannah) + Diocese of Atlanta
    'HI': ['Hawaii'],
    'IA': ['Iowa'],
    'ID': ['Idaho'],
    'KS': ['Kansas', 'Western Kansas'],
    'KY': ['Kentucky', 'Lexington'],
    'LA': ['Louisiana', 'Western Louisiana'],
    'MA': ['Massachusetts', 'Western Massachusetts'],
    'MD': ['Maryland', 'Washington', 'Easton'],  # Washington covers DC+MD counties
    'ME': ['Maine'],
    'MI': ['Michigan', 'Great Lakes', 'Northern Michigan', 'Western Michigan', 'Eastern Michigan'],
    'MN': ['Minnesota'],
    'MO': ['Missouri', 'West Missouri'],
    'MS': ['Mississippi'],
    'MT': ['Montana'],
    'NC': ['North Carolina', 'East Carolina', 'Western North Carolina'],
    'ND': ['North Dakota'],
    'NE': ['Nebraska'],
    'NH': ['New Hampshire'],
    'NJ': ['New Jersey', 'Newark'],
    'NM': ['Rio Grande'],
    'NV': ['Nevada'],
    'NY': ['New York', 'Long Island', 'Albany', 'Central New York', 'Rochester', 'Western New York'],
    'OH': ['Ohio', 'Southern Ohio'],
    'OK': ['Oklahoma'],
    'OR': ['Oregon', 'Eastern Oregon'],
    'PA': ['Pennsylvania', 'Pittsburgh', 'Northwestern Pennsylvania', 'Susquehanna'],
    'RI': ['Rhode Island'],
    'SC': ['South Carolina', 'Upper South Carolina'],
    'SD': ['South Dakota'],
    'TN': ['Tennessee', 'East Tennessee', 'West Tennessee'],
    'TX': ['Texas', 'Dallas', 'West Texas', 'Northwest Texas', 'Rio Grande'],
    'UT': ['Utah'],
    'VA': ['Virginia', 'Southern Virginia', 'Southwestern Virginia'],
    'VT': ['Vermont'],
    'WA': ['Olympia', 'Spokane'],
    'WI': ['Wisconsin'],
    'WV': ['West Virginia'],
    'WY': ['Wyoming'],
    'AL': ['Alabama'],
    'AR': ['Arkansas'],
    'CA': ['California', 'Los Angeles', 'San Diego', 'San Joaquin', 'Northern California', 'El Camino Real'],
    'DC': ['Washington'],
    'FL': ['Florida', 'Southeast Florida', 'Southwest Florida', 'Central Florida', 'Central Gulf Coast'],
    'IL': ['Chicago', 'Springfield'],
    'IN': ['Indianapolis', 'Northern Indiana'],
}

def assign_diocese(state, county_name):
    """Assign diocese based on state and county.
    Uses STATE_COUNTY_DIOCESE mapping for multi-diocese states.
    Falls back to primary diocese if county not mapped."""
    if not state or state not in STATE_DIOCESE:
        return None
    dioceses = STATE_DIOCESE[state]
    if len(dioceses) == 1:
        return dioceses[0]
    # Multi-diocese state — check county-level mapping
    if county_name and state in STATE_COUNTY_DIOCESE:
        county_key = county_name.strip()
        if county_key.lower().endswith(' county'):
            county_key = county_key[:-7].strip()
        state_map = STATE_COUNTY_DIOCESE[state]
        if county_key in state_map:
            return state_map[county_key]
        # Case-insensitive fallback
        county_upper = county_key.upper()
        for k, v in state_map.items():
            if k.upper() == county_upper:
                return v
    # Fallback to primary diocese
    return dioceses[0]

def clean_name(raw_name):
    """Strip diocese prefix and return (clean_name, diocese)."""
    if not raw_name:
        return raw_name, None
    m = DIOCESE_PREFIX_RE.match(raw_name)
    if m:
        diocese_raw = m.group(1).strip()
        remaining = raw_name[m.end():].strip()
        if remaining and len(remaining) > 3:
            diocese = DIOCESE_ABBREV.get(diocese_raw.upper(), diocese_raw.title())
            return remaining, diocese
    return raw_name, None

# Also a broader diocese extractor for names like "ALL ANGELS EPISCOPAL CHURCH INC DIOCESE OF SOUTHEAST FLORIDA"
DIOCESE_SUFFIX_RE = re.compile(
    r'\bINC\s+DIOCESE\s+OF\s+([A-Z\s]+?)$', re.IGNORECASE
)

def normalize_diocese_name(raw_diocese):
    """Normalize diocese name: strip INC, strip EPISCOPAL suffix, canonicalize."""
    d = raw_diocese.strip().upper()
    # Strip suffixes (try all, not just first match)
    changed = True
    while changed:
        changed = False
        for suffix in [' INC', ' EPISCOPAL', ' PROTESTANT EPISCOPAL', ' DIOCESE', ' INC.']:
            if d.endswith(suffix):
                d = d[:-len(suffix)].strip()
                changed = True
    # Abbrev lookup
    return DIOCESE_ABBREV.get(d, d.title())

def extract_diocese_from_name(raw_name):
    """Try to extract diocese from both prefix and suffix patterns."""
    _, diocese = clean_name(raw_name)
    if diocese:
        return normalize_diocese_name(diocese)
    # Try suffix pattern: "...INC DIOCESE OF X"
    m = DIOCESE_SUFFIX_RE.search(raw_name)
    if m:
        return normalize_diocese_name(m.group(1).strip())
    return None

# ═══ Run query ═══
print("Querying BigQuery...", end=" ", flush=True)
results = list(client.query(f"""
    SELECT name, city, state, county_poverty_rate, county_median_hh_income, 
           county_total_pop, county_name, county_unemployment_rate
    FROM `{DATASET}.vw_church_census`
    WHERE {CLEAN_FILTER}
      AND county_poverty_rate IS NOT NULL
      AND county_poverty_rate >= 15
    ORDER BY county_poverty_rate DESC
""").result())
print(f"{len(results):,} rows")

# ═══ Clean names and strip diocese suffix from display ═══
diocese_groups = {}
no_diocese = []
cleaned = []

for row in results:
    name, city, state, pov, income, pop, county_name, unemp = row
    
    # Clean the legal name: strip diocese prefix AND suffix
    clean_nm, _ = clean_name(name)
    
    # Also strip " INC DIOCESE OF [Anything]" suffix from display name
    clean_nm = re.sub(r'\s+INC\s+DIOCESE\s+OF\s+[A-Z\s]+$', '', (clean_nm or name), flags=re.IGNORECASE)
    
    # Capitalize nicely
    if clean_nm:
        clean_nm = clean_nm.strip()
        clean_nm = re.sub(r'\bSt\s+', 'St ', clean_nm)
    
    # Determine diocese: first from name, then from state+county lookup
    diocese = extract_diocese_from_name(name)
    if not diocese:
        diocese = assign_diocese(state, county_name)
    
    # Tag community-facing facilities
    tags = []
    nm_upper = (clean_nm or name).upper()
    if 'COMMUNITY CENTER' in nm_upper:
        tags.append('[Community Center]')
    if 'FOOD PANTRY' in nm_upper or 'FOOD BANK' in nm_upper or 'SOUP KITCHEN' in nm_upper:
        tags.append('[Food Ministry]')
    if 'OUTREACH' in nm_upper:
        tags.append('[Outreach]')
    tag_str = ' ' + ' '.join(tags) if tags else ''
    
    entry = {
        'name': clean_nm or name,
        'original': name,
        'city': city, 'state': state, 'pov': pov,
        'income': income, 'pop': pop, 'county': county_name, 'unemp': unemp,
        'diocese': diocese, 'tags': tags
    }
    cleaned.append(entry)
    
    if diocese:
        diocese_groups.setdefault(diocese, []).append(entry)
    else:
        no_diocese.append(entry)

# ═══ Total ═══
total_all = list(client.query(f"""
    SELECT COUNT(*) FROM `{DATASET}.vw_church_census` WHERE {CLEAN_FILTER}
""").result())
total = total_all[0][0]

# ═══ Report ═══
lines = []
def L(s=""): lines.append(s)

L("=" * 72)
L("  EPISCOPAL CHURCH (TEC): CONGREGATIONS IN FOOD-INSECURE COMMUNITIES")
L("=" * 72)
L(f"  Generated: {datetime.now().strftime('%B %d, %Y')}")
L("  Source: American Religious Infrastructure Dataset (BigQuery)")
L(f"  Total TEC congregations: {total:,}")
L(f"  Showing: {len(results)} in counties with >=15% poverty ({len(results)/total*100:.1f}% of total)")
L("")
L("  EXCLUDED: foundations, endowments, trusts, schools, diocese offices,")
L("  bishops, conventions, retirement homes. Filtered by denomination = 'Episcopal Church'.")
L("  Diocese-prefixed legal names cleaned.")
L("=" * 72)

# Top 50
L("")
L("-" * 72)
L("  TOP 50 BY COUNTY POVERTY RATE")
L("-" * 72)
L(f"  {'#':>3} {'Congregation':<53} {'Location':<22} {'Pov':>6} {'Diocese':<24}")
L(f"  {'-'*3} {'-'*53} {'-'*22} {'-'*6} {'-'*24}")

for i, entry in enumerate(cleaned[:50], 1):
    nm = (entry['name'] + (' ' + ' '.join(entry.get('tags', [])) if entry.get('tags') else ''))[:53]
    loc = f"{entry['city'] or '?'}, {entry['state'] or '??'}"
    pov = f"{entry['pov']*1:.1f}%" if entry['pov'] else 'N/A'
    dio = (entry['diocese'] or '')[:(24)]
    L(f"  {i:3} {nm:<53} {loc:<22} {pov:>6} {dio:<24}")

# Summary
count_20 = sum(1 for e in cleaned if e['pov'] and e['pov'] >= 20)
avg_pov = sum(e['pov'] for e in cleaned if e['pov']) / max(1, len([e for e in cleaned if e['pov']]))
incomes = [e['income'] for e in cleaned if e['income']]
avg_income = sum(incomes) / max(1, len(incomes))

L("")
L("-" * 72)
L("  SUMMARY")
L("-" * 72)
L(f"  >=15% poverty: {len(results):,} ({len(results)/total*100:.1f}%)  |  >=20%: {count_20} ({count_20/total*100:.1f}%)")
L(f"  Avg poverty rate: {avg_pov:.1f}%  |  Avg median income: ${avg_income:,.0f}")
L(f"  Dioceses represented: {len(diocese_groups)}")
if cleaned:
    L(f"  Highest poverty county: {cleaned[0]['pov']*1:.1f}%")

# By Diocese
L("")
L("=" * 72)
L("  BY DIOCESE")
L("=" * 72)

for dname, dchurches in sorted(diocese_groups.items(), key=lambda x: len(x[1]), reverse=True):
    if not dchurches:
        continue
    dpovs = [e['pov'] for e in dchurches if e['pov']]
    avg_p = sum(dpovs) / max(1, len(dpovs))
    high_pov = max(dpovs) if dpovs else 0
    L(f"\n  Diocese of {dname}")
    L(f"  {len(dchurches)} congregations | avg {avg_p:.1f}% poverty | max {high_pov*1:.1f}%")
    L(f"  {'-'*60}")
    
    for e in sorted(dchurches, key=lambda x: x['pov'] or 0, reverse=True)[:12]:
        nm = (e['name'] + (' ' + ' '.join(e.get('tags', [])) if e.get('tags') else ''))[:53]
        loc = f"{e['city'] or '?'}, {e['state'] or '??'}"
        pov = f"{e['pov']*1:.1f}%" if e['pov'] else 'N/A'
        L(f"    {nm:<53} {loc:<22} {pov:>6}")
    if len(dchurches) > 12:
        L(f"    ... +{len(dchurches)-12} more")

# Ungrouped
if no_diocese:
    L(f"\n  UNGROUPED (diocese unknown) — {len(no_diocese)} congregations")
    L(f"  {'-'*60}")
    for e in sorted(no_diocese, key=lambda x: x['pov'] or 0, reverse=True)[:15]:
        nm = (e['name'] + (' ' + ' '.join(e.get('tags', [])) if e.get('tags') else ''))[:53]
        loc = f"{e['city'] or '?'}, {e['state'] or '??'}"
        pov = f"{e['pov']*1:.1f}%" if e['pov'] else 'N/A'
        L(f"    {nm:<53} {loc:<22} {pov:>6}")
    if len(no_diocese) > 15:
        L(f"    ... +{len(no_diocese)-15} more")

# State summary
L("")
L("-" * 72)
L("  BY STATE")
L("-" * 72)
state_counts = {}
for e in cleaned:
    st = e['state'] or '??'
    sc = state_counts.setdefault(st, {'count': 0, 'pov_sum': 0.0})
    sc['count'] += 1
    sc['pov_sum'] += (e['pov'] or 0)

L(f"  {'State':<6} {'Churches':>8} {'Avg Pov':>8}")
L(f"  {'-'*6} {'-'*8} {'-'*8}")
for st in sorted(state_counts, key=lambda s: state_counts[s]['count'], reverse=True):
    sc = state_counts[st]
    L(f"  {st:<6} {sc['count']:>8} {(sc['pov_sum']/sc['count']):>7.1f}%")

L("")
L("=" * 72)
L(f"  {count_20} TEC congregations in persistent-poverty counties (>=20% USDA threshold).")
L("  These represent immediate opportunities for targeted nutrition partnerships.")
L("=" * 72)

# Write
output = '\n'.join(lines)
with open('reports/episcopal_food_insecurity.txt', 'w', encoding='utf-8') as f:
    f.write(output)

print(f"\nReport: reports/episcopal_food_insecurity.txt ({len(output):,} bytes)")
print(f"TEC congregations: {total:,} total | {len(results):,} >=15% poverty ({len(results)/total*100:.1f}%) | {count_20} >=20% ({count_20/total*100:.1f}%)")
print(f"Dioceses: {len(diocese_groups)} | Ungrouped: {len(no_diocese)}")
