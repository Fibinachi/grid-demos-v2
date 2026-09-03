"""
Download geoBoundaries admin boundaries for all countries with churches.
Downloads Admin 0, 1, 2 (and 3 where available) for spatial joins.

geoBoundaries API: https://www.geoboundaries.org/api/current/gbOpen/{ISO3}/ADM{level}/
Free, CC-BY-4.0 license.
"""
import urllib.request, json, os, sys, time

BASE_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), 'data', 'world_boundaries')
os.makedirs(BASE_DIR, exist_ok=True)

# Get list of countries with churches
import sqlite3
db = sqlite3.connect(os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), 'churches.db'))

# Get ISO3 codes for all countries in DB
# We need a country name→ISO3 mapping. Use our existing COUNTRY_TO_ISO and then ISO2→ISO3
ISO2_TO_ISO3 = {
    'AF':'AFG','AL':'ALB','DZ':'DZA','AS':'ASM','AD':'AND','AO':'AGO',
    'AR':'ARG','AM':'ARM','AU':'AUS','AT':'AUT','AZ':'AZE','BS':'BHS',
    'BH':'BHR','BD':'BGD','BB':'BRB','BY':'BLR','BE':'BEL','BZ':'BLZ',
    'BJ':'BEN','BM':'BMU','BT':'BTN','BO':'BOL','BA':'BIH','BW':'BWA',
    'BR':'BRA','BN':'BRN','BG':'BGR','BF':'BFA','BI':'BDI','CV':'CPV',
    'KH':'KHM','CM':'CMR','CA':'CAN','KY':'CYM','CF':'CAF','TD':'TCD',
    'CL':'CHL','CN':'CHN','CO':'COL','KM':'COM','CG':'COG','CD':'COD',
    'CR':'CRI','CI':'CIV','HR':'HRV','CU':'CUB','CY':'CYP','CZ':'CZE',
    'DK':'DNK','DJ':'DJI','DO':'DOM','EC':'ECU','EG':'EGY','SV':'SLV',
    'GQ':'GNQ','ER':'ERI','EE':'EST','SZ':'SWZ','ET':'ETH','FJ':'FJI',
    'FI':'FIN','FR':'FRA','GA':'GAB','GM':'GMB','GE':'GEO','DE':'DEU',
    'GH':'GHA','GR':'GRC','GL':'GRL','GT':'GTM','GN':'GIN','GW':'GNB',
    'GY':'GUY','HT':'HTI','HN':'HND','HK':'HKG','HU':'HUN','IS':'ISL',
    'IN':'IND','ID':'IDN','IR':'IRN','IQ':'IRQ','IE':'IRL','IL':'ISR',
    'IT':'ITA','JM':'JAM','JP':'JPN','JO':'JOR','KZ':'KAZ','KE':'KEN',
    'KI':'KIR','KP':'PRK','KR':'KOR','KW':'KWT','KG':'KGZ','LA':'LAO',
    'LV':'LVA','LB':'LBN','LS':'LSO','LR':'LBR','LY':'LBY','LI':'LIE',
    'LT':'LTU','LU':'LUX','MO':'MAC','MG':'MDG','MW':'MWI','MY':'MYS',
    'MV':'MDV','ML':'MLI','MT':'MLT','MH':'MHL','MR':'MRT','MU':'MUS',
    'MX':'MEX','FM':'FSM','MD':'MDA','MC':'MCO','MN':'MNG','ME':'MNE',
    'MA':'MAR','MZ':'MOZ','MM':'MMR','NA':'NAM','NR':'NRU','NP':'NPL',
    'NL':'NLD','NZ':'NZL','NI':'NIC','NE':'NER','NG':'NGA','MK':'MKD',
    'MP':'MNP','NO':'NOR','OM':'OMN','PK':'PAK','PW':'PLW','PS':'PSE',
    'PA':'PAN','PG':'PNG','PY':'PRY','PE':'PER','PH':'PHL','PL':'POL',
    'PT':'PRT','PR':'PRI','QA':'QAT','RO':'ROU','RU':'RUS','RW':'RWA',
    'WS':'WSM','SM':'SMR','ST':'STP','SA':'SAU','SN':'SEN','RS':'SRB',
    'SC':'SYC','SL':'SLE','SG':'SGP','SK':'SVK','SI':'SVN','SB':'SLB',
    'SO':'SOM','ZA':'ZAF','SS':'SSD','ES':'ESP','LK':'LKA','SD':'SDN',
    'SR':'SUR','SE':'SWE','CH':'CHE','SY':'SYR','TW':'TWN','TJ':'TJK',
    'TZ':'TZA','TH':'THA','TL':'TLS','TG':'TGO','TO':'TON','TT':'TTO',
    'TN':'TUN','TR':'TUR','TM':'TKM','TV':'TUV','UG':'UGA','UA':'UKR',
    'AE':'ARE','GB':'GBR','US':'USA','UY':'URY','UZ':'UZB','VU':'VUT',
    'VA':'VAT','VE':'VEN','VN':'VNM','VI':'VIR','YE':'YEM','ZM':'ZMB',
    'ZW':'ZWE',
}

# Countries with most churches, get their ISO3
country_counts = db.execute("""
    SELECT country, COUNT(*) n FROM churches
    WHERE country IS NOT NULL AND country!=''
    AND latitude IS NOT NULL AND latitude!=0
    GROUP BY country ORDER BY n DESC LIMIT 80
""").fetchall()

