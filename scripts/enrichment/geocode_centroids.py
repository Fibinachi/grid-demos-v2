"""
Centroid-based geocoding using ZIP centroids and global city gazetteer.
No API calls - pure in-memory lookups. Fast and free.

Data sources:
  - outputs/geocoding/Gaz_zcta_national.txt   (33K Census ZCTA centroids)
  - outputs/geocoding/geonames_cities1000.txt  (170K global cities >1K pop)

Usage:
  python scripts/enrichment/geocode_centroids.py           # all lookups
  python scripts/enrichment/geocode_centroids.py --dry-run # test 5 each
"""
import sqlite3, sys, os
from tqdm import tqdm

BASE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DB = os.path.join(BASE, 'churches.db')
GEO = os.path.join(BASE, 'outputs', 'geocoding')
DRY_RUN = '--dry-run' in sys.argv


def s(v):
    return (v or '').strip()


# ── State name → 2-letter code ──
STATE_TO_ABBR = {
    'ALABAMA': 'AL', 'ALASKA': 'AK', 'ARIZONA': 'AZ', 'ARKANSAS': 'AR',
    'CALIFORNIA': 'CA', 'COLORADO': 'CO', 'CONNECTICUT': 'CT', 'DELAWARE': 'DE',
    'FLORIDA': 'FL', 'GEORGIA': 'GA', 'HAWAII': 'HI', 'IDAHO': 'ID',
    'ILLINOIS': 'IL', 'INDIANA': 'IN', 'IOWA': 'IA', 'KANSAS': 'KS',
    'KENTUCKY': 'KY', 'LOUISIANA': 'LA', 'MAINE': 'ME', 'MARYLAND': 'MD',
    'MASSACHUSETTS': 'MA', 'MICHIGAN': 'MI', 'MINNESOTA': 'MN',
    'MISSISSIPPI': 'MS', 'MISSOURI': 'MO', 'MONTANA': 'MT', 'NEBRASKA': 'NE',
    'NEVADA': 'NV', 'NEW HAMPSHIRE': 'NH', 'NEW JERSEY': 'NJ',
    'NEW MEXICO': 'NM', 'NEW YORK': 'NY', 'NORTH CAROLINA': 'NC',
    'NORTH DAKOTA': 'ND', 'OHIO': 'OH', 'OKLAHOMA': 'OK', 'OREGON': 'OR',
    'PENNSYLVANIA': 'PA', 'RHODE ISLAND': 'RI', 'SOUTH CAROLINA': 'SC',
    'SOUTH DAKOTA': 'SD', 'TENNESSEE': 'TN', 'TEXAS': 'TX', 'UTAH': 'UT',
    'VERMONT': 'VT', 'VIRGINIA': 'VA', 'WASHINGTON': 'WA',
    'WEST VIRGINIA': 'WV', 'WISCONSIN': 'WI', 'WYOMING': 'WY',
    'DISTRICT OF COLUMBIA': 'DC', 'DC': 'DC',
    'PUERTO RICO': 'PR', 'GUAM': 'GU', 'AMERICAN SAMOA': 'AS',
    'NORTHERN MARIANA ISLANDS': 'MP', 'US VIRGIN ISLANDS': 'VI',
}


def norm_state(st):
    """Normalize to 2-letter US state code. Returns '' if unrecognized."""
    st = s(st).upper()
    if len(st) == 2 and st in STATE_TO_ABBR.values():
        return st
    return STATE_TO_ABBR.get(st, '')


