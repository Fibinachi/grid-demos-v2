"""
Import Ireland Places of Worship datasets.
Sources:
  1. Dublin City Council — 156 places (GPS, NACE code, addresses)
  2. Dún Laoghaire-Rathdown — 54 places (addresses, websites)
"""
import json, sys, os, re
sys.path.insert(0, r'E:\grid')
from gw_db import connect, log_change

SOURCE = 'ireland_places_of_worship'
FAITH_KEYWORDS = {
    'Catholic': ['CATHOLIC', 'ROMAN CATH', 'OUR LADY', 'ST ', 'SAINT ', 'HOLY CROSS', 'HOLY FAMILY',
                 'HOLY SPIRIT', 'HOLY TRINITY', 'ASSUMPTION', 'IMMACULATE', 'GUARDIAN ANGELS',
                 'MIRACULOUS MEDAL', 'GOOD SHEPHERD', 'ASCENSION', 'ALPHONSUS', 'COLUMBANUS'],
    'Church of Ireland': ['CHURCH OF IRELAND', 'ANGLICAN', 'TULLOW CHURCH', 'RATHMICHAEL',
                          'ST MATTHIAS', 'ST PAUL', 'MONKSTOWN CHURCH'],
    'Methodist': ['METHODIST'],
    'Presbyterian': ['PRESBYTERIAN'],
    'Quaker': ['QUAKER', 'FRIENDS', 'RELIGIOUS SOCIETY'],
    'Evangelical': ['EVANGELICAL', 'EVANGELICAL'],
    'Baptist': ['BAPTIST'],
    'Pentecostal': ['PENTECOSTAL', 'TAMIL AG'],
    'Islam': ['ISLAMIC', 'MOSQUE', 'AHLUL BAYT'],
    'Judaism': ['SYNAGOGUE', 'JEWISH'],
}


def classify(title):
    """Classify by faith from title."""
    t = (title or '').upper().strip()
    for faith, keywords in FAITH_KEYWORDS.items():
        for kw in keywords:
            if kw in t:
                return faith
    # Default to Christian/Catholic for "Church of" style names
    if t.startswith('CHURCH') or t.startswith('ST ') or t.startswith('SAINT'):
        return 'Catholic'
    if t.startswith('CHRIST CHURCH'):
        return 'Church of Ireland'
    return 'Christian'


def main():
    print("=" * 70)
    print("Ireland Places of Worship — Import")
    print("=" * 70)
    
    conn = connect(r'E:\grid\churches.db')
    
    # 1. Dublin City Council (156 records with GPS)
    print("\n[1/3] Dublin City Council Places of Worship...")
    with open(r'E:\grid\dublin_places_of_worship.json') as f:
        dcc_data = json.load(f)
    
    dcc_count = len(dcc_data)
    print(f"  {dcc_count} records loaded")
    
    # 2. Dún Laoghaire-Rathdown (54 records)
    print("\n[2/3] Dún Laoghaire-Rathdown Places of Worship...")
    dlr_data = []
    try:
        dlr_api = 'https://data.smartdublin.ie/api/3/action/datastore_search?resource_id=d888d4c3-3d33-4953-aab2-def51f5d4fb4&limit=100'
        import urllib.request
        with urllib.request.urlopen(dlr_api, timeout=15) as resp:
            dlr_data = json.loads(resp.read())['result']['records']
        print(f"  {len(dlr_data)} records loaded")
    except Exception as e:
        print(f"  Error: {e}")
    
    # Combine all records
    all_records = []
    
    for r in dcc_data:
        all_records.append({
            'source_dataset': 'dcc',
            'title': r.get('Title', ''),
            'description': r.get('Description', ''),
            'address': r.get('Address1', ''),
            'address2': r.get('Address2', ''),
            'lat': r.get('Latitude'),
            'lon': r.get('Longitude'),
            'region': r.get('Region', ''),
            'area': r.get('DccArea', ''),
        })
    
    for r in dlr_data:
        all_records.append({
            'source_dataset': 'dlr',
            'title': r.get('Title', '').strip(),
            'address': r.get('Address1', '').strip(),
            'address2': r.get('Address2', '').strip(),
            'eircode': r.get('EirCode', ''),
            'website': r.get('Website', '').strip(),
            'lat': None,
            'lon': None,
        })
    
    print(f"\n[3/3] Importing {len(all_records)} total records...")
    
    # Check existing Irish records to avoid dupes
    existing = set()
    for row in conn.execute("SELECT name FROM churches WHERE country='Ireland'").fetchall():
        if row[0]:
            existing.add(row[0].strip().upper())
    
    imported = 0
    skipped = 0
    
    for r in all_records:
        title = r['title'].strip()
        if not title:
            skipped += 1
            continue
        
        # Skip if already exists in Ireland
        if title.upper() in existing:
            skipped += 1
            continue
        
        faith = classify(title)
        address = r['address']
        if r.get('address2'):
            address = (address + ', ' + r['address2']).strip(', ')
        
        lat = r.get('lat')
        lon = r.get('lon')
        city = 'Dublin'
        
        # Determine landmark type
        lm_type = 'church'
        if 'mosque' in title.lower() or 'islamic' in title.lower():
            lm_type = 'mosque'
        elif 'synagogue' in title.lower() or 'jewish' in title.lower():
            lm_type = 'synagogue'
        elif 'quaker' in title.lower() or 'friends' in title.lower():
            lm_type = 'meeting_house'
        elif 'cemetery' in title.lower() or 'burial' in title.lower():
            lm_type = 'cemetery'
        
        try:
            conn.execute("""
                INSERT INTO churches (
                    name, faith, denomination, city, country,
                    address, latitude, longitude, landmark_type,
                    source, last_updated
                ) VALUES (?, ?, ?, ?, 'Ireland', ?, ?, ?, ?, ?, date('now'))
            """, (
                title, 'Christian', faith, city,
                address, lat, lon, lm_type,
                SOURCE
            ))
            imported += 1
            existing.add(title.upper())  # prevent re-import in this batch
            
            if imported % 50 == 0:
                conn.commit()
                print(f"    Imported {imported}...")
                
        except Exception as e:
            print(f"    ERROR: {title[:40]}: {e}")
            skipped += 1
    
    conn.commit()
    
    print(f"\n{'='*60}")
    print(f"IMPORT COMPLETE")
    print(f"{'='*60}")
    print(f"  Total records: {len(all_records)}")
    print(f"  Imported:      {imported}")
    print(f"  Skipped:       {skipped}")
    
    # Show samples
    if imported > 0:
        samples = conn.execute(
            "SELECT name, faith, denomination, latitude, longitude FROM churches WHERE source=? ORDER BY id DESC LIMIT 10",
            (SOURCE,)
        ).fetchall()
        print("\n  Samples:")
        for s in samples:
            gps = f"({s[3]},{s[4]})" if s[3] and s[4] else "no GPS"
            print(f"    {s[0][:45]:45s} | {s[1]:10s} | {s[2] or '-':20s} | {gps}")
    
    conn.close()


if __name__ == '__main__':
    main()
