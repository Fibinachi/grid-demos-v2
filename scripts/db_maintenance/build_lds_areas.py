"""
Build LDS Area Office hierarchy from Wikipedia data.

Strategy:
- 5 existing Presiding Bishop Offices (PBOs) with defined state/country territories
- 16 international Area Offices scraped from Wikipedia with country coverage
- 231 temples linked to Area Office by territorial authority (not pure spatial)
- 1 GPS-less temple stays on HQ directly

Hierarchy: HQ -> Area Office (21) -> Temple -> Stake House -> Meetinghouse
Note: "Temple District" level exists between Area Office and Temple
      in the real organization but is absent from this dataset.

Area data: https://en.wikipedia.org/wiki/Area_(LDS_Church)

Usage:
    python scripts/db_maintenance/build_lds_areas.py
    python scripts/db_maintenance/build_lds_areas.py --dry-run
"""
import sqlite3
import sys
import math
import time
from datetime import datetime, timezone

DB_PATH = r'E:\grid\churches.db'
DRY_RUN = '--dry-run' in sys.argv

# Existing PBO IDs
EXISTING_PBO_IDS = [41356, 41357, 41358, 41359, 41360]

# PBO territorial authority — which states/countries each PBO covers
PBO_TERRITORIES = {
    41356: {'name': 'PBO - Canada', 'states': [], 'countries': ['CA']},
    41357: {'name': 'PBO - Southwest',
            'states': ['AZ', 'NV', 'NM', 'OK', 'TX'],
            'countries': ['MX']},
    41358: {'name': 'PBO - West',
            'states': ['AK', 'CA', 'HI', 'OR', 'WA'],
            'countries': []},
    41359: {'name': 'PBO - Central/Northeast',
            'states': ['CO', 'ID', 'IL', 'IA', 'KS', 'MN', 'MO', 'MT',
                       'NE', 'ND', 'SD', 'WI', 'WY',
                       'CT', 'DE', 'IN', 'ME', 'MD', 'MA', 'MI',
                       'NH', 'NJ', 'NY', 'OH', 'PA', 'RI', 'VT',
                       'VA', 'WV', 'DC'],
            'countries': []},
    41360: {'name': 'PBO - South',
            'states': ['AL', 'AR', 'FL', 'GA', 'KY', 'LA', 'MS',
                       'NC', 'SC', 'TN'],
            'countries': []},
}

# International Area Office country coverage (from Wikipedia)
INTL_AO_COVERAGE = {
    'Africa Central': ['KE', 'CD', 'CG', 'ET', 'TZ', 'UG', 'RW', 'BI',
                       'SO', 'SS', 'DJ', 'ER', 'CF', 'GQ', 'GA', 'CM', 'TD'],
    'Africa South': ['ZA', 'AO', 'BW', 'LS', 'MW', 'MZ', 'NA', 'ZM', 'ZW',
                     'MG', 'MU', 'SC', 'KM', 'ST', 'SZ'],
    'Africa West': ['GH', 'NG', 'CI', 'SN', 'SL', 'LR', 'BJ', 'BF',
                    'GM', 'GN', 'ML', 'MR', 'NE', 'TG', 'EH'],
    'Asia': ['HK', 'CN', 'TW', 'IN', 'TH', 'VN', 'KH', 'ID', 'SG',
             'MY', 'BN', 'LK', 'NP', 'BD', 'PK', 'MM', 'LA', 'MN', 'BT'],
    'Asia North': ['JP', 'KR', 'GU', 'MP', 'PW'],
    'Brazil': ['BR'],
    'Canada': ['CA'],
    'Caribbean': ['DO', 'HT', 'PR', 'CU', 'JM', 'BB', 'TT', 'BS', 'GY',
                  'SR', 'GD', 'DM', 'AG', 'LC', 'VC', 'KN', 'AW', 'CW',
                  'BQ', 'SX', 'MF', 'GP', 'MQ', 'GF', 'KY', 'VG', 'VI',
                  'TC', 'AI', 'MS', 'BM'],
    'Central America': ['GT', 'SV', 'HN', 'NI', 'CR', 'PA', 'BZ'],
    'Europe Central': ['DE', 'FR', 'IT', 'ES', 'CH', 'AT', 'BE', 'NL',
                       'PT', 'GR', 'HR', 'BA', 'SI', 'HU', 'CZ', 'SK',
                       'PL', 'RO', 'BG', 'AL', 'MK', 'RS', 'ME', 'XK',
                       'LU', 'LI', 'MC', 'SM', 'VA', 'AD', 'MT', 'CY'],
    'Europe North': ['GB', 'IE', 'DK', 'NO', 'SE', 'FI', 'IS', 'FO',
                     'GL', 'EE', 'LV', 'LT', 'CV', 'UA', 'MD', 'BY'],
    'Mexico': ['MX'],
    'Pacific': ['NZ', 'AU', 'FJ', 'PG', 'SB', 'VU', 'NC', 'PF', 'WS',
                'TO', 'AS', 'CK', 'NU', 'TK', 'TV', 'KI', 'MH', 'FM',
                'NR', 'WF'],
    'Philippines': ['PH'],
    'South America Northwest': ['PE', 'CO', 'EC', 'BO'],
    'South America South': ['AR', 'CL', 'UY', 'PY'],
}

