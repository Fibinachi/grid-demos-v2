"""
Classify unclassified US Christian churches using legacy, source, and name patterns.
Fast — no API calls needed.
"""
import sqlite3, re
from collections import defaultdict

DB = r"E:\grid\churches.db"

# ── Legacy → Tradition mapping ──
LEGACY_TO_TRADITION = {
    'Restorationist': 'Restorationist',
    'Presbyterian': 'Presbyterian',
    'Pentecostal': 'Pentecostal',
    'Evangelical': 'Evangelical',
    'Lutheran': 'Lutheran',
    'Orthodox': 'Orthodox',
    'Methodist': 'Methodist',
    'Anglican': 'Anglican',
    'Episcopal': 'Episcopal',
    'Baptist': 'Baptist',
    'Catholic': 'Catholic (Roman)',
    'Adventist': 'Adventist',
    'Holiness': 'Holiness',
    'Congregational': 'Congregational',
    'Mennonite': 'Mennonite',
    'Quaker': 'Quaker',
    'Reformed': 'Reformed',
    'Anabaptist': 'Anabaptist',
    'Moravian': 'Moravian',
    'Brethren': 'Brethren',
    'Amish': 'Amish',
}

# ── Source → Tradition mapping for known denominational directories ──
SOURCE_TO_TRADITION = {
    'cog_anderson_api': 'Church of God (Anderson)',
    'efca_api': 'Evangelical Free Church',
    'bma_directory': 'Baptist Missionary Association',
    'pb_directory_import': 'Primitive Baptist',
    'churchunion_scraper': None,  # use legacy
    'churchunion_scraper+holy_sites_enrichment': None,
}

# ── Name pattern → Tradition ──
NAME_PATTERNS = [
    (r'\bassembly of god\b', 'Assemblies of God'),
    (r'\bchurch of god\b(?!.*anderson)', 'Church of God'),
    (r'\bchurch of god.*anderson\b', 'Church of God (Anderson)'),
    (r'\bchurch of god in christ\b', 'Church of God in Christ'),
    (r'\bchurch of christ\b', 'Churches of Christ'),
    (r'\bunited methodist\b', 'United Methodist'),
    (r'\bfree methodist\b', 'Free Methodist'),
    (r'\bwesleyan\b', 'Wesleyan'),
    (r'\bpresbyterian\b', 'Presbyterian'),
    (r'\bepiscopal\b', 'Episcopal'),
    (r'\bassemblies of god\b', 'Assemblies of God'),
    (r'\bfull gospel\b', 'Full Gospel'),
    (r'\bfoursquare\b', 'Foursquare'),
    (r'\bvineyard\b', 'Vineyard'),
    (r'\bcalvary chapel\b', 'Calvary Chapel'),
    (r'\bchristian & missionary alliance\b', 'Christian and Missionary Alliance'),
    (r'\bchristian and missionary alliance\b', 'Christian and Missionary Alliance'),
    (r'\bcma\b', 'Christian and Missionary Alliance'),
    (r'\bnazarene\b', 'Nazarene'),
    (r'\bsalvation army\b', 'Salvation Army'),
    (r'\bseventh.day adventist\b', 'Seventh-day Adventist'),
    (r'\bsda\b', 'Seventh-day Adventist'),
    (r'\badventist\b', 'Adventist'),
    (r'\bmennonite\b', 'Mennonite'),
    (r'\bamish\b', 'Amish'),
    (r'\bquaker\b', 'Quaker'),
    (r'\bfriends church\b', 'Quaker'),
    (r'\bfriends meeting\b', 'Quaker'),
    (r'\bunited church of christ\b', 'United Church of Christ'),
    (r'\bcongregational\b', 'Congregational'),
    (r'\breformed church\b', 'Reformed'),
    (r'\bchristian reformed\b', 'Christian Reformed'),
    (r'\bunited reformed\b', 'United Reformed'),
    (r'\blutheran\b', 'Lutheran'),
    (r'\bbaptist\b', 'Baptist'),
    (r'\bmethodist\b', 'Methodist'),
    (r'\bpentecostal\b', 'Pentecostal'),
    (r'\bapostolic\b', 'Apostolic'),
    (r'\bholiness\b', 'Holiness'),
    (r'\bjehovah.{0,5}witness', "Jehovah's Witnesses"),
    (r'\bmormon\b', 'Latter-day Saints'),
    (r'\blds\b', 'Latter-day Saints'),
    (r'\blatter.day saint', 'Latter-day Saints'),
    (r'\bcatholic\b', 'Catholic (Roman)'),
    (r'\beastern orthodox\b', 'Eastern Orthodox'),
    (r'\bgreek orthodox\b', 'Greek Orthodox'),
    (r'\brussian orthodox\b', 'Russian Orthodox'),
    (r'\borthodox\b', 'Eastern Orthodox'),
    (r'\bnondenominational\b', 'Non-Denominational'),
    (r'\bnon.denominational\b', 'Non-Denominational'),
    (r'\bcommunity church\b', 'Non-Denominational'),
    (r'\bbible church\b', 'Non-Denominational'),
    (r'\bfellowship church\b', 'Non-Denominational'),
    (r'\bchapel\b', 'Non-Denominational'),
    (r'\bchristian church\b', 'Christian Church'),
    (r'\bdisciples of christ\b', 'Christian Church (Disciples of Christ)'),
    (r'\bevangelical free\b', 'Evangelical Free Church'),
    (r'\bevangelical covenant\b', 'Evangelical Covenant'),
    (r'\bevangelical lutheran\b', 'Evangelical Lutheran'),
    (r'\bprimitive baptist\b', 'Primitive Baptist'),
    (r'\bsouthern baptist\b', 'Southern Baptist'),
    (r'\bmissionary baptist\b', 'Missionary Baptist'),
    (r'\bfree will baptist\b', 'Free Will Baptist'),
    (r'\bgeneral baptist\b', 'General Baptist'),
    (r'\bindependent baptist\b', 'Independent Baptist'),
    (r'\breformed baptist\b', 'Reformed Baptist'),
    (r'\bregular baptist\b', 'Regular Baptist'),
]

