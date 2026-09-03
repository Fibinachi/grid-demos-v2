"""
Classify non-US Christians using country priors + name patterns.
DeepSeek only for ambiguous cases.
"""
import sqlite3, time

DB = r'E:\grid\churches.db'

# Country → (legacy, tradition, movement) priors
# Based on dominant Christian tradition in each country
COUNTRY_PRIORS = {
    # Catholic-majority countries → Roman Catholic
    'IT': ('Catholic', 'Roman Catholic', None),      # Italy
    'ES': ('Catholic', 'Roman Catholic', None),      # Spain
    'FR': ('Catholic', 'Roman Catholic', None),      # France
    'PL': ('Catholic', 'Roman Catholic', None),      # Poland
    'PT': ('Catholic', 'Roman Catholic', None),      # Portugal
    'AT': ('Catholic', 'Roman Catholic', None),      # Austria
    'BE': ('Catholic', 'Roman Catholic', None),      # Belgium
    'HR': ('Catholic', 'Roman Catholic', None),      # Croatia
    'CZ': ('Catholic', 'Roman Catholic', None),      # Czech Republic
    'IE': ('Catholic', 'Roman Catholic', None),      # Ireland
    'LT': ('Catholic', 'Roman Catholic', None),      # Lithuania
    'SK': ('Catholic', 'Roman Catholic', None),      # Slovakia
    'SI': ('Catholic', 'Roman Catholic', None),      # Slovenia
    'HU': ('Catholic', 'Roman Catholic', None),      # Hungary
    'AR': ('Catholic', 'Roman Catholic', None),      # Argentina
    'CL': ('Catholic', 'Roman Catholic', None),      # Chile
    'CO': ('Catholic', 'Roman Catholic', None),      # Colombia
    'PE': ('Catholic', 'Roman Catholic', None),      # Peru
    'VE': ('Catholic', 'Roman Catholic', None),      # Venezuela
    'EC': ('Catholic', 'Roman Catholic', None),      # Ecuador
    'BO': ('Catholic', 'Roman Catholic', None),      # Bolivia
    'PY': ('Catholic', 'Roman Catholic', None),      # Paraguay
    'UY': ('Catholic', 'Roman Catholic', None),      # Uruguay
    'CR': ('Catholic', 'Roman Catholic', None),      # Costa Rica
    'PA': ('Catholic', 'Roman Catholic', None),      # Panama
    'DO': ('Catholic', 'Roman Catholic', None),      # Dominican Republic
    'GT': ('Catholic', 'Roman Catholic', None),      # Guatemala
    'HN': ('Catholic', 'Roman Catholic', None),      # Honduras
    'SV': ('Catholic', 'Roman Catholic', None),      # El Salvador
    'NI': ('Catholic', 'Roman Catholic', None),      # Nicaragua
    'CU': ('Catholic', 'Roman Catholic', None),      # Cuba
    'PR': ('Catholic', 'Roman Catholic', None),      # Puerto Rico
    
    # Protestant/Reformed majority
    'DE': ('Protestant', 'Lutheran', 'Evangelical Church in Germany'),    # Germany (EKD)
    'SE': ('Protestant', 'Lutheran', 'Church of Sweden'),
    'NO': ('Protestant', 'Lutheran', 'Church of Norway'),
    'DK': ('Protestant', 'Lutheran', 'Church of Denmark'),
    'FI': ('Protestant', 'Lutheran', 'Evangelical Lutheran Church of Finland'),
    'IS': ('Protestant', 'Lutheran', 'Church of Iceland'),
    'NL': ('Protestant', 'Reformed', 'Protestant Church in the Netherlands'),
    'CH': ('Protestant', 'Reformed', 'Swiss Reformed Church'),
    
    # Anglican
    'GB': ('Anglican', 'Anglican', 'Church of England'),
    'AU': ('Anglican', 'Anglican', 'Anglican Church of Australia'),
    'NZ': ('Anglican', 'Anglican', 'Anglican Church in Aotearoa, New Zealand'),
    'CA': ('Protestant', 'Non-Denominational', None),  # Too diverse for single prior
    
    # Orthodox
    'GR': ('Orthodox', 'Eastern Orthodox', 'Church of Greece'),
    'RU': ('Orthodox', 'Eastern Orthodox', 'Russian Orthodox Church'),
    'UA': ('Orthodox', 'Eastern Orthodox', 'Orthodox Church of Ukraine'),
    'RO': ('Orthodox', 'Eastern Orthodox', 'Romanian Orthodox Church'),
    'BG': ('Orthodox', 'Eastern Orthodox', 'Bulgarian Orthodox Church'),
    'RS': ('Orthodox', 'Eastern Orthodox', 'Serbian Orthodox Church'),
    'GE': ('Orthodox', 'Eastern Orthodox', 'Georgian Orthodox Church'),
    'CY': ('Orthodox', 'Eastern Orthodox', 'Church of Cyprus'),
    'MD': ('Orthodox', 'Eastern Orthodox', 'Moldovan Orthodox Church'),
    'MK': ('Orthodox', 'Eastern Orthodox', 'Macedonian Orthodox Church'),
    'ME': ('Orthodox', 'Eastern Orthodox', 'Montenegrin Orthodox Church'),
    
    # Mixed Catholic/Protestant → Catholic unless name suggests Protestant
    'BR': ('Catholic', 'Roman Catholic', None),       # Brazil (but many Pentecostals)
    'MX': ('Catholic', 'Roman Catholic', None),       # Mexico
    'PH': ('Catholic', 'Roman Catholic', None),       # Philippines
    
    # Lutheran state churches
    'EE': ('Protestant', 'Lutheran', 'Estonian Evangelical Lutheran Church'),
    'LV': ('Protestant', 'Lutheran', 'Evangelical Lutheran Church of Latvia'),
    
    # Other
    'ZA': ('Protestant', 'Non-Denominational', None), # South Africa (diverse)
    'KR': ('Protestant', 'Presbyterian', None),       # South Korea (strong Presbyterian)
    'NG': ('Protestant', 'Non-Denominational', None), # Nigeria (diverse Christian)
    'KE': ('Protestant', 'Non-Denominational', None), # Kenya
    'GH': ('Protestant', 'Non-Denominational', None), # Ghana
    'TZ': ('Protestant', 'Non-Denominational', None), # Tanzania
    'UG': ('Protestant', 'Non-Denominational', None), # Uganda
    'CD': ('Catholic', 'Roman Catholic', None),       # DRC
    'AO': ('Catholic', 'Roman Catholic', None),       # Angola
    'MZ': ('Catholic', 'Roman Catholic', None),       # Mozambique
}

