"""
Import OSAGE (Online Spiritual Atlas of the Global East) datasets into GRID.

Sources:
  - OSAGE-China (OSAC v2): 72,887 sites from China's 2004 Economic Census
    DOI: 10.4231/ZN8M-KY34 | CC0 | https://purr.purdue.edu/publications/3210/2
  - OSAGE-Hong Kong: 2,657 sites collected 2022 by Dr. Kim-kwong Chan
    DOI: 10.4231/MTMA-8479 | CC0 | https://purr.purdue.edu/publications/4162/1

OSAGE-Korea (~64K sites) is NOT yet available for download (still being cleaned).

China Type codes:
  1  = Protestantism (churches)
  10 = Protestantism (TSPM/CCC offices, YMCA/YWCA)
  2  = Catholicism (churches)
  20 = Catholicism (Patriotic Association offices)
  3  = Buddhism (temples)
  30 = Buddhism (Buddhist Association offices)
  4  = Daoism (temples)
  5  = Islam (mosques + Islamic Association offices)
  12 = Other (Eastern Orthodox - "Shengniguladongzheng")
  90 = Other (govt Religious Affairs Bureau offices)
  99 = Other (cemeteries, village committees)
"""
import csv
import sys
import os
import math
from collections import Counter, defaultdict

sys.path.insert(0, r'E:\grid')
from gw_db import connect, Provenance, log_change

CHUNK_SIZE = 500
DATA_DIR = r'E:\grid\data\osage'

# ── Type code → (faith, taxonomy_id, landmark_type, is_office) ──
# Taxonomy IDs reference the GRID CFTLM taxonomy
TYPE_MAP = {
    '1':  ('Christian',  2,    'church',         False),  # Protestant church
    '10': ('Christian',  2,    'office',          True),   # TSPM/CCC committee office
    '2':  ('Christian',  14,   'church',          False),  # Catholic church
    '20': ('Christian',  14,   'office',          True),   # Catholic Patriotic Assoc
    '3':  ('Buddhist',   8,    'temple',          False),  # Buddhist temple
    '30': ('Buddhist',   8,    'office',          True),   # Buddhist Association
    '4':  ('Taoist',     10,   'temple',          False),  # Daoist temple
    '5':  ('Islam',      4,    'mosque',          False),  # Islamic site
    '12': ('Christian',  17,   'church',          False),  # Eastern Orthodox
    '90': ('Other',      6,    'office',          True),   # Govt Religious Affairs
    '99': ('Other',      6,    'other',           True),   # Cemetery/village hall
}

# HK Religion_EN → (faith, taxonomy_id, landmark_type)
HK_RELIGION_MAP = {
    'Buddhism':           ('Buddhist',   8,    'temple'),
    'Catholicism':        ('Christian',  14,   'church'),
    'Protestantism':      ('Christian',  2,    'church'),
    'Daoism':             ('Taoist',     10,   'temple'),
    'Islam':              ('Islam',      4,    'mosque'),
    'Hinduism':           ('Hindu',      3,    'temple'),
    'Folk Religion':      ('Other',      6,    'temple'),
    'New Age Movement':   ('Other',      6,    'other'),
    'Sikhism':            ('Sikh',       37,   'gurdwara'),
    'Sikhism/Sant Mat':   ('Sikh',       37,   'gurdwara'),
    'Judaism':            ('Judaism',    24,   'synagogue'),
    'Confucianism':       ('Confucian',  46,   'temple'),
    'Other Religion':     ('Other',      6,    'other'),
    'Christian Fringe':   ('Christian',  17,   'church'),     # JW, Mormon, etc.
    'Orthodox':           ('Christian',  17,   'church'),     # Eastern Orthodox
    "Bahai's Faith":      ('Other',      56,   'other'),      # Baháʼí
    'Jainism':            ('Jain',       55,   'temple'),
    'Zoroastrianism':     ('Other',      6,    'temple'),
    'Falun Gong':         ('Other',      6,    'other'),
    'Humanism':           ('Non-Religious', 41, 'other'),
    'Unification Church': ('Christian',  17,   'church'),
}

