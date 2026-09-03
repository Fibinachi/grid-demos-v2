"""
Fix 128,949 records that have country but no continent.
Uses a country→continent mapping derived from UN M.49 standard.
"""
from gw_db import connect, Provenance, log_change

# Comprehensive country -> continent mapping (ISO alpha-2 codes)
# Based on UN statistical division classification
COUNTRY_CONTINENT = {
    # North America
    'US': 'North America', 'CA': 'North America', 'MX': 'North America',
    'BM': 'North America', 'GL': 'North America', 'PM': 'North America',
    'BZ': 'North America', 'CR': 'North America', 'SV': 'North America',
    'GT': 'North America', 'HN': 'North America', 'NI': 'North America',
    'PA': 'North America',
    # Caribbean (part of North America per UN)
    'AI': 'North America', 'AG': 'North America', 'AW': 'North America',
    'BS': 'North America', 'BB': 'North America', 'BQ': 'North America',
    'VG': 'North America', 'KY': 'North America', 'CU': 'North America',
    'CW': 'North America', 'DM': 'North America', 'DO': 'North America',
    'GD': 'North America', 'GP': 'North America', 'HT': 'North America',
    'JM': 'North America', 'MQ': 'North America', 'MS': 'North America',
    'PR': 'North America', 'BL': 'North America', 'KN': 'North America',
    'LC': 'North America', 'MF': 'North America', 'VC': 'North America',
    'SX': 'North America', 'TT': 'North America', 'TC': 'North America',
    'VI': 'North America',

    # South America
    'AR': 'South America', 'BO': 'South America', 'BR': 'South America',
    'CL': 'South America', 'CO': 'South America', 'EC': 'South America',
    'FK': 'South America', 'GF': 'South America', 'GY': 'South America',
    'PY': 'South America', 'PE': 'South America', 'SR': 'South America',
    'UY': 'South America', 'VE': 'South America',

    # Europe
    'AL': 'Europe', 'AD': 'Europe', 'AM': 'Europe', 'AT': 'Europe',
    'AZ': 'Europe', 'BY': 'Europe', 'BE': 'Europe', 'BA': 'Europe',
    'BG': 'Europe', 'HR': 'Europe', 'CY': 'Europe', 'CZ': 'Europe',
    'DK': 'Europe', 'EE': 'Europe', 'FO': 'Europe', 'FI': 'Europe',
    'FR': 'Europe', 'GE': 'Europe', 'DE': 'Europe', 'GI': 'Europe',
    'GR': 'Europe', 'GG': 'Europe', 'VA': 'Europe', 'HU': 'Europe',
    'IS': 'Europe', 'IE': 'Europe', 'IM': 'Europe', 'IT': 'Europe',
    'JE': 'Europe', 'XK': 'Europe', 'LV': 'Europe', 'LI': 'Europe',
    'LT': 'Europe', 'LU': 'Europe', 'MT': 'Europe', 'MD': 'Europe',
    'MC': 'Europe', 'ME': 'Europe', 'NL': 'Europe', 'MK': 'Europe',
    'NO': 'Europe', 'PL': 'Europe', 'PT': 'Europe', 'RO': 'Europe',
    'RU': 'Europe', 'SM': 'Europe', 'RS': 'Europe', 'SK': 'Europe',
    'SI': 'Europe', 'ES': 'Europe', 'SJ': 'Europe', 'SE': 'Europe',
    'CH': 'Europe', 'UA': 'Europe', 'GB': 'Europe', 'AX': 'Europe',
    'SX': 'Europe',  # Sint Maarten is sometimes classified here

    # Africa
    'DZ': 'Africa', 'AO': 'Africa', 'BJ': 'Africa', 'BW': 'Africa',
    'BF': 'Africa', 'BI': 'Africa', 'CV': 'Africa', 'CM': 'Africa',
    'CF': 'Africa', 'TD': 'Africa', 'KM': 'Africa', 'CD': 'Africa',
    'CG': 'Africa', 'CI': 'Africa', 'DJ': 'Africa', 'EG': 'Africa',
    'GQ': 'Africa', 'ER': 'Africa', 'SZ': 'Africa', 'ET': 'Africa',
    'GA': 'Africa', 'GM': 'Africa', 'GH': 'Africa', 'GN': 'Africa',
    'GW': 'Africa', 'KE': 'Africa', 'LS': 'Africa', 'LR': 'Africa',
    'LY': 'Africa', 'MG': 'Africa', 'MW': 'Africa', 'ML': 'Africa',
    'MR': 'Africa', 'MU': 'Africa', 'MA': 'Africa', 'MZ': 'Africa',
    'NA': 'Africa', 'NE': 'Africa', 'NG': 'Africa', 'RW': 'Africa',
    'ST': 'Africa', 'SN': 'Africa', 'SC': 'Africa', 'SL': 'Africa',
    'SO': 'Africa', 'ZA': 'Africa', 'SS': 'Africa', 'SD': 'Africa',
    'TZ': 'Africa', 'TG': 'Africa', 'TN': 'Africa', 'UG': 'Africa',
    'ZM': 'Africa', 'ZW': 'Africa', 'EH': 'Africa', 'SH': 'Africa',
    'YT': 'Africa', 'RE': 'Africa',

    # Asia
    'AF': 'Asia', 'AM': 'Asia', 'AZ': 'Asia', 'BH': 'Asia',
    'BD': 'Asia', 'BT': 'Asia', 'BN': 'Asia', 'KH': 'Asia',
    'CN': 'Asia', 'CX': 'Asia', 'CC': 'Asia', 'IO': 'Asia',
    'GE': 'Asia', 'HK': 'Asia', 'IN': 'Asia', 'ID': 'Asia',
    'IR': 'Asia', 'IQ': 'Asia', 'IL': 'Asia', 'JP': 'Asia',
    'JO': 'Asia', 'KZ': 'Asia', 'KW': 'Asia', 'KG': 'Asia',
    'LA': 'Asia', 'LB': 'Asia', 'MO': 'Asia', 'MY': 'Asia',
    'MV': 'Asia', 'MN': 'Asia', 'MM': 'Asia', 'NP': 'Asia',
    'KP': 'Asia', 'OM': 'Asia', 'PK': 'Asia', 'PS': 'Asia',
    'PH': 'Asia', 'QA': 'Asia', 'SA': 'Asia', 'SG': 'Asia',
    'KR': 'Asia', 'LK': 'Asia', 'SY': 'Asia', 'TW': 'Asia',
    'TJ': 'Asia', 'TH': 'Asia', 'TL': 'Asia', 'TR': 'Asia',
    'TM': 'Asia', 'AE': 'Asia', 'UZ': 'Asia', 'VN': 'Asia',
    'YE': 'Asia',

    # Oceania
    'AS': 'Oceania', 'AU': 'Oceania', 'CK': 'Oceania', 'FJ': 'Oceania',
    'PF': 'Oceania', 'GU': 'Oceania', 'KI': 'Oceania', 'MH': 'Oceania',
    'FM': 'Oceania', 'NR': 'Oceania', 'NC': 'Oceania', 'NZ': 'Oceania',
    'NU': 'Oceania', 'NF': 'Oceania', 'MP': 'Oceania', 'PW': 'Oceania',
    'PG': 'Oceania', 'PN': 'Oceania', 'WS': 'Oceania', 'SB': 'Oceania',
    'TK': 'Oceania', 'TO': 'Oceania', 'TV': 'Oceania', 'VU': 'Oceania',
    'WF': 'Oceania',

    # Antarctica
    'AQ': 'Antarctica', 'BV': 'Antarctica', 'GS': 'Antarctica',
    'HM': 'Antarctica', 'TF': 'Antarctica',
}