# ── Country name → 2-letter ISO ──
COUNTRY_TO_ISO = {
    'AF': 'AF', 'AFGHANISTAN': 'AF', 'AL': 'AL', 'ALBANIA': 'AL',
    'DZ': 'DZ', 'ALGERIA': 'DZ', 'AS': 'AS', 'AMERICAN SAMOA': 'AS',
    'AD': 'AD', 'ANDORRA': 'AD', 'AO': 'AO', 'ANGOLA': 'AO',
    'AR': 'AR', 'ARGENTINA': 'AR', 'AM': 'AM', 'ARMENIA': 'AM',
    'AU': 'AU', 'AUSTRALIA': 'AU', 'AT': 'AT', 'AUSTRIA': 'AT',
    'AZ': 'AZ', 'AZERBAIJAN': 'AZ', 'BS': 'BS', 'BAHAMAS': 'BS',
    'BH': 'BH', 'BAHRAIN': 'BH', 'BD': 'BD', 'BANGLADESH': 'BD',
    'BB': 'BB', 'BARBADOS': 'BB', 'BY': 'BY', 'BELARUS': 'BY',
    'BE': 'BE', 'BELGIUM': 'BE', 'BZ': 'BZ', 'BELIZE': 'BZ',
    'BJ': 'BJ', 'BENIN': 'BJ', 'BM': 'BM', 'BERMUDA': 'BM',
    'BT': 'BT', 'BHUTAN': 'BT', 'BO': 'BO', 'BOLIVIA': 'BO',
    'BA': 'BA', 'BOSNIA': 'BA', 'BW': 'BW', 'BOTSWANA': 'BW',
    'BR': 'BR', 'BRAZIL': 'BR', 'BN': 'BN', 'BRUNEI': 'BN',
    'BG': 'BG', 'BULGARIA': 'BG', 'BF': 'BF', 'BURKINA FASO': 'BF',
    'BI': 'BI', 'BURUNDI': 'BI', 'CV': 'CV', 'CABO VERDE': 'CV',
    'KH': 'KH', 'CAMBODIA': 'KH', 'CM': 'CM', 'CAMEROON': 'CM',
    'CA': 'CA', 'CANADA': 'CA', 'KY': 'KY', 'CAYMAN ISLANDS': 'KY',
    'CF': 'CF', 'CENTRAL AFRICAN REPUBLIC': 'CF', 'TD': 'TD', 'CHAD': 'TD',
    'CL': 'CL', 'CHILE': 'CL', 'CN': 'CN', 'CHINA': 'CN',
    'CO': 'CO', 'COLOMBIA': 'CO', 'KM': 'KM', 'COMOROS': 'KM',
    'CG': 'CG', 'CONGO': 'CG', 'CD': 'CD', 'DRC': 'CD',
    'CR': 'CR', 'COSTA RICA': 'CR', 'CI': 'CI', "COTE D'IVOIRE": 'CI',
    'HR': 'HR', 'CROATIA': 'HR', 'CU': 'CU', 'CUBA': 'CU',
    'CY': 'CY', 'CYPRUS': 'CY', 'CZ': 'CZ', 'CZECH REPUBLIC': 'CZ',
    'DK': 'DK', 'DENMARK': 'DK', 'DJ': 'DJ', 'DJIBOUTI': 'DJ',
    'DO': 'DO', 'DOMINICAN REPUBLIC': 'DO', 'EC': 'EC', 'ECUADOR': 'EC',
    'EG': 'EG', 'EGYPT': 'EG', 'SV': 'SV', 'EL SALVADOR': 'SV',
    'GQ': 'GQ', 'EQUATORIAL GUINEA': 'GQ', 'ER': 'ER', 'ERITREA': 'ER',
    'EE': 'EE', 'ESTONIA': 'EE', 'SZ': 'SZ', 'ESWATINI': 'SZ',
    'ET': 'ET', 'ETHIOPIA': 'ET', 'FJ': 'FJ', 'FIJI': 'FJ',
    'FI': 'FI', 'FINLAND': 'FI', 'FR': 'FR', 'FRANCE': 'FR',
    'GA': 'GA', 'GABON': 'GA', 'GM': 'GM', 'GAMBIA': 'GM',
    'GE': 'GE', 'GEORGIA': 'GE', 'DE': 'DE', 'GERMANY': 'DE',
    'GH': 'GH', 'GHANA': 'GH', 'GR': 'GR', 'GREECE': 'GR',
    'GL': 'GL', 'GREENLAND': 'GL', 'GT': 'GT', 'GUATEMALA': 'GT',
    'GN': 'GN', 'GUINEA': 'GN', 'GW': 'GW', 'GUINEA-BISSAU': 'GW',
    'GY': 'GY', 'GUYANA': 'GY', 'HT': 'HT', 'HAITI': 'HT',
    'HN': 'HN', 'HONDURAS': 'HN', 'HK': 'HK', 'HONG KONG': 'HK',
    'HU': 'HU', 'HUNGARY': 'HU', 'IS': 'IS', 'ICELAND': 'IS',
    'IN': 'IN', 'INDIA': 'IN', 'ID': 'ID', 'INDONESIA': 'ID',
    'IR': 'IR', 'IRAN': 'IR', 'IQ': 'IQ', 'IRAQ': 'IQ',
    'IE': 'IE', 'IRELAND': 'IE', 'IL': 'IL', 'ISRAEL': 'IL',
    'IT': 'IT', 'ITALY': 'IT', 'JM': 'JM', 'JAMAICA': 'JM',
    'JP': 'JP', 'JAPAN': 'JP', 'JO': 'JO', 'JORDAN': 'JO',
    'KZ': 'KZ', 'KAZAKHSTAN': 'KZ', 'KE': 'KE', 'KENYA': 'KE',
    'KI': 'KI', 'KIRIBATI': 'KI', 'KP': 'KP', 'NORTH KOREA': 'KP',
    'KR': 'KR', 'SOUTH KOREA': 'KR', 'KW': 'KW', 'KUWAIT': 'KW',
    'KG': 'KG', 'KYRGYZSTAN': 'KG', 'LA': 'LA', 'LAOS': 'LA',
    'LV': 'LV', 'LATVIA': 'LV', 'LB': 'LB', 'LEBANON': 'LB',
    'LS': 'LS', 'LESOTHO': 'LS', 'LR': 'LR', 'LIBERIA': 'LR',
    'LY': 'LY', 'LIBYA': 'LY', 'LI': 'LI', 'LIECHTENSTEIN': 'LI',
    'LT': 'LT', 'LITHUANIA': 'LT', 'LU': 'LU', 'LUXEMBOURG': 'LU',
    'MO': 'MO', 'MACAO': 'MO', 'MG': 'MG', 'MADAGASCAR': 'MG',
    'MW': 'MW', 'MALAWI': 'MW', 'MY': 'MY', 'MALAYSIA': 'MY',
    'MV': 'MV', 'MALDIVES': 'MV', 'ML': 'ML', 'MALI': 'ML',
    'MT': 'MT', 'MALTA': 'MT', 'MH': 'MH', 'MARSHALL ISLANDS': 'MH',
    'MR': 'MR', 'MAURITANIA': 'MR', 'MU': 'MU', 'MAURITIUS': 'MU',
    'MX': 'MX', 'MEXICO': 'MX', 'FM': 'FM', 'MICRONESIA': 'FM',
    'MD': 'MD', 'MOLDOVA': 'MD', 'MC': 'MC', 'MONACO': 'MC',
    'MN': 'MN', 'MONGOLIA': 'MN', 'ME': 'ME', 'MONTENEGRO': 'ME',
    'MA': 'MA', 'MOROCCO': 'MA', 'MZ': 'MZ', 'MOZAMBIQUE': 'MZ',
    'MM': 'MM', 'MYANMAR': 'MM', 'NA': 'NA', 'NAMIBIA': 'NA',
    'NR': 'NR', 'NAURU': 'NR', 'NP': 'NP', 'NEPAL': 'NP',
    'NL': 'NL', 'NETHERLANDS': 'NL', 'NZ': 'NZ', 'NEW ZEALAND': 'NZ',
    'NI': 'NI', 'NICARAGUA': 'NI', 'NE': 'NE', 'NIGER': 'NE',
    'NG': 'NG', 'NIGERIA': 'NG', 'MK': 'MK', 'NORTH MACEDONIA': 'MK',
    'MP': 'MP', 'NORTHERN MARIANA ISLANDS': 'MP', 'NO': 'NO', 'NORWAY': 'NO',
    'OM': 'OM', 'OMAN': 'OM', 'PK': 'PK', 'PAKISTAN': 'PK',
    'PW': 'PW', 'PALAU': 'PW', 'PS': 'PS', 'PALESTINE': 'PS',
    'PA': 'PA', 'PANAMA': 'PA', 'PG': 'PG', 'PAPUA NEW GUINEA': 'PG',
    'PY': 'PY', 'PARAGUAY': 'PY', 'PE': 'PE', 'PERU': 'PE',
    'PH': 'PH', 'PHILIPPINES': 'PH', 'PL': 'PL', 'POLAND': 'PL',
    'PT': 'PT', 'PORTUGAL': 'PT', 'PR': 'PR', 'PUERTO RICO': 'PR',
    'QA': 'QA', 'QATAR': 'QA', 'RO': 'RO', 'ROMANIA': 'RO',
    'RU': 'RU', 'RUSSIA': 'RU', 'RW': 'RW', 'RWANDA': 'RW',
    'WS': 'WS', 'SAMOA': 'WS', 'SM': 'SM', 'SAN MARINO': 'SM',
    'ST': 'ST', 'SAO TOME AND PRINCIPE': 'ST', 'SA': 'SA', 'SAUDI ARABIA': 'SA',
    'SN': 'SN', 'SENEGAL': 'SN', 'RS': 'RS', 'SERBIA': 'RS',
    'SC': 'SC', 'SEYCHELLES': 'SC', 'SL': 'SL', 'SIERRA LEONE': 'SL',
    'SG': 'SG', 'SINGAPORE': 'SG', 'SK': 'SK', 'SLOVAKIA': 'SK',
    'SI': 'SI', 'SLOVENIA': 'SI', 'SB': 'SB', 'SOLOMON ISLANDS': 'SB',
    'SO': 'SO', 'SOMALIA': 'SO', 'ZA': 'ZA', 'SOUTH AFRICA': 'ZA',
    'SS': 'SS', 'SOUTH SUDAN': 'SS', 'ES': 'ES', 'SPAIN': 'ES',
    'LK': 'LK', 'SRI LANKA': 'LK', 'SD': 'SD', 'SUDAN': 'SD',
    'SR': 'SR', 'SURINAME': 'SR', 'SE': 'SE', 'SWEDEN': 'SE',
    'CH': 'CH', 'SWITZERLAND': 'CH', 'SY': 'SY', 'SYRIA': 'SY',
    'TW': 'TW', 'TAIWAN': 'TW', 'TJ': 'TJ', 'TAJIKISTAN': 'TJ',
    'TZ': 'TZ', 'TANZANIA': 'TZ', 'TH': 'TH', 'THAILAND': 'TH',
    'TL': 'TL', 'TIMOR-LESTE': 'TL', 'TG': 'TG', 'TOGO': 'TG',
    'TO': 'TO', 'TONGA': 'TO', 'TT': 'TT', 'TRINIDAD AND TOBAGO': 'TT',
    'TN': 'TN', 'TUNISIA': 'TN', 'TR': 'TR', 'TURKEY': 'TR',
    'TM': 'TM', 'TURKMENISTAN': 'TM', 'TV': 'TV', 'TUVALU': 'TV',
    'UG': 'UG', 'UGANDA': 'UG', 'UA': 'UA', 'UKRAINE': 'UA',
    'AE': 'AE', 'UAE': 'AE', 'UNITED ARAB EMIRATES': 'AE',
    'GB': 'GB', 'UNITED KINGDOM': 'GB', 'UK': 'GB', 'ENGLAND': 'GB',
    'US': 'US', 'UNITED STATES': 'US', 'USA': 'US',
    'UY': 'UY', 'URUGUAY': 'UY', 'UZ': 'UZ', 'UZBEKISTAN': 'UZ',
    'VU': 'VU', 'VANUATU': 'VU', 'VA': 'VA', 'VATICAN CITY': 'VA',
    'VE': 'VE', 'VENEZUELA': 'VE', 'VN': 'VN', 'VIETNAM': 'VN',
    'VI': 'VI', 'US VIRGIN ISLANDS': 'VI', 'YE': 'YE', 'YEMEN': 'YE',
    'ZM': 'ZM', 'ZAMBIA': 'ZM', 'ZW': 'ZW', 'ZIMBABWE': 'ZW',
}