# ── Deduplication helpers ──

def load_existing_index(db):
    """Build in-memory index of existing CN/HK churches for dedup."""
    print("Building existing church index...")
    index = {}  # (name_key, country) → [(id, lat, lon, name)]
    
    for country in ['CN', 'HK']:
        cur = db.execute(
            "SELECT id, name, latitude, longitude FROM churches WHERE country=?",
            (country,)
        )
        for row in cur.fetchall():
            key = name_key(row[1])
            if key not in index:
                index[key] = {}
            if country not in index[key]:
                index[key][country] = []
            index[key][country].append((row[0], row[1], row[2], row[3]))
    
    print(f"  {sum(len(v) for v in index.values()):,} unique name keys indexed")
    return index


def name_key(name):
    """Normalize name for dedup matching."""
    if not name:
        return ''
    n = name.lower().strip()
    # Remove punctuation and extra whitespace
    n = ''.join(c for c in n if c.isalnum() or c.isspace())
    return ' '.join(n.split())


def is_duplicate(name, country, lat, lon, index, threshold_km=0.5):
    """Check if a site is already in GRID by name proximity + GPS proximity."""
    nk = name_key(name)
    
    # Exact name match in same country
    if nk in index and country in index[nk]:
        entries = index[nk][country]
        for eid, ename, elat, elon in entries:
            if elat and elon and lat and lon:
                dist = haversine_km(lat, lon, elat, elon)
                if dist < threshold_km:
                    return eid
            else:
                # Name match but no coordinates to compare — treat as dup
                return eid
    
    # Fuzzy: name key without last word (handles "Beijing Islamic Association" vs "Beijing Islamic Assoc")
    words = nk.split()
    if len(words) > 2:
        shorter = ' '.join(words[:-1])
        if shorter in index and country in index[shorter]:
            entries = index[shorter][country]
            for eid, ename, elat, elon in entries:
                if elat and elon and lat and lon:
                    dist = haversine_km(lat, lon, elat, elon)
                    if dist < threshold_km:
                        return eid
    
    return None


def haversine_km(lat1, lon1, lat2, lon2):
    """Haversine distance between two GPS points in km."""
    R = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (math.sin(dlat / 2) ** 2 +
         math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) *
         math.sin(dlon / 2) ** 2)
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def progress_bar(current, total, width=50):
    """Simple ASCII progress bar."""
    if total == 0:
        return ''
    pct = current / total
    filled = int(width * pct)
    bar = '█' * filled + '░' * (width - filled)
    return f'|{bar}| {current:>6,}/{total:>6,} ({pct*100:5.1f}%)'


# ── China Import ──

