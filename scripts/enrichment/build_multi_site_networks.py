"""
build_multi_site_networks.py — Identify non-denominational multi-site church
networks via name clustering. Flags churches that are campuses of larger networks.

Method:
  1. Normalize names (strip city/address suffixes, standardize keywords)
  2. Group by normalized name → flag networks with 3+ locations
  3. Identify known mega-networks by keyword matching
  4. Create church_network table with network_id, hub church, campus count

Output: church_networks + church_network_members tables
"""
import sqlite3, sys, os, time, re
from collections import defaultdict

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, PROJECT_ROOT)
from gw_db import connect as get_db

def normalize_name(name):
    """Strip location suffixes, standardize for matching."""
    if not name:
        return None
    n = name.strip()
    # Remove known location suffixes
    for suffix in [' - ', ' – ', ' — ']:
        if suffix in n:
            # Check if after suffix looks like a location
            parts = n.split(suffix, 1)
            after = parts[1].strip()
            # If after contains a state code or common campus indicator
            if len(after) <= 30:
                n = parts[0].strip()
    # Standardize common words
    replacements = {
        '&': 'AND',
        '+': 'AND',
    }
    for old, new in replacements.items():
        n = n.replace(old, new)
    # Collapse whitespace
    n = ' '.join(n.split())
    return n.upper()

# Known mega-network keywords
KNOWN_NETWORKS = {
    'LIFE.CHURCH': 'Life.Church Network',
    'LIFECHURCH': 'Life.Church Network',
    'LIFE CHURCH': 'Life.Church Network',
    'NORTH COAST CHURCH': 'North Coast Church',
    'NORTHCOAST CHURCH': 'North Coast Church',
    'SOUTHEAST CHRISTIAN CHURCH': 'Southeast Christian Church',
    'WILLOW CREEK': 'Willow Creek Community Church',
    'ELEVATION CHURCH': 'Elevation Church',
    'GATEWAY CHURCH': 'Gateway Church',
    'SADDLEBACK CHURCH': 'Saddleback Church',
    'CHURCH OF THE HIGHLANDS': 'Church of the Highlands',
    'CROSSROADS CHURCH': 'Crossroads Church',
    'CHRIST FELLOWSHIP': 'Christ Fellowship',
    'NEWSPRING CHURCH': 'NewSpring Church',
    'THE VILLAGE CHURCH': 'The Village Church',
    'PASSION CITY CHURCH': 'Passion City Church',
    'TRANSFORMATION CHURCH': 'Transformation Church',
    'VOUS CHURCH': 'VOUS Church',
}

def elapsed(t0):
    return f'({time.time()-t0:.0f}s)'

print('=' * 70)
print('MULTI-SITE NETWORK IDENTIFICATION')
print('=' * 70)

db = get_db()
c = db.cursor()
t0 = time.time()

# ── STEP 1: Create tables ──
c.execute('DROP TABLE IF EXISTS church_network_members')
c.execute('DROP TABLE IF EXISTS church_networks')
c.execute('''
    CREATE TABLE church_networks (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        network_name TEXT NOT NULL,
        normalized_name TEXT NOT NULL,
        hub_church_id INTEGER,
        hub_name TEXT,
        hub_city TEXT,
        hub_state TEXT,
        campus_count INTEGER DEFAULT 0,
        state_count INTEGER DEFAULT 0,
        total_building_sqft REAL,
        is_known_network INTEGER DEFAULT 0,
        known_network_label TEXT,
        created_at TEXT DEFAULT (datetime('now'))
    )
''')
c.execute('''
    CREATE TABLE church_network_members (
        network_id INTEGER REFERENCES church_networks(id),
        church_id INTEGER REFERENCES churches(id),
        name TEXT,
        city TEXT,
        state TEXT,
        building_sqft REAL,
        is_hub INTEGER DEFAULT 0,
        PRIMARY KEY (network_id, church_id)
    )
''')
db.commit()

# ── STEP 2: Pull US non-denominational / independent churches ──
print('Loading US churches for network analysis...')
c.execute('''
    SELECT id, name, city, state, tradition, faith, latitude, longitude
    FROM churches
    WHERE country = 'US' AND latitude IS NOT NULL
''')
churches = c.fetchall()
print(f'  {len(churches):,} US churches loaded {elapsed(t0)}')

# ── STEP 3: Normalize and group ──
print('Normalizing names and grouping...')
t0 = time.time()
name_groups = defaultdict(list)

# Focus on traditions that tend to be multi-site
multi_site_traditions = {
    'Protestant', 'Evangelical', 'Baptist', 'Pentecostal', 'Charismatic',
    'Non-denominational', 'Independent', 'Community Church', 'Bible Church',
    'Christian', 'Methodist', 'Presbyterian'
}

