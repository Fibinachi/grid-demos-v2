"""
Boston Non-Public Schools — Import & Cross-Reference
=====================================================
Fetches the Non-Public Schools dataset from Boston's CKAN portal,
categorizes by religious affiliation, cross-references with our
churches.db, and adds unmatched religious schools as new entries.

API Resource: fae7152d-a053-4158-93b4-12828a2c5203
"""

import json, re, sys, os, time
sys.path.insert(0, r'E:\grid')
import requests
from gw_db import connect

SOURCE = 'boston_nonpublic_schools'
CKAN_URL = ('https://data.boston.gov/api/3/action/datastore_search'
            '?resource_id=fae7152d-a053-4158-93b4-12828a2c5203&limit=100')
CACHE_FILE = r'E:\grid\data\boston_schools.json'


def fetch_schools():
    """Fetch or load cached schools data."""
    if os.path.exists(CACHE_FILE):
        with open(CACHE_FILE) as f:
            return json.load(f)
    resp = requests.get(CKAN_URL).json()
    records = resp['result']['records']
    os.makedirs(os.path.dirname(CACHE_FILE), exist_ok=True)
    with open(CACHE_FILE, 'w') as f:
        json.dump(records, f, indent=2)
    print(f"  Fetched {len(records)} records, cached to {CACHE_FILE}")
    return records


def classify_school(name, school_type):
    """Classify a school by religious affiliation based on name."""
    n = (name or '').upper()
    
    # Only classify private schools as potentially religious
    if school_type not in ('PRI',):
        return None, None  # Not a private school, skip
    
    # Catholic
    if any(w in n for w in ['ST ', 'SAINT', 'CATHEDRAL', 'CATHOLIC',
                            'POPE JOHN PAUL', 'OUR LADY', 'HOLY',
                            'JESUIT', 'MISSION GIRLS']):
        return 'Christian', 'Catholic'
    
    # Seventh-day Adventist
    if 'ADVENTIST' in n or 'SDA' in n:
        return 'Christian', 'Seventh-day Adventist'
    
    # Advent (Christian)
    if n.startswith('THE ADVENT'):
        return 'Christian', 'Episcopal'
    
    # Jewish
    if any(w in n for w in ['BOSTON HEBREW', 'JEWISH', 'NECHAMAH', 'MAIMONIDES',
                            'SHALOM', 'TORAH', 'RASHI', 'HILLEL']):
        return 'Judaism', None
    
    # Islamic
    if any(w in n for w in ['ISLAMIC', 'MUSLIM', 'AL-NOOR', 'AL-QURAN']):
        return 'Islam', None
    
    # Episcopalian
    if any(w in n for w in ['ST. ', 'ST .']):
        # Many "St." schools are Catholic, handled above
        pass
    
    # Generic Christian private school
    if any(w in n for w in ['CHRISTIAN', 'BIBLE', 'KINGDOM', 'TRINITY',
                            'FAITH', 'GRACE', 'CROSS', 'CALVARY',
                            'NEW COVENANT']):
        return 'Christian', None
    
    return None, None  # Secular or unknown


def get_churches_near(conn, lat, lon, radius_km=0.5):
    """Find churches near a given GPS coordinate."""
    if not lat or not lon:
        return []
    try:
        lat_f, lon_f = float(lat), float(lon)
    except (ValueError, TypeError):
        return []
    
    # Approximate: 1 deg lat ~ 111km, 1 deg lon ~ 111*cos(lat) km  
    deg_km = 111.0
    lon_deg_km = deg_km * abs(__import__('math').cos(lat_f * 3.14159 / 180.0)) or deg_km
    
    dlat = radius_km / deg_km
    dlon = radius_km / lon_deg_km
    
    rows = conn.execute("""
        SELECT id, name, faith, latitude, longitude, boston_pid
        FROM churches
        WHERE latitude BETWEEN ? AND ?
          AND longitude BETWEEN ? AND ?
          AND latitude IS NOT NULL AND longitude IS NOT NULL
        ORDER BY ABS(latitude - ?) + ABS(longitude - ?)
        LIMIT 5
    """, (lat_f - dlat, lat_f + dlat, lon_f - dlon, lon_f + dlon,
          lat_f, lon_f)).fetchall()
    return rows