# Area Office definitions
AREA_OFFICES = [
    # Existing PBOs
    {'id': 41356, 'name': 'PBO - Canada Office',
     'city': 'Richmond Hill', 'state': 'ON', 'country': 'CA',
     'lat': 43.8498, 'lon': -79.3997},
    {'id': 41357, 'name': 'PBO - Southwest Office',
     'city': 'Mesa', 'state': 'AZ', 'country': 'US',
     'lat': 33.4107, 'lon': -111.8874},
    {'id': 41358, 'name': 'PBO - West Office',
     'city': 'Sacramento', 'state': 'CA', 'country': 'US',
     'lat': 38.5304, 'lon': -121.3957},
    {'id': 41359, 'name': 'PBO - Central/Northeast Office',
     'city': 'Apple Valley', 'state': 'MN', 'country': 'US',
     'lat': 44.7388, 'lon': -93.2047},
    {'id': 41360, 'name': 'PBO - South Office',
     'city': 'Round Rock', 'state': 'TX', 'country': 'US',
     'lat': 30.4983, 'lon': -97.6104},

    # International Area Offices
    {'id': None, 'name': 'Africa Central Area Office',
     'city': 'Nairobi', 'country': 'KE', 'lat': -1.2921, 'lon': 36.8219},
    {'id': None, 'name': 'Africa South Area Office',
     'city': 'Johannesburg', 'country': 'ZA', 'lat': -26.2041, 'lon': 28.0473},
    {'id': None, 'name': 'Africa West Area Office',
     'city': 'Accra', 'country': 'GH', 'lat': 5.6037, 'lon': -0.1870},
    {'id': None, 'name': 'Asia Area Office',
     'city': 'Hong Kong', 'country': 'HK', 'lat': 22.3193, 'lon': 114.1694},
    {'id': None, 'name': 'Asia North Area Office',
     'city': 'Tokyo', 'country': 'JP', 'lat': 35.6762, 'lon': 139.6503},
    {'id': None, 'name': 'Brazil Area Office',
     'city': 'Sao Paulo', 'country': 'BR', 'lat': -23.5505, 'lon': -46.6333},
    {'id': None, 'name': 'Canada Area Office',
     'city': 'Calgary', 'country': 'CA', 'lat': 51.0447, 'lon': -114.0719},
    {'id': None, 'name': 'Caribbean Area Office',
     'city': 'Santo Domingo', 'country': 'DO', 'lat': 18.4861, 'lon': -69.9312},
    {'id': None, 'name': 'Central America Area Office',
     'city': 'Guatemala City', 'country': 'GT', 'lat': 14.6349, 'lon': -90.5069},
    {'id': None, 'name': 'Europe Central Area Office',
     'city': 'Frankfurt', 'country': 'DE', 'lat': 50.1109, 'lon': 8.6821},
    {'id': None, 'name': 'Europe North Area Office',
     'city': 'London', 'country': 'GB', 'lat': 51.5074, 'lon': -0.1278},
    {'id': None, 'name': 'Mexico Area Office',
     'city': 'Mexico City', 'country': 'MX', 'lat': 19.4326, 'lon': -99.1332},
    {'id': None, 'name': 'Pacific Area Office',
     'city': 'Auckland', 'country': 'NZ', 'lat': -36.8485, 'lon': 174.7633},
    {'id': None, 'name': 'Philippines Area Office',
     'city': 'Quezon City', 'country': 'PH', 'lat': 14.6760, 'lon': 121.0437},
    {'id': None, 'name': 'South America Northwest Area Office',
     'city': 'Lima', 'country': 'PE', 'lat': -12.0464, 'lon': -77.0428},
    {'id': None, 'name': 'South America South Area Office',
     'city': 'Buenos Aires', 'country': 'AR', 'lat': -34.6037, 'lon': -58.3816},
]