def classify_name(name):
    """Return tradition from name patterns, or None."""
    if not name:
        return None
    name_lower = name.lower()
    for pattern, tradition in NAME_PATTERNS:
        if re.search(pattern, name_lower):
            return tradition
    return None

def main():
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    
    # ── US Christians with no tradition ──
    c.execute("""
        SELECT id, name, legacy, source, landmark_type
        FROM churches 
        WHERE country='US' AND faith='Christian' 
          AND (tradition IS NULL OR tradition = '')
    """)
    records = c.fetchall()
    print(f"US Christians to classify: {len(records):,}")
    
    classified = 0
    by_method = defaultdict(int)
    BATCH = 1000
    
    for i, r in enumerate(records):
        tradition = None
        
        # Priority 1: Source-specific mapping
        src = r['source'] or ''
        if src in SOURCE_TO_TRADITION:
            tradition = SOURCE_TO_TRADITION[src]
            if tradition:
                by_method['source'] += 1
        
        # Priority 2: Legacy mapping
        if not tradition:
            legacy = r['legacy'] or ''
            if legacy in LEGACY_TO_TRADITION:
                tradition = LEGACY_TO_TRADITION[legacy]
                by_method['legacy'] += 1
        
        # Priority 3: Name pattern matching
        if not tradition:
            tradition = classify_name(r['name'])
            if tradition:
                by_method['name'] += 1
        
        # Priority 4: Landmark type fallback
        if not tradition and r['landmark_type']:
            lt = r['landmark_type']
            if lt in ('church', 'chapel', 'cathedral', 'basilica', 'abbey', 'parish'):
                tradition = 'Christian (general)'
                by_method['landmark_type'] += 1
        
        if tradition:
            c.execute("UPDATE churches SET tradition=? WHERE id=?", (tradition, r['id']))
            classified += 1
        else:
            by_method['unclassified'] += 1
        
        if i % BATCH == 0 and i > 0:
            conn.commit()
            print(f"  {i:,}/{len(records):,} | classified: {classified:,}")
    
    conn.commit()
    
    print(f"\n{'='*50}")
    print(f"US Christian Classification Complete")
    print(f"{'='*50}")
    print(f"  Total:           {len(records):,}")
    print(f"  Classified:      {classified:,}")
    for method, count in sorted(by_method.items()):
        print(f"    via {method:20} {count:>8,}")
    
    # Remaining
    c.execute("""
        SELECT COUNT(*) FROM churches 
        WHERE country='US' AND faith='Christian' 
          AND (tradition IS NULL OR tradition = '')
    """)
    remaining = c.fetchone()[0]
    print(f"  Remaining:       {remaining:,}")
    
    conn.close()

if __name__ == "__main__":
    main()