for row in churches:
    cid, name, city, state, tradition, faith, lat, lon = row
    if not name:
        continue
    norm = normalize_name(name)
    if norm and len(norm) >= 10:  # Skip very short names
        name_groups[norm].append(row)

print(f'  {len(name_groups):,} unique normalized names {elapsed(t0)}')

# ── STEP 4: Identify networks (3+ locations with same normalized name) ──
print('Identifying multi-site networks...')
t0 = time.time()
networks = []
singletons = 0

for norm_name, members in name_groups.items():
    if len(members) >= 3:
        # Check if they're in different cities (not just dupes)
        cities = {m[2] for m in members if m[2]}
        states = {m[3] for m in members if m[3]}
        if len(cities) >= 2:  # At least 2 different cities
            # Find hub (most populous city typically, or first)
            hub = max(members, key=lambda m: len(m[2]) if m[2] else 0)
            networks.append({
                'norm_name': norm_name,
                'members': members,
                'hub': hub,
                'cities': cities,
                'states': states,
            })
    else:
        singletons += 1

# Sort by campus count
networks.sort(key=lambda n: len(n['members']), reverse=True)

print(f'  {len(networks):,} multi-site networks identified')
print(f'  {singletons:,} singleton names')
print(f'  {elapsed(t0)}')

# ── STEP 5: Insert into tables ──
print('Inserting into database...')
t0 = time.time()
batch_members = []
network_count = 0

for net in networks:
    if len(net['members']) < 3:
        continue
    
    norm = net['norm_name']
    original_name = net['members'][0][1]  # Use first member's original name
    
    # Check if this is a known network
    known_label = None
    for keyword, label in KNOWN_NETWORKS.items():
        if keyword in norm:
            known_label = label
            break
    
    hub = net['hub']
    c.execute('''
        INSERT INTO church_networks (network_name, normalized_name, hub_church_id, hub_name, hub_city, hub_state,
                                      campus_count, state_count, is_known_network, known_network_label)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (
        original_name, norm, hub[0], hub[1], hub[2], hub[3],
        len(net['members']), len(net['states']),
        1 if known_label else 0, known_label
    ))
    network_id = c.lastrowid
    network_count += 1
    
    for m in net['members']:
        batch_members.append((
            network_id, m[0], m[1], m[2], m[3],
            1 if m[0] == hub[0] else 0
        ))
    
    if len(batch_members) >= 5000:
        c.executemany('''
            INSERT OR IGNORE INTO church_network_members (network_id, church_id, name, city, state, is_hub)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', batch_members)
        db.commit()
        batch_members = []

# Final batch
if batch_members:
    c.executemany('''
        INSERT OR IGNORE INTO church_network_members (network_id, church_id, name, city, state, is_hub)
        VALUES (?, ?, ?, ?, ?, ?)
    ''', batch_members)
db.commit()

print(f'  {network_count:,} networks inserted')
print(f'  {elapsed(t0)}')

# ── STEP 6: Update building sqft for network members ──
print('Updating building sqft...')
t0 = time.time()
c.execute('''
    UPDATE church_network_members
    SET building_sqft = (SELECT b.building_area_sqft FROM church_building_sqft_us b WHERE b.church_id = church_network_members.church_id)
''')
db.commit()

# Update network total sqft
c.execute('''
    UPDATE church_networks
    SET total_building_sqft = (
        SELECT SUM(m.building_sqft) FROM church_network_members m WHERE m.network_id = church_networks.id
    )
''')
db.commit()
print(f'  {elapsed(t0)}')

# ── STEP 7: Stats ──
print()
print('=' * 70)
print('NETWORK STATISTICS')
print('=' * 70)

c.execute('SELECT COUNT(*), SUM(campus_count), ROUND(AVG(campus_count),1) FROM church_networks')
r = c.fetchone()
print(f'Networks: {r[0]:,}  |  Total campuses: {r[1]:,}  |  Avg campuses/network: {r[2]}')

c.execute('SELECT COUNT(*) FROM church_networks WHERE is_known_network = 1')
print(f'Known mega-networks: {c.fetchone()[0]}')

c.execute('''
    SELECT network_name, campus_count, state_count, 
           ROUND(COALESCE(total_building_sqft,0),0) as total_sqft,
           known_network_label
    FROM church_networks
    ORDER BY campus_count DESC
    LIMIT 15
''')
print('\nTop 15 multi-site networks:')
for row in c.fetchall():
    known = f' [{row[4]}]' if row[4] else ''
    print(f'  {row[0][:40]:40s} {row[1]:4d} campuses  {row[2]:2d} states  {row[3]:>10,.0f} sqft{known}')

total_time = time.time() - t0
print(f'\nPipeline complete in {total_time:.0f}s')
db.close()