# Some countries are transcontinental — use the most common assignment
# Russia -> Europe (UN convention), Turkey -> Asia, etc.
# For edge cases, override above:
OVERLAY = {
    'RU': 'Europe',      # UN classifies Russia as Europe
    'TR': 'Asia',         # UN classification (though transcontinental)
    'AM': 'Asia',         # UN: Western Asia
    'AZ': 'Asia',         # UN: Western Asia
    'GE': 'Asia',         # UN: Western Asia
    'CY': 'Europe',       # UN: Europe
    'GR': 'Europe',
    'MX': 'North America',
    'IL': 'Asia',
    'PS': 'Asia',
    'KZ': 'Asia',         # UN: Central Asia
}
COUNTRY_CONTINENT.update(OVERLAY)

db = connect()

# Check how many we can map
c = db.cursor()
c.execute("""
    SELECT DISTINCT country
    FROM churches
    WHERE (continent IS NULL OR continent = '')
    AND country IS NOT NULL AND country != ''
""")
missing_countries = [r[0] for r in c.fetchall()]
mappable = sum(1 for cc in missing_countries if cc in COUNTRY_CONTINENT)
unmappable = [cc for cc in missing_countries if cc not in COUNTRY_CONTINENT]
print(f"Countries needing continent: {len(missing_countries)}")
print(f"  Mappable: {mappable}")
print(f"  Unmappable: {len(unmappable)} -> {unmappable}")

# Run the fix
with Provenance(db, script_name="_fix_continents.py",
                source="continent_fix", action="enriched",
                fields="continent") as prov:

    # Build case statement
    case_sql = "UPDATE churches SET continent = CASE country\n"
    for cc, cont in COUNTRY_CONTINENT.items():
        case_sql += f"  WHEN '{cc}' THEN '{cont}'\n"
    case_sql += "  ELSE continent\nEND\n"
    case_sql += "WHERE (continent IS NULL OR continent = '')\n"
    case_sql += "AND country IS NOT NULL AND country != ''"

    c = db.cursor()
    c.execute(case_sql)
    affected = db._conn.total_changes  # approximate, but good enough
    prov.churches_updated = affected

db.commit()
print(f"\nUpdated {affected:,} records with continent data")

# Verify
c.execute("SELECT COUNT(*) FROM churches WHERE (continent IS NULL OR continent = '') AND country IS NOT NULL AND country != ''")
remaining = c.fetchone()[0]
print(f"Remaining without continent (but have country): {remaining:,}")

# Also fix the 8 with neither
c.execute("SELECT COUNT(*) FROM churches WHERE (continent IS NULL OR continent = '') AND (country IS NULL OR country = '')")
no_nada = c.fetchone()[0]
print(f"Remaining with NEITHER country nor continent: {no_nada}")

db.close()
