"""
Create all missing movement entries and backfill churches.
Covers the 23 gaps found.
"""
import sqlite3

DB_PATH = r'E:\grid\churches.db'
db = sqlite3.connect(DB_PATH)
db.row_factory = sqlite3.Row
db.execute('PRAGMA busy_timeout=60000')
db.execute('PRAGMA journal_mode=WAL')
c = db.cursor()

# Get parent tradition IDs
trad_ids = {r['name']: r['id'] for r in c.execute('SELECT id, name FROM tradition').fetchall()}
legacy_ids = {r['name']: r['id'] for r in c.execute('SELECT id, name FROM legacy').fetchall()}

def get_max_id():
    return c.execute("SELECT MAX(id) FROM movement").fetchone()[0]

def add_movement(name, tradition, desc=''):
    """Add movement if not exists, return id"""
    existing = c.execute("SELECT id FROM movement WHERE name=?", (name,)).fetchone()
    if existing:
        return existing[0]
    new_id = get_max_id() + 1
    trad_id = trad_ids.get(tradition)
    c.execute("INSERT INTO movement (id, name, tradition_id, description) VALUES (?,?,?,?)",
              (new_id, name, trad_id, desc))
    return new_id

def backfill(pattern, tradition, legacy, movement_id):
    """Backfill churches matching pattern"""
    trad_id = trad_ids.get(tradition)
    leg_id = legacy_ids.get(legacy)
    n = c.execute("""
        UPDATE churches SET movement_id=?, tradition_id=?, legacy_id=?,
        landmark_type=COALESCE(landmark_type, 'church')
        WHERE faith='Christian' AND movement_id IS NULL
        AND name LIKE ?
    """, (movement_id, trad_id, leg_id, pattern)).rowcount
    return n

# ========================
# Define all new movements: name, tradition, pattern, legacy
# ========================
new_movements = [
    # Pentecostal
    ('United Holy Church', 'Pentecostal', '%United Holy Church%', 'Protestant'),
    ('Fire Baptized Holiness', 'Pentecostal', '%Fire Baptized Holiness%', 'Protestant'),
    ('Apostolic Faith', 'Pentecostal', '%Apostolic Faith%', 'Protestant'),
    ('Pentecostal Church of God', 'Pentecostal', '%Pentecostal Church of God%', 'Protestant'),
    ('International Pentecostal Holiness Church', 'Pentecostal', '%International Pentecostal Holiness%', 'Protestant'),
    ('Pentecostal Assemblies of the World', 'Pentecostal', '%Pentecostal Assemblies of the World%', 'Protestant'),
    
    # Baptist
    ('Full Gospel Baptist', 'Baptist', '%Full Gospel Baptist%', 'Protestant'),
    ('American Baptist', 'Baptist', '%American Baptist%', 'Protestant'),
    ('Conservative Baptist', 'Baptist', '%Conservative Baptist%', 'Protestant'),
    ('Landmark Baptist', 'Baptist', '%Landmark Baptist%', 'Protestant'),
    ('Original Free Will Baptist', 'Baptist', '%Original Free Will Baptist%', 'Protestant'),
    
    # Methodist
    ('Wesleyan Methodist', 'Methodist', '%Wesleyan Methodist%', 'Protestant'),
    ('Congregational Methodist', 'Methodist', '%Congregational Methodist%', 'Protestant'),
    ('Christian Methodist Episcopal', 'Methodist', '%Christian Methodist Episcopal%', 'Protestant'),
    
    # Holiness
    ('Pilgrim Holiness', 'Holiness', '%Pilgrim Holiness%', 'Protestant'),
    
    # Presbyterian
    ('Evangelical Presbyterian', 'Presbyterian', '%Evangelical Presbyterian%', 'Protestant'),
    ('Orthodox Presbyterian', 'Presbyterian', '%Orthodox Presbyterian%', 'Protestant'),
    ('Bible Presbyterian', 'Presbyterian', '%Bible Presbyterian%', 'Protestant'),
    
    # Reformed
    ('United Reformed', 'Reformed', '%United Reformed%', 'Protestant'),
    
    # Anglican
    ('Reformed Episcopal', 'Anglican', '%Reformed Episcopal%', 'Anglican'),
    ('Anglican Catholic', 'Anglican', '%Anglican Catholic%', 'Anglican'),
    
    # Evangelical
    ('Evangelical Free Church', 'Evangelical', '%Evangelical Free Church%', 'Protestant'),
    
    # Anabaptist
    ('Brethren in Christ', 'Anabaptist', '%Brethren in Christ%', 'Protestant'),
    
    # Other
    ('Salvation Army', 'Holiness', '%Salvation Army%', 'Protestant'),
    ('Moravian Church', 'Moravian', '%Moravian Church%', 'Moravian'),
    ('Religious Society of Friends', 'Quaker', '%Religious Society of Friends%', 'Protestant'),
    ('RLDS', 'Latter-day Saints', '%RLDS%', 'Restorationist'),
]

print('=== Creating movements & backfilling ===')
total_created = 0
total_backfilled = 0

for name, tradition, pattern, legacy in new_movements:
    # Check if movement already exists
    existing = c.execute("SELECT id FROM movement WHERE name=?", (name,)).fetchone()
    if existing:
        mov_id = existing[0]
        status = 'exists'
    else:
        mov_id = add_movement(name, tradition)
        total_created += 1
        status = 'NEW'
    
    n = backfill(pattern, tradition, legacy, mov_id)
    total_backfilled += n
    if n > 0 or status == 'NEW':
        print(f'  [{status}] {name:<40} backfilled={n:>6,}')

db.commit()

print(f'\n  Created: {total_created} new movements')
print(f'  Backfilled: {total_backfilled:,} churches')

# Verify some key ones
print('\n=== Verification ===')
for name in ['Salvation Army', 'Moravian Church', 'United Reformed', 'Evangelical Free Church']:
    mv = c.execute("SELECT id FROM movement WHERE name=?", (name,)).fetchone()
    if mv:
        n = c.execute("SELECT COUNT(*) FROM churches WHERE movement_id=?", (mv[0],)).fetchone()[0]
        print(f'  {name}: {n:,} churches')

db.close()
print('\nDONE')