# Name pattern overrides (override country prior if name matches)
NAME_PATTERNS = [
    ('%Baptist%', 'Protestant', 'Baptist', None),
    ('%Lutheran%', 'Protestant', 'Lutheran', None),
    ('%Methodist%', 'Protestant', 'Methodist', None),
    ('%Presbyterian%', 'Protestant', 'Presbyterian', None),
    ('%Pentecostal%', 'Protestant', 'Pentecostal', None),
    ('%Adventist%', 'Protestant', 'Adventist', None),
    ('%Anglican%', 'Anglican', 'Anglican', None),
    ('%Episcopal%', 'Anglican', 'Anglican', None),
    ('%Orthodox%', 'Orthodox', 'Eastern Orthodox', None),
    ('%Catholic%', 'Catholic', 'Roman Catholic', None),
    ('%Reformed%', 'Protestant', 'Reformed', None),
    ('%Evangelical%', 'Protestant', 'Evangelical', None),
    ('%Mormon%', 'Restorationist', 'Latter-day Saints', 'Church of Jesus Christ of Latter-day Saints'),
    ("%Latter-day Saints%", 'Restorationist', 'Latter-day Saints', 'Church of Jesus Christ of Latter-day Saints'),
    ("%Jehovah%", 'Other', "Jehovah's Witnesses", None),
    ('%Salvation Army%', 'Protestant', 'Holiness', 'Salvation Army'),
    ('%Assemblies of God%', 'Protestant', 'Pentecostal', 'Assemblies of God'),
    ('%Seventh-day Adventist%', 'Protestant', 'Adventist', 'Seventh-day Adventist'),
    ('%Church of the Nazarene%', 'Protestant', 'Holiness', 'Church of the Nazarene'),
    ('%Church of Christ%', 'Restorationist', 'Churches of Christ', None),
    ('%Iglesia%', 'Catholic', 'Roman Catholic', None),  # Spanish
    ('%Igreja%', 'Catholic', 'Roman Catholic', None),   # Portuguese
    ('%Chiesa%', 'Catholic', 'Roman Catholic', None),    # Italian
    ('%Église%', 'Catholic', 'Roman Catholic', None),    # French
    ('%Kirche%', 'Protestant', 'Lutheran', None),        # German
    ('%EKD%', 'Protestant', 'Lutheran', 'Evangelical Church in Germany'),
    ('%ELCA%', 'Protestant', 'Lutheran', 'Evangelical Lutheran Church in America'),
    ('%LCMS%', 'Protestant', 'Lutheran', 'Lutheran Church - Missouri Synod'),
]