def norm_country(c):
    """Normalize to 2-letter ISO country code. Returns '' if unrecognized."""
    c = s(c).upper()
    if len(c) == 2 and c in COUNTRY_TO_ISO.values():
        return c
    return COUNTRY_TO_ISO.get(c, '')


# ── Data loaders ──

def load_zcta():
    """Returns {zip5: (lat, lon)} from Census ZCTA gazetteer."""
    zips = {}
    path = os.path.join(GEO, 'Gaz_zcta_national.txt')
    if not os.path.exists(path):
        print(f"  WARNING: {path} not found!")
        return zips
    with open(path, encoding='latin-1') as f:
        next(f)
        for line in f:
            p = line.strip().split('\t')
            if len(p) >= 9:
                geo_id = p[0].strip()
                lat = float(p[7]) if p[7] else 0
                lon = float(p[8]) if p[8] else 0
                if lat and lon:
                    zips[geo_id] = (lat, lon)
    print(f"  Loaded {len(zips):,} US ZCTA centroids")
    return zips


def load_cities():
    """Returns {(city_lower, admin1, country_iso): (lat, lon, full_name)}
    admin1 is 2-letter state for US, province code for others, '' if unknown."""
    cities = {}
    path = os.path.join(GEO, 'geonames_cities1000.txt')
    if not os.path.exists(path):
        print(f"  WARNING: {path} not found!")
        return cities
    with open(path, encoding='utf-8') as f:
        for line in tqdm(f, desc="  Loading cities", unit=' lines', total=170_000):
            p = line.strip().split('\t')
            if len(p) < 11:
                continue
            if p[6].strip() != 'P':  # populated places only
                continue
            name = p[1].strip().lower()
            country = p[8].strip().upper()
            admin1 = p[10].strip().upper() if len(p) > 10 else ''
            lat = float(p[4]) if p[4] else 0
            lon = float(p[5]) if p[5] else 0
            full = p[1].strip()
            if lat and lon and country:
                key = (name, admin1, country)
                if key not in cities:
                    cities[key] = (lat, lon, full)
                # Also index without admin1 for cross-state/country fallback
                key2 = (name, '', country)
                if key2 not in cities:
                    cities[key2] = (lat, lon, full)
                # Index alternate names
                alt = p[3].strip().lower() if p[3] else ''
                if alt:
                    for a in alt.split(','):
                        a = a.strip()
                        if a and a != name:
                            ak = (a, admin1, country)
                            if ak not in cities:
                                cities[ak] = (lat, lon, full)
                            ak2 = (a, '', country)
                            if ak2 not in cities:
                                cities[ak2] = (lat, lon, full)
    print(f"  Loaded {len(cities):,} global city centroids")
    return cities