def find_pbo_for_temple(temple):
    """Find PBO by territorial authority (state for US, country for non-US)."""
    t_state = (temple.get('state') or '').strip()
    t_country = (temple.get('country') or '').strip()

    for pbo_id, territory in PBO_TERRITORIES.items():
        if t_country == 'US' and t_state:
            if t_state in territory['states']:
                return pbo_id, 'PBO'
        if t_country in territory['countries']:
            return pbo_id, 'PBO'
    return None, None


def find_intl_ao_for_temple(temple, ao_lookup):
    """Find international Area Office by country coverage."""
    t_country = (temple.get('country') or '').strip()
    for name, countries in INTL_AO_COVERAGE.items():
        if t_country in countries:
            return name
    return None


def haversine_km(lat1, lon1, lat2, lon2):
    if None in (lat1, lon1, lat2, lon2):
        return float('inf')
    R = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat / 2)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2)**2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def main():
    print(f'{"="*60}')
    print(f'Building LDS Area Office hierarchy ({"DRY RUN" if DRY_RUN else "LIVE"})')
    print(f'{"="*60}')
    t0 = time.time()

    conn = sqlite3.connect(DB_PATH)
    conn.execute('PRAGMA journal_mode=WAL')
    conn.row_factory = sqlite3.Row
    c = conn.cursor()

    hq_id = 40546

    # Step 1: Update PBO notes (accurate description, NOT reclassifying)
    print('\n[1/6] Updating PBO notes...')
    pbo_note = ('Presiding Bishop Office - regional administrative hub for '
                'Church properties, temple facilities, and finances.')
    for pid in EXISTING_PBO_IDS:
        c.execute("UPDATE lds_hierarchy SET notes = ? WHERE id = ?", (pbo_note, pid))
    if not DRY_RUN:
        conn.commit()
    print(f'  {len(EXISTING_PBO_IDS)} PBO notes updated')

    # Step 2: Get current max ID
    c.execute('SELECT COALESCE(MAX(id), 0) FROM lds_hierarchy')
    next_id = c.fetchone()[0] + 1

    # Step 3: Get existing PBO data, prepare full AO list
    print('\n[2/6] Preparing Area Office list...')
    existing_ids = set(EXISTING_PBO_IDS)
    new_aos = [ao for ao in AREA_OFFICES if ao['id'] is None]

    all_aos = []
    for ao in AREA_OFFICES:
        if ao['id'] is not None:
            c.execute("SELECT id, name, lat, lon FROM lds_hierarchy WHERE id = ?", (ao['id'],))
            row = c.fetchone()
            if row:
                all_aos.append({'id': row['id'], 'name': row['name'],
                                'lat': row['lat'], 'lon': row['lon'],
                                'city': ao['city'], 'country': ao['country'],
                                'existing': True})
        else:
            all_aos.append({'id': next_id, 'name': ao['name'],
                            'lat': ao['lat'], 'lon': ao['lon'],
                            'city': ao['city'], 'country': ao['country'],
                            'existing': False})
            next_id += 1

    n_existing = sum(1 for a in all_aos if a['existing'])
    n_new = sum(1 for a in all_aos if not a['existing'])
    print(f'  {n_existing} existing PBOs + {n_new} new intl Area Offices = {len(all_aos)} total')

    # Step 4: Insert new international Area Offices
    print('\n[3/6] Inserting new Area Office records...')
    inserted = 0
    for ao in new_aos:
        note = (f'Area Office - {ao["name"]} ({ao["city"]}, {ao["country"]}). '
                f'Sourced from Wikipedia area list.')
        if DRY_RUN:
            print(f'  Would insert: {ao["name"]} ({ao["city"]}, {ao["country"]})')
            inserted += 1
        else:
            c.execute("""
                INSERT INTO lds_hierarchy
                    (parent_id, parent_lds_type, relationship, name,
                     lds_type, city, state, country, lat, lon, notes)
                VALUES (?, ?, ?, ?, 'area_office', ?, ?, ?, ?, ?, ?)
            """, (hq_id, 'hq', 'administered_by', ao['name'],
                  ao['city'], None, ao['country'], ao['lat'], ao['lon'], note))
            inserted += 1

    if not DRY_RUN:
        conn.commit()
    print(f'  {inserted} Area Offices inserted')

    # Rebuild all_aos with real IDs if live
    if not DRY_RUN:
        c.execute("SELECT id, name, city, state, country, lat, lon FROM lds_hierarchy WHERE lds_type = 'area_office'")
        all_aos = []
        for row in c.fetchall():
            all_aos.append({'id': row['id'], 'name': row['name'],
                            'lat': row['lat'], 'lon': row['lon'],
                            'city': row['city'], 'country': row['country']})

    print(f'  {len(all_aos)} Area Offices ready for temple assignment')

    # Build AO lookup by name for ID resolution
    ao_by_name = {}
    for ao in all_aos:
        name_key = ao['name'].replace('PBO - ', '').replace(' Area Office', '')
        ao_by_name[name_key] = ao['id']

    # Step 5: Re-link temples by territorial authority
    print('\n[4/6] Re-linking temples by territorial authority...')
    print('  Priority: PBO territory -> intl AO country coverage -> haversine fallback')
    c.execute("SELECT id, name, city, state, country, lat, lon FROM lds_hierarchy WHERE lds_type = 'temple'")
    temples = [dict(row) for row in c.fetchall()]
    print(f'  {len(temples)} temples')

    assigned = 0
    hq_stay = 0
    pbo_by_territory = 0
    intl_by_coverage = 0
    ao_counts = {}
    ao_info = {}
    method_counts = {'PBO territory': 0, 'Intl coverage': 0, 'Haversine': 0, 'No GPS': 0}

    for temple in temples:
        if temple['lat'] is None or temple['lon'] is None:
            hq_stay += 1
            method_counts['No GPS'] += 1
            if not DRY_RUN:
                c.execute("""
                    UPDATE lds_hierarchy SET parent_id=?, parent_lds_type='hq', relationship='administered_by'
                    WHERE id=? AND (parent_id IS NULL OR parent_id!=?)
                """, (hq_id, temple['id'], hq_id))
            continue

        # Method 1: PBO territorial authority
        pbo_id, _ = find_pbo_for_temple(temple)
        if pbo_id is not None:
            if not DRY_RUN:
                c.execute("""
                    UPDATE lds_hierarchy SET parent_id=?, parent_lds_type='area_office', relationship='administered_by'
                    WHERE id=?
                """, (pbo_id, temple['id']))
            assigned += 1
            pbo_by_territory += 1
            method_counts['PBO territory'] += 1
            # Get name for display
            c.execute("SELECT name FROM lds_hierarchy WHERE id = ?", (pbo_id,))
            ao_name = (c.fetchone() or ['Unknown'])[0][:45]
            ao_counts[ao_name] = ao_counts.get(ao_name, 0) + 1
            continue

        # Method 2: International AO country coverage
        intl_name = find_intl_ao_for_temple(temple, ao_by_name)
        if intl_name:
            # Map to actual AO ID
            for name_key, aid in ao_by_name.items():
                if intl_name in name_key or name_key in intl_name:
                    if not DRY_RUN:
                        c.execute("""
                            UPDATE lds_hierarchy SET parent_id=?, parent_lds_type='area_office', relationship='administered_by'
                            WHERE id=?
                        """, (aid, temple['id']))
                    assigned += 1
                    intl_by_coverage += 1
                    method_counts['Intl coverage'] += 1
                    # Get name
                    c.execute("SELECT name FROM lds_hierarchy WHERE id = ?", (aid,))
                    ao_name = (c.fetchone() or ['Unknown'])[0][:45]
                    ao_counts[ao_name] = ao_counts.get(ao_name, 0) + 1
                    break
            continue

        # Method 3: Haversine fallback (nearest AO by distance)
        best_idx, best_dist = None, float('inf')
        for i, ao in enumerate(all_aos):
            d = haversine_km(temple['lat'], temple['lon'], ao['lat'], ao['lon'])
            if d < best_dist:
                best_dist = d
                best_idx = i

        if best_idx is not None:
            ao = all_aos[best_idx]
            if not DRY_RUN:
                c.execute("""
                    UPDATE lds_hierarchy SET parent_id=?, parent_lds_type='area_office', relationship='administered_by'
                    WHERE id=?
                """, (ao['id'], temple['id']))
            assigned += 1
            method_counts['Haversine'] += 1
            an = ao['name'][:45]
            ao_counts[an] = ao_counts.get(an, 0) + 1
            ao_info[an] = (ao['city'], ao['country'])
        else:
            hq_stay += 1

    if not DRY_RUN:
        conn.commit()

    print(f'  Assigned: {assigned} | On HQ: {hq_stay}')
    print(f'  By method: {method_counts}')
    print()
    for name, cnt in sorted(ao_counts.items(), key=lambda x: -x[1]):
        print(f'    {name:50s}: {cnt:>3d}')

    # Step 6: Verify
    print(f'\n[5/6] Verification...')
    c.execute("SELECT parent_lds_type, COUNT(*) FROM lds_hierarchy WHERE lds_type='temple' GROUP BY parent_lds_type")
    for row in c.fetchall():
        print(f'  Temples -> {row[0]:>25}: {row[1]:,}')
    c.execute("SELECT lds_type, COUNT(*) FROM lds_hierarchy GROUP BY lds_type ORDER BY COUNT(*) DESC")
    for row in c.fetchall():
        print(f'  {row[0]:>30}: {row[1]:,}')
    r = c.execute("SELECT COUNT(*) FROM lds_hierarchy WHERE parent_id IS NULL").fetchone()
    print(f'  Root/unlinked: {r[0]}')

    # Provenance
    print(f'\n[6/6] Provenance...')
    if not DRY_RUN:
        now = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
        note = (f'Area hierarchy: {len(all_aos)} AOs ({n_existing} PBOs + {inserted} Wikipedia). '
                f'{assigned} temples to nearest AO, {hq_stay} on HQ.')
        c.execute("""
            INSERT INTO provenance_log(source,script_name,started_at,completed_at,
                churches_updated,churches_inserted,fields_populated,
                records_attempted,records_matched,status,notes)
            VALUES(?,?,?,?,?,?,?,?,?,?,?)
        """, ('lds_hierarchy','build_lds_areas.py',now,now,
              assigned+n_existing,inserted,
              'parent_id,parent_lds_type,relationship,notes',
              len(temples)+n_existing,assigned+n_existing,'completed',note))
        conn.commit()
        print('  Provenance logged.')

    elapsed = time.time() - t0
    print(f'\nTime: {elapsed:.1f}s | Mode: {"DRY RUN" if DRY_RUN else "LIVE"}')
    if DRY_RUN:
        print('Run without --dry-run to execute.')
    conn.close()


if __name__ == '__main__':
    main()