def main():
    print("=" * 70)
    print("Boston Non-Public Schools — Import & Cross-Reference")
    print("=" * 70)
    
    # 1. Fetch schools
    print("\n[1/4] Fetching schools data...")
    schools = fetch_schools()
    
    # Breakdown by type
    type_counts = {}
    for s in schools:
        t = s.get('TYPE', '?')
        type_counts[t] = type_counts.get(t, 0) + 1
    print("  By type:")
    for t, c in sorted(type_counts.items()):
        print(f"    {t}: {c}")
    
    # 2. Classify private schools
    print("\n[2/4] Classifying by religious affiliation...")
    conn = connect(r'E:\grid\churches.db')
    
    religious_schools = []
    secular_schools = []
    
    for s in schools:
        faith, denom = classify_school(s.get('NAME'), s.get('TYPE'))
        s['_faith'] = faith
        s['_denomination'] = denom
        
        if faith:
            religious_schools.append(s)
        else:
            secular_schools.append(s)
    
    print(f"  Religious schools: {len(religious_schools)}")
    print(f"  Secular/unknown:   {len(secular_schools)}")
    
    faith_counts = {}
    for s in religious_schools:
        f = s['_faith']
        faith_counts[f] = faith_counts.get(f, 0) + 1
    for f, c in sorted(faith_counts.items(), key=lambda x: -x[1]):
        print(f"    {f}: {c}")
    
    # 3. Cross-reference with DB
    print("\n[3/4] Cross-referencing with churches.db...")
    
    # Check existing PIDs and Boston sources
    existing_pids = set()
    for row in conn.execute("SELECT boston_pid FROM churches WHERE boston_pid IS NOT NULL").fetchall():
        if row[0]:
            existing_pids.add(row[0])
    
    matched = []
    new_entries = []
    
    # We need to add columns if not exist
    cols = [c[1] for c in conn.execute('PRAGMA table_info(churches)').fetchall()]
    if 'boston_school_schid' not in cols:
        conn.execute("ALTER TABLE churches ADD COLUMN boston_school_schid TEXT")
    if 'boston_school_type' not in cols:
        conn.execute("ALTER TABLE churches ADD COLUMN boston_school_type TEXT")
    conn.commit()
    
    for s in religious_schools:
        faith = s['_faith']
        denom = s['_denomination']
        lat = s.get('POINT_Y')
        lon = s.get('POINT_X')
        name = s.get('NAME', '')
        address = s.get('ADDRESS', '')
        town = s.get('TOWN', '')
        phone = s.get('PHONE', '')
        schid = s.get('SCHID', '')
        school_type = s.get('TYPE', '')
        
        # Try GPS proximity match
        nearby = get_churches_near(conn, lat, lon, radius_km=0.1)  # 100m
        
        if nearby:
            matched.append((s, nearby))
            continue
        
        new_entries.append(s)
    
    print(f"  Matched to existing churches: {len(matched)}")
    print(f"  New entries to add:           {len(new_entries)}")
    
    # Show matched
    if matched:
        print("\n  Matched schools:")
        for s, churches in matched[:15]:
            name = s['NAME']
            faith = s['_faith']
            church_names = '; '.join([f"#{c[0]} {c[1][:30]}" for c in churches[:2]])
            print(f"    {name[:45]:45s} [{faith:10s}] -> {church_names}")
    
    # 4. Add new entries
    print("\n[4/4] Adding new religious schools to DB...")
    
    added = 0
    for s in new_entries:
        faith = s['_faith']
        denom = s['_denomination']
        name = s.get('NAME', '')
        address = s.get('ADDRESS', '')
        town = (s.get('TOWN') or 'BOSTON').title()
        zip_code = s.get('ZIP', '')
        lat = s.get('POINT_Y')
        lon = s.get('POINT_X')
        phone = s.get('PHONE', '')
        schid = s.get('SCHID', '')
        
        try:
            conn.execute("""
                INSERT INTO churches (
                    name, faith, denomination, city, state, zip, address,
                    latitude, longitude, landmark_type, source,
                    boston_school_schid, boston_school_type
                ) VALUES (?, ?, ?, ?, 'MA', ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                name, faith, denom, town, zip_code, address,
                lat, lon, 'school', SOURCE,
                schid, school_type
            ))
            
            # Store phone as contact value if available
            if phone:
                try:
                    conn.execute(
                        "INSERT INTO church_contact_values (church_id, contact_type, value, confidence, source) VALUES (?, 'phone', ?, 0.9, ?)",
                        (conn.execute("SELECT last_insert_rowid()").fetchone()[0], phone, SOURCE)
                    )
                except:
                    pass
            
            added += 1
            if added % 25 == 0:
                conn.commit()
                print(f"    Added {added}...")
        
        except Exception as e:
            print(f"    ERROR adding {name}: {e}")
    
    conn.commit()
    
    # Summary
    print(f"\n{'='*70}")
    print(f"SUMMARY")
    print(f"{'='*70}")
    print(f"  Total schools:           {len(schools)}")
    print(f"  Religious/private:       {len(religious_schools)}")
    print(f"  Matched to DB:           {len(matched)}")
    print(f"  New entries added:       {added}")
    
    # Show new entries
    if new_entries:
        print(f"\n  New schools added:")
        faith_groups = {}
        for s in new_entries:
            f = s['_faith'] or 'Unknown'
            faith_groups.setdefault(f, []).append(s['NAME'])
        for f, names in sorted(faith_groups.items()):
            print(f"    [{f}]")
            for n in names:
                print(f"      {n}")
    
    conn.close()


if __name__ == '__main__':
    main()
