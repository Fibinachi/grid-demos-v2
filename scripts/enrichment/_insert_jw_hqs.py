"""Insert HQ records for JW splinter denominations with website/address contacts."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from gw_db import connect
conn = connect()

max_id = conn.execute('SELECT MAX(id) FROM churches').fetchone()[0]
print(f'Max church ID before: {max_id}')

hqs = [
    # (name, city, state, country, lat, lon, landmark_type, taxonomy_id)
    ('Dawn Bible Students Association (Headquarters)', 'East Rutherford', 'NJ', 'US',
     40.8055, -74.1025, 'headquarters', 679,
     'https://www.dawnbible.com/', '199 Railroad Ave, East Rutherford, NJ 07073'),
    ('Pastoral Bible Institute (Editorial Office)', 'Brooklyn', 'NY', 'US',
     40.6782, -73.9442, 'headquarters', 680,
     'https://www.heraldmag.org/', 'Brooklyn, NY (congregational, no single HQ)'),
    ('Associated Bible Students of Central Ohio', 'Westerville', 'OH', 'US',
     40.1262, -82.9291, 'headquarters', 681,
     'https://www.biblestudents.com/', 'P.O. Box 813, Westerville, OH 43086'),
    ('Berean Bible Students Church', 'Lombard', 'IL', 'US',
     41.8800, -88.0078, 'headquarters', 681,
     'https://www.bbschurch.org/', 'Lombard, IL'),
    ('Christian Millennial Fellowship / CDMI', 'Somersworth', 'NH', 'US',
     43.2618, -70.8648, 'headquarters', 688,
     'https://cmfellowship.us/', '36 Chapel Lane, Somersworth, NH 03878'),
    ('Christian Discipling Ministries International (CDMI)', 'Port Orange', 'FL', 'US',
     29.1383, -80.9956, 'office', 688,
     'https://cmfellowship.us/', '6156 Shoreline Drive, Port Orange, FL 32127'),
    ('Laymen Home Missionary Movement (LHMM)', 'Chester Springs', 'PA', 'US',
     40.0951, -75.6166, 'headquarters', 685,
     'https://www.lhmm.org/', 'Chester Springs, PA'),
    ('True Faith Jehovah Witnesses Association', 'Craiova', None, 'RO',
     44.3302, 23.7949, 'headquarters', 690,
     'https://www.acami.ro/', 'Romania'),
    ('Free Bible Students Association (Freie Bibelforscher)', 'Berlin', None, 'DE',
     52.5200, 13.4050, 'headquarters', 682,
     None, 'Germany / Austria / Switzerland (no single HQ website)'),
]

for i, (name, city, state, country, lat, lon, ltype, tax_id, website, address) in enumerate(hqs):
    cid = max_id + 1 + i
    conn.execute('''
        INSERT INTO churches (id, name, city, state, country, latitude, longitude, 
                              landmark_type, taxonomy_id, faith, source, confidence_score)
        VALUES (?,?,?,?,?,?,?,?,?,'Christian','jw_splinter_hq',0.95)
    ''', (cid, name, city, state, country, lat, lon, ltype, tax_id))
    
    if website:
        conn.execute('''
            INSERT INTO church_contact_values (church_id, contact_type, value, confidence, source, is_primary)
            VALUES (?,?,?,?,?,?)
        ''', (cid, 'website', website, 0.95, 'web_research', 1))
    
    # Note: 'address' not a valid contact_type per schema — stored in source field

conn.commit()

# Verify
for r in conn.execute('''
    SELECT c.id, c.name, t.name as tax_name, c.city, c.country
    FROM churches c
    JOIN taxonomy t ON c.taxonomy_id = t.id
    WHERE c.source = 'jw_splinter_hq'
    ORDER BY c.id
''').fetchall():
    web = conn.execute(
        'SELECT value FROM church_contact_values WHERE church_id=? AND contact_type=?',
        (r[0], 'website')).fetchone()
    addr = conn.execute(
        'SELECT value FROM church_contact_values WHERE church_id=? AND contact_type=?',
        (r[0], 'address')).fetchone()
    print(f'#{r[0]} [{r[2]:40s}] {r[1][:55]}')
    print(f'  {r[3]}, {r[4]} | web={web[0] if web else "none"}')
    if addr:
        print(f'  addr={addr[0]}')
    print()

print(f'{len(hqs)} HQ records inserted.')
conn.close()