def import_china(db, index):
    """Import OSAGE-China (OSAC v2) data."""
    csv_path = os.path.join(DATA_DIR, 'china', 'bundle', 'CSVdata', 'data_ReligiousSiteBase.csv')
    
    print("\n" + "=" * 70)
    print("OSAGE-CHINA IMPORT")
    print("=" * 70)
    
    # Read all rows
    print(f"\nLoading {csv_path}...")
    with open(csv_path, encoding='utf-8') as f:
        reader = csv.DictReader(f)
        rows = list(reader)
    print(f"  {len(rows):,} rows loaded")
    
    # Statistics
    type_stats = Counter()
    new_entries = []
    dup_count = 0
    skip_no_coords = 0
    
    print(f"\nProcessing {len(rows):,} entries...\n")
    
    for i, row in enumerate(rows):
        type_code = row['Type'].strip().rstrip('0').rstrip('.')
        # Normalize type to integer string
        try:
            type_int = int(float(row['Type']))
            type_code = str(type_int)
        except ValueError:
            type_code = row['Type'].strip().split('.')[0]
        
        type_info = TYPE_MAP.get(type_code)
        if not type_info:
            print(f"  ⚠ UNKNOWN TYPE CODE: {type_code} | {row.get('Name_Type','')} | {row.get('E_name','')[:50]}")
            type_info = ('Other', 6, 'other', True)
        
        faith, tax_id, ltype, is_office = type_info
        
        # Name-based refinement for Type 5 (Islam): Association/Academy/Service Center → office
        name_en_lower = (row.get('E_name', '') or '').lower()
        if type_code == '5':
            if any(kw in name_en_lower for kw in ['association', 'academy', 'service center', 'affairs bureau']):
                ltype = 'office'
                is_office = True
        
        type_stats[(type_code, faith, ltype, is_office)] += 1
        
        # Extract coordinates (prefer WGS84, fallback to Google)
        lat = row.get('Latitude_W', '').strip()
        lon = row.get('Longitude1', '').strip()
        if not lat or not lon or lat == '0' or lon == '0':
            lat = row.get('Latitude_G', '').strip()
            lon = row.get('Longitude_', '').strip()
        
        if not lat or not lon or lat == '0' or lon == '0':
            skip_no_coords += 1
            if skip_no_coords <= 5:
                print(f"  ⚠ No coords | {row.get('E_name','')[:50]}")
            continue
        
        try:
            lat_f = float(lat)
            lon_f = float(lon)
        except ValueError:
            skip_no_coords += 1
            continue
        
        # Names
        name_en = (row.get('E_name', '') or '').strip()
        name_s = (row.get('S_name', '') or '').strip()  # Simplified Chinese
        name_t = (row.get('T_name', '') or '').strip()  # Traditional Chinese
        name_pinyin = (row.get('P_name', '') or '').strip()
        
        # Use English name if available, otherwise Simplified Chinese, otherwise pinyin
        name = name_en or name_s or name_t or name_pinyin or 'Unknown'
        
        # Address
        addr = (row.get('CH_address', '') or '').strip()
        zipcode = (row.get('Zipcode', '') or '').strip()
        year = (row.get('Year', '') or '').strip()
        
        # Admin hierarchy
        province_en = (row.get('E_province', '') or '').strip()
        prefecture_en = (row.get('E_prefectu', '') or '').strip()
        county_en = (row.get('E_county', '') or '').strip()
        province_s = (row.get('S_province', '') or '').strip()
        
        # City = prefecture or county (most granular admin)
        city = county_en or prefecture_en or province_en or ''
        
        # Dedup
        dup_id = is_duplicate(name, 'CN', lat_f, lon_f, index)
        if dup_id:
            dup_count += 1
            continue
        
        # Build source description
        gd_number = (row.get('GD_number', '') or '').strip().split('.')[0]
        
        new_entries.append({
            'name': name,
            'name_simplified': name_s,
            'name_traditional': name_t,
            'name_pinyin': name_pinyin,
            'address': addr,
            'city': city,
            'state': province_en,
            'zip': zipcode,
            'country': 'CN',
            'latitude': lat_f,
            'longitude': lon_f,
            'faith': faith,
            'taxonomy_id': tax_id,
            'landmark_type': ltype,
            'is_office': is_office,
            'source': 'osage_china',
            'source_detail': f"China 2004 Economic Census, GD#{gd_number}",
            'year': year,
            'type_code': type_code,
        })
        
        # Live output every 100 entries
        if (i + 1) % 100 == 0 or (i + 1) == len(rows):
            bar = progress_bar(i + 1, len(rows))
            print(f"\r  {bar}  new={len(new_entries):,}  dup={dup_count:,}  no_coords={skip_no_coords:,}", end='')
    
    print()  # newline after progress bar
    
    # Summary stats
    print(f"\n{'─' * 50}")
    print(f"Results:")
    print(f"  New entries:    {len(new_entries):>8,}")
    print(f"  Duplicates:     {dup_count:>8,}")
    print(f"  No coordinates: {skip_no_coords:>8,}")
    print(f"  Total input:    {len(rows):>8,}")
    
    print(f"\nBy type code:")
    for (tc, faith, ltype, is_office), cnt in sorted(type_stats.items()):
        office_str = ' [OFFICE]' if is_office else ''
        print(f"  Type {tc:>3s}: {faith:12s} {ltype:12s}{office_str:10s} {cnt:>6,}")
    
    # Preview
    print(f"\nSample entries:")
    for e in new_entries[:10]:
        off = ' 🏢' if e['is_office'] else ''
        print(f"  {e['name'][:45]:45s} | {e['city'][:20]:20s} | {e['state'][:20]:20s} | {e['landmark_type']}{off}")
    
    return new_entries