# ── Main ──

def main():
    print("Loading lookup tables...")
    zips = load_zcta()
    cities = load_cities()
    print()

    if not zips and not cities:
        print("No lookup data loaded!")
        return

    db = sqlite3.connect(DB)
    db.execute("PRAGMA journal_mode=WAL")
    c = db.cursor()

    if DRY_RUN:
        print("DRY RUN - 5 samples each\n")

    zi = ci = gi = no = 0
    batch = []

    # ── Phase 1: US ZIP centroids ──
    if zips:
        c.execute("""SELECT id, name, zip, city, state FROM churches
            WHERE country='US' AND (latitude IS NULL OR latitude=0)
            AND zip IS NOT NULL AND zip!='' ORDER BY id""")
        rows = c.fetchall()
        print(f"Phase 1: US ZIP -> {len(rows):,} candidates")
        if DRY_RUN:
            rows = rows[:5]

        for row in tqdm(rows, desc="  ZIP lookup", unit='rec'):
            chid, name, zip_code, city, state = row
            zip5 = s(zip_code)[:5]
            m = zips.get(zip5)
            if m:
                lat, lon = m
                batch.append((lat, lon, 'zip_centroid', chid))
                zi += 1
                if DRY_RUN:
                    print(f"  OK [{chid}] ZIP {zip5} -> {lat:.6f},{lon:.6f} | {s(name)[:40]}")
            else:
                no += 1
                if DRY_RUN:
                    print(f"  NOM [{chid}] ZIP {zip5} not found | {s(name)[:40]}")

        if batch:
            c.executemany("UPDATE churches SET latitude=?, longitude=?, geocode_source=? WHERE id=?", batch)
            db.commit()
            print(f"  -> {zi:,} matched\n")
            batch = []

    # ── Phase 2: US city+state ──
    if cities:
        c.execute("""SELECT id, name, city, state FROM churches
            WHERE country='US' AND (latitude IS NULL OR latitude=0)
            AND city IS NOT NULL AND city!=''
            AND state IS NOT NULL AND state!='' ORDER BY id""")
        rows = c.fetchall()
        print(f"Phase 2: US city+state -> {len(rows):,} candidates")
        if DRY_RUN:
            rows = rows[:5]

        for row in tqdm(rows, desc="  City lookup", unit='rec'):
            chid, name, city, state = row
            st = norm_state(state)
            city_lower = s(city).lower()
            
            if st:
                m = cities.get((city_lower, st, 'US'))
            else:
                m = None
            
            if m:
                lat, lon, full = m
                batch.append((lat, lon, 'city_centroid', chid))
                ci += 1
                if DRY_RUN:
                    print(f"  OK [{chid}] {s(city)}, {st or '??'} -> {lat:.6f},{lon:.6f} ({full}) | {s(name)[:35]}")
            else:
                no += 1
                if DRY_RUN:
                    print(f"  NOM [{chid}] {s(city)}, {st or '??'} not found | {s(name)[:40]}")

        if batch:
            c.executemany("UPDATE churches SET latitude=?, longitude=?, geocode_source=? WHERE id=?", batch)
            db.commit()
            print(f"  -> {ci:,} matched\n")
            batch = []

    # ── Phase 3: Global city+country ──
    if cities:
        c.execute("""SELECT id, name, city, state, country FROM churches
            WHERE country IS NOT NULL AND country!='' AND country!='US'
            AND city IS NOT NULL AND city!=''
            AND (latitude IS NULL OR latitude=0) ORDER BY id""")
        rows = c.fetchall()
        print(f"Phase 3: Global city+country -> {len(rows):,} candidates")
        if DRY_RUN:
            rows = rows[:5]

        for row in tqdm(rows, desc="  Global lookup", unit='rec'):
            chid, name, city, state, country = row
            cc = norm_country(country)
            if not cc:
                no += 1
                continue
            city_lower = s(city).lower()
            m = cities.get((city_lower, '', cc))
            if m:
                lat, lon, full = m
                batch.append((lat, lon, 'global_gazetteer', chid))
                gi += 1
                if DRY_RUN:
                    print(f"  OK [{chid}] {s(city)}, {cc} -> {lat:.6f},{lon:.6f} ({full}) | {s(name)[:35]}")
            else:
                no += 1
                if DRY_RUN:
                    print(f"  NOM [{chid}] {s(city)}, {cc} not found | {s(name)[:40]}")

        if batch:
            c.executemany("UPDATE churches SET latitude=?, longitude=?, geocode_source=? WHERE id=?", batch)
            db.commit()
            print(f"  -> {gi:,} matched\n")

    print(f"{'='*60}")
    print(f"COMPLETE")
    print(f"  ZIP centroids:     {zi:>10,}")
    print(f"  US city centroids: {ci:>10,}")
    print(f"  Global gazetteer:  {gi:>10,}")
    print(f"  TOTAL:             {zi+ci+gi:>10,}")
    print(f"  No match:          {no:>10,}")
    db.close()


if __name__ == '__main__':
    main()