# ISO2 code mapping (same as in geocode_centroids.py)
COUNTRY_TO_ISO = {
    'CA':'CA','CANADA':'CA','MX':'MX','MEXICO':'MX','GB':'GB','UNITED KINGDOM':'GB','UK':'GB',
    'IN':'IN','INDIA':'IN','IE':'IE','IRELAND':'IE','DE':'DE','GERMANY':'DE',
    'FR':'FR','FRANCE':'FR','IT':'IT','ITALY':'IT','ES':'ES','SPAIN':'ES',
    'BR':'BR','BRAZIL':'BR','AU':'AU','AUSTRALIA':'AU','JP':'JP','JAPAN':'JP',
    'KR':'KR','SOUTH KOREA':'KR','PH':'PH','PHILIPPINES':'PH','ID':'ID','INDONESIA':'ID',
    'ZA':'ZA','SOUTH AFRICA':'ZA','NG':'NG','NIGERIA':'NG','KE':'KE','KENYA':'KE',
    'TZ':'TZ','TANZANIA':'TZ','GH':'GH','GHANA':'GH','ET':'ET','ETHIOPIA':'ET',
    'EG':'EG','EGYPT':'EG','SA':'SA','SAUDI ARABIA':'SA','TR':'TR','TURKEY':'TR',
    'PK':'PK','PAKISTAN':'PK','BD':'BD','BANGLADESH':'BD','TH':'TH','THAILAND':'TH',
    'VN':'VN','VIETNAM':'VN','MY':'MY','MALAYSIA':'MY','CN':'CN','CHINA':'CN',
    'TW':'TW','TAIWAN':'TW','RU':'RU','RUSSIA':'RU','PL':'PL','POLAND':'PL',
    'UA':'UA','UKRAINE':'UA','RO':'RO','ROMANIA':'RO','NL':'NL','NETHERLANDS':'NL',
    'BE':'BE','BELGIUM':'BE','CH':'CH','SWITZERLAND':'CH','AT':'AT','AUSTRIA':'AT',
    'SE':'SE','SWEDEN':'SE','NO':'NO','NORWAY':'NO','DK':'DK','DENMARK':'DK',
    'FI':'FI','FINLAND':'FI','PT':'PT','PORTUGAL':'PT','GR':'GR','GREECE':'GR',
    'CZ':'CZ','CZECH REPUBLIC':'CZ','HU':'HU','HUNGARY':'HU','AR':'AR','ARGENTINA':'AR',
    'CL':'CL','CHILE':'CL','CO':'CO','COLOMBIA':'CO','PE':'PE','PERU':'PE',
    'VE':'VE','VENEZUELA':'VE','EC':'EC','ECUADOR':'EC','BO':'BO','BOLIVIA':'BO',
    'PY':'PY','PARAGUAY':'PY','NZ':'NZ','NEW ZEALAND':'NZ','SG':'SG','SINGAPORE':'SG',
    'AE':'AE','UAE':'AE','IL':'IL','ISRAEL':'IL','JO':'JO','JORDAN':'JO',
    'QA':'QA','QATAR':'QA','BH':'BH','BAHRAIN':'BH','OM':'OM','OMAN':'OM',
    'LB':'LB','LEBANON':'LB','SY':'SY','SYRIA':'SY','IQ':'IQ','IRAQ':'IQ',
    'IR':'IR','IRAN':'IR','AF':'AF','AFGHANISTAN':'AF','YE':'YE','YEMEN':'YE',
    'US':'US','UNITED STATES':'US','USA':'US',
}

def norm_country(c):
    c = c.strip().upper()
    if len(c) == 2 and c in ISO2_TO_ISO3:
        return c
    return COUNTRY_TO_ISO.get(c, '')

# Build list of ISO3 codes to download
needed = set()
for country, count in country_counts:
    cc = norm_country(country)
    iso3 = ISO2_TO_ISO3.get(cc)
    if iso3:
        needed.add(iso3)

print(f"Countries with churches: {len(country_counts)}")
print(f"Mapped to ISO3: {len(needed)}")

# For each country, check what levels are available and download missing ones
downloaded = 0
skipped = 0
failed = 0

for iso3 in sorted(needed):
    for level in [0, 1, 2]:
        out_name = f"geoBoundaries-{iso3}-ADM{level}.geojson"
        out_path = os.path.join(BASE_DIR, out_name)
        
        if os.path.exists(out_path):
            skipped += 1
            continue
        
        # Check if available via API
        api_url = f"https://www.geoboundaries.org/api/current/gbOpen/{iso3}/ADM{level}/"
        try:
            meta = json.loads(urllib.request.urlopen(api_url + '?', timeout=10).read())
        except:
            failed += 1
            continue
        
        geojson_url = meta.get('simplifiedGeometryGeoJSON') or meta.get('gjDownloadURL')
        if not geojson_url:
            continue  # Level not available for this country
        
        try:
            print(f"  {iso3} ADM{level}: downloading...", end=' ', flush=True)
            urllib.request.urlretrieve(geojson_url, out_path)
            size_kb = os.path.getsize(out_path) // 1024
            print(f"OK ({size_kb}KB)")
            downloaded += 1
            time.sleep(0.3)
        except Exception as e:
            print(f"FAILED: {e}")
            failed += 1
            if os.path.exists(out_path):
                os.remove(out_path)

print(f"\nDownloaded: {downloaded} | Skipped: {skipped} | Failed/NA: {failed}")
db.close()