def apply_classification():
    db = sqlite3.connect(DB)
    db.execute('PRAGMA busy_timeout=60000')
    c = db.cursor()
    
    # Get taxonomy IDs
    leg_ids = {r[0]: r[1] for r in c.execute("SELECT name, id FROM legacy").fetchall()}
    trad_ids = {r[0]: r[1] for r in c.execute("SELECT name, id FROM tradition").fetchall()}
    mov_ids = {r[0]: r[1] for r in c.execute("SELECT name, id FROM movement").fetchall()}
    
    total_applied = 0
    
    # Phase 1: Name patterns (override everything)
    print('=== Phase 1: Name patterns ===')
    for pattern, legacy, tradition, movement in NAME_PATTERNS:
        leg_id = leg_ids.get(legacy)
        trad_id = trad_ids.get(tradition)
        mov_id = mov_ids.get(movement) if movement else None
        
        if not leg_id:
            continue
        
        n = c.execute("""
            UPDATE churches SET legacy_id=?, tradition_id=?, movement_id=?,
            landmark_type=COALESCE(landmark_type, 'church')
            WHERE faith='Christian' AND country!='US' AND legacy_id IS NULL
            AND name LIKE ?
        """, (leg_id, trad_id, mov_id, pattern)).rowcount
        
        if n > 100:
            print(f'  {pattern[:40]:<42} {n:>8,}')
        total_applied += n
    
    db.commit()
    print(f'  Phase 1 total: {total_applied:,}')
    
    # Phase 2: Country priors
    print('\n=== Phase 2: Country priors ===')
    p2_total = 0
    for country, (legacy, tradition, movement) in COUNTRY_PRIORS.items():
        leg_id = leg_ids.get(legacy)
        trad_id = trad_ids.get(tradition)
        mov_id = mov_ids.get(movement) if movement else None
        
        if not leg_id:
            continue
        
        n = c.execute("""
            UPDATE churches SET legacy_id=?, tradition_id=?, movement_id=?,
            landmark_type=COALESCE(landmark_type, 'church')
            WHERE faith='Christian' AND country=? AND legacy_id IS NULL
        """, (leg_id, trad_id, mov_id, country)).rowcount
        
        if n > 100:
            print(f'  {country}: {legacy:<20} {n:>8,}')
        p2_total += n
    
    db.commit()
    print(f'  Phase 2 total: {p2_total:,}')
    
    # Phase 3: Remaining
    remaining = c.execute("""
        SELECT COUNT(*) FROM churches WHERE faith='Christian' AND country!='US' AND legacy_id IS NULL
    """).fetchone()[0]
    print(f'\n  Remaining unclassified: {remaining:,}')
    
    # Check top remaining countries
    print('\n  Top remaining countries:')
    rows = c.execute("""
        SELECT country, COUNT(*) n FROM churches
        WHERE faith='Christian' AND country!='US' AND legacy_id IS NULL
        GROUP BY country ORDER BY n DESC LIMIT 15
    """).fetchall()
    for r in rows:
        print(f'    {r[0]:<20} {r[1]:>8,}')
    
    db.close()
    print(f'\nTotal classified: {total_applied + p2_total:,}')
    return remaining

if __name__ == '__main__':
    apply_classification()