# ── Hong Kong Import ──

def import_hk(db, index):
    """Import OSAGE-Hong Kong data."""
    csv_path = os.path.join(DATA_DIR, 'hk', 'bundle', 'CSVdata', 'data_ReligiousSite_Base.csv')
    
    print("\n" + "=" * 70)
    print("OSAGE-HONG KONG IMPORT")
    print("=" * 70)
    
    print(f"\nLoading {csv_path}...")
    with open(csv_path, encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        rows = list(reader)
    print(f"  {len(rows):,} rows loaded")
    
    religion_stats = Counter()
    new_entries = []
    dup_count = 0
    skip_no_coords = 0
    unknown_religions = set()
    
    print(f"\nProcessing {len(rows):,} entries...\n")
    
    for i, row in enumerate(rows):
        religion_en = (row.get('Religion_EN', '') or '').strip()
        denomination_en = (row.get('Denomination_EN', '') or '').strip()
        
        rel_info = HK_RELIGION_MAP.get(religion_en)
        if not rel_info:
            unknown_religions.add(religion_en)
            rel_info = ('Other', 6, 'other')
        
        faith, tax_id, ltype = rel_info
        religion_stats[(religion_en, denomination_en)] += 1
        
        # Coordinates
        lat_str = (row.get('Latitude', '') or '').strip()
        lon_str = (row.get('Longitude', '') or '').strip()
        
        if not lat_str or not lon_str:
            skip_no_coords += 1
            continue
        
        try:
            lat = float(lat_str)
            lon = float(lon_str)
        except ValueError:
            skip_no_coords += 1
            continue
        
        # Names
        name_en = (row.get('Name_EN', '') or '').strip()
        name_ch = (row.get('Name_CH', '') or '').strip()
        name = name_en or name_ch or 'Unknown'
        
        # Address
        addr_en = (row.get('Address_EN', '') or '').strip()
        addr_ch = (row.get('Address_CH', '') or '').strip()
        region_en = (row.get('Region_EN', '') or '').strip()
        subregion_en = (row.get('Subregion_EN', '') or '').strip()
        
        # Dedup
        dup_id = is_duplicate(name, 'HK', lat, lon, index)
        if dup_id:
            dup_count += 1
            continue
        
        new_entries.append({
            'name': name,
            'name_chinese': name_ch,
            'address': addr_en or addr_ch,
            'city': subregion_en or region_en,
            'state': 'Hong Kong',
            'country': 'HK',
            'latitude': lat,
            'longitude': lon,
            'faith': faith,
            'taxonomy_id': tax_id,
            'landmark_type': ltype,
            'denomination': denomination_en,
            'is_office': False,
            'source': 'osage_hk',
            'source_detail': f"OSAGE-HK 2022, {religion_en}",
        })
        
        if (i + 1) % 100 == 0 or (i + 1) == len(rows):
            bar = progress_bar(i + 1, len(rows))
            print(f"\r  {bar}  new={len(new_entries):,}  dup={dup_count:,}", end='')
    
    print()
    
    print(f"\n{'─' * 50}")
    print(f"Results:")
    print(f"  New entries:    {len(new_entries):>8,}")
    print(f"  Duplicates:     {dup_count:>8,}")
    print(f"  No coordinates: {skip_no_coords:>8,}")
    print(f"  Total input:    {len(rows):>8,}")
    
    if unknown_religions:
        print(f"\n  Unknown religions: {unknown_religions}")
    
    print(f"\nBy religion:")
    religion_counts = Counter()
    for (rel, den), cnt in religion_stats.items():
        religion_counts[rel] += cnt
    for rel, cnt in religion_counts.most_common():
        print(f"  {rel:25s} {cnt:>6,}")
    
    print(f"\nSample entries:")
    for e in new_entries[:10]:
        print(f"  {e['name'][:45]:45s} | {e['city'][:20]:20s} | {e['faith']:12s} | {e['denomination'][:25]}")
    
    return new_entries


# ── Database Insert ──

def insert_entries(db, entries, source_label):
    """Batch-insert entries into the churches table."""
    if not entries:
        print(f"\n  No {source_label} entries to insert.")
        return 0
    
    print(f"\nInserting {len(entries):,} {source_label} entries into churches...")
    
    with Provenance(db, source=f"osage_{source_label}", action="inserted",
                    fields="name,latitude,longitude,taxonomy_id,faith,landmark_type,source",
                    records_attempted=len(entries)) as prov:
        
        inserted = 0
        for i in range(0, len(entries), CHUNK_SIZE):
            batch = entries[i:i + CHUNK_SIZE]
            for e in batch:
                try:
                    cur = db.execute("SELECT COALESCE(MAX(id), 0) + 1 FROM churches")
                    next_id = cur.fetchone()[0]
                    
                    db.execute("""
                        INSERT INTO churches 
                            (id, name, city, state, country, latitude, longitude,
                             taxonomy_id, faith, landmark_type, source, address, zip,
                             name_transliterated)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        next_id,
                        e['name'],
                        e.get('city', ''),
                        e.get('state', ''),
                        e['country'],
                        e['latitude'],
                        e['longitude'],
                        e['taxonomy_id'],
                        e['faith'],
                        e['landmark_type'],
                        e['source'],
                        e.get('address', ''),
                        e.get('zip', ''),
                        e.get('name_pinyin', ''),
                    ))
                    prov.churches_inserted += 1
                    inserted += 1
                    
                except Exception as ex:
                    print(f"\n  ❌ ERROR: {e['name'][:50]} - {ex}")
            
            db.commit()
            bar = progress_bar(i + len(batch), len(entries), width=40)
            print(f"\r  {bar}  {inserted:,} inserted", end='')
        
        print()
        prov.records_matched = len(entries)
    
    print(f"  ✓ {inserted:,} {source_label} entries inserted")
    return inserted


# ── Main ──

def main():
    print("=" * 70)
    print("OSAGE DATA IMPORT")
    print("Purdue University Center on Religion and the Global East (CRGE)")
    print("CC0 1.0 Universal — Public Domain")
    print("=" * 70)
    
    db = connect()
    
    # Build existing index for dedup
    index = load_existing_index(db)
    
    # Import China
    china_entries = import_china(db, index)
    
    # Import Hong Kong
    hk_entries = import_hk(db, index)
    
    # Confirm before insert
    total = len(china_entries) + len(hk_entries)
    print(f"\n{'=' * 70}")
    print(f"READY TO INSERT: {total:,} total new entries")
    print(f"  China:    {len(china_entries):>8,}")
    print(f"  Hong Kong: {len(hk_entries):>8,}")
    print(f"{'=' * 70}")
    
    if total == 0:
        print("Nothing to insert.")
        db.close()
        return
    
    response = input("\nProceed with insert? [Y/n]: ").strip().lower()
    if response and response != 'y':
        print("Aborted.")
        db.close()
        return
    
    # Insert
    n_china = insert_entries(db, china_entries, 'china')
    n_hk = insert_entries(db, hk_entries, 'hk')
    
    # Final summary
    print(f"\n{'=' * 70}")
    print(f"IMPORT COMPLETE")
    print(f"  China:    {n_china:>8,} inserted")
    print(f"  Hong Kong: {n_hk:>8,} inserted")
    print(f"  Total:    {n_china + n_hk:>8,} inserted")
    print(f"{'=' * 70}")
    
    # Show updated country counts
    for country in ['CN', 'HK']:
        cur = db.execute("SELECT COUNT(*) FROM churches WHERE country=?", (country,))
        cnt = cur.fetchone()[0]
        print(f"  {country} total in GRID: {cnt:,}")
    
    db.close()


if __name__ == '__main__':
    main()
