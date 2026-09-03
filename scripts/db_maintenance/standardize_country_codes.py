"""Complete country code standardization to ISO 3166-1 alpha-2."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from gw_db import connect

db = connect()
cur = db.cursor()

FULL_MAP = {
    "Nigeria":"NG","South Africa":"ZA","Algeria":"DZ","Ireland":"IE",
    "Kenya":"KE","Egypt":"EG","Ghana":"GH","Italy":"IT",
    "United Kingdom":"GB","France":"FR","Canada":"CA","Malaysia":"MY",
    "Uganda":"UG","Ivory Coast":"CI","Democratic Republic of the Congo":"CD",
    "Mexico":"MX","Zambia":"ZM","Spain":"ES","Morocco":"MA",
    "Poland":"PL","Zimbabwe":"ZW","Turkey":"TR","Germany":"DE",
    "Netherlands":"NL","Tanzania":"TZ","Tunisia":"TN","Mauritius":"MU",
    "Romania":"RO","Iran":"IR","Ethiopia":"ET","Mozambique":"MZ",
    "Cameroon":"CM","India":"IN","Estonia":"EE","Angola":"AO",
    "Botswana":"BW","Russia":"RU","Malawi":"MW","Hungary":"HU",
    "Czechia":"CZ","Greece":"GR","Libya":"LY","Philippines":"PH",
    "Indonesia":"ID","Liberia":"LR","Namibia":"NA","Austria":"AT",
    "Portugal":"PT","Slovenia":"SI","Belgium":"BE",
    "Bosnia and Herzegovina":"BA","Madagascar":"MG","Malta":"MT",
    "Sweden":"SE","North Macedonia":"MK","Benin":"BJ","Croatia":"HR",
    "Bulgaria":"BG","China":"CN","Ukraine":"UA","Israel":"IL",
    "Iraq":"IQ","Togo":"TG","Burkina Faso":"BF","Saudi Arabia":"SA",
    "Senegal":"SN","Syria":"SY","Brazil":"BR","Slovakia":"SK",
    "Sierra Leone":"SL","Gabon":"GA","Bangladesh":"BD","Eswatini":"SZ",
    "Switzerland":"CH","Argentina":"AR","Congo-Brazzaville":"CG",
    "Norway":"NO","Czech Republic":"CZ","Lithuania":"LT","Burundi":"BI",
    "Mali":"ML","Lesotho":"LS","Palestinian Territories":"PS",
    "Chile":"CL","Sudan":"SD","Uzbekistan":"UZ","Denmark":"DK",
    "Rwanda":"RW","Singapore":"SG","Pakistan":"PK","Serbia":"RS",
    "Albania":"AL","Colombia":"CO","Azerbaijan":"AZ","Latvia":"LV",
    "South Sudan":"SS","Finland":"FI","Thailand":"TH","Venezuela":"VE",
    "Peru":"PE","Yemen":"YE","Israel/Palestine":"PS","Japan":"JP",
    "Kosovo":"XK","Niger":"NE","Cape Verde":"CV","Cyprus":"CY",
    "Belarus":"BY","Jordan":"JO","Montenegro":"ME","The Gambia":"GM",
    "Armenia":"AM","Kazakhstan":"KZ","Afghanistan":"AF","Cambodia":"KH",
    "Lebanon":"LB","Chad":"TD","Georgia":"GE","Somalia":"SO",
    "Vietnam":"VN","Central African Republic":"CF","Guatemala":"GT",
    "Taiwan":"TW","United Arab Emirates":"AE","Uruguay":"UY",
    "Eritrea":"ER","Bolivia":"BO","Ecuador":"EC","Iceland":"IS",
    "Mauritania":"MR","South Korea":"KR","Equatorial Guinea":"GQ",
    "Guinea-Bissau":"GW","New Zealand":"NZ","Honduras":"HN","Kuwait":"KW",
    "Bahrain":"BH","El Salvador":"SV","Maldives":"MV","Seychelles":"SC",
    "Sri Lanka":"LK","Turkmenistan":"TM","Brunei":"BN","Cuba":"CU",
    "Greenland":"GL","Laos":"LA","Myanmar":"MM","Nicaragua":"NI",
    "Oman":"OM","Somaliland":"SO","Comoros":"KM",
    "Dominican Republic":"DO","East Timor":"TL","Haiti":"HT",
    "Luxembourg":"LU","Moldova":"MD","Paraguay":"PY","San Marino":"SM",
    "Tajikistan":"TJ","Trinidad and Tobago":"TT","Vatican City":"VA",
    "Djibouti":"DJ","Falkland Islands":"FK","Faroe Islands":"FO",
    "Fiji":"FJ","Guinea":"GN","Guyana":"GY","Kyrgyzstan":"KG",
    "Monaco":"MC","Mongolia":"MN","Nepal":"NP","Papua New Guinea":"PG",
    "Qatar":"QA","Suriname":"SR","Sao Tome and Principe":"ST",
    "Vanuatu":"VU",
}

# Also handle NULL mappings
NULL_MAP = {"unknown": None, "": None, "38000": None}

print(f"Fixing {len(FULL_MAP)} full-name + {len(NULL_MAP)} null patterns...")
now = __import__('datetime').datetime.now().isoformat()
fixed = 0

for bad_val, iso_code in {**FULL_MAP, **NULL_MAP}.items():
    if iso_code is None:
        cur.execute("UPDATE churches SET country=NULL, last_updated=? WHERE country=?", (now, bad_val))
    else:
        cur.execute("UPDATE churches SET country=?, last_updated=? WHERE country=?", (iso_code, now, bad_val))
    n = cur.rowcount
    fixed += n
    if n > 0:
        print(f"  {bad_val:40s} -> {iso_code or 'NULL':4s}  ({n:,} rows)")

db.commit()

# Verify
cur.execute("""
    SELECT COUNT(*) FROM churches
    WHERE country IS NOT NULL 
      AND (length(country) != 2 OR country != upper(country) OR country GLOB '*[^A-Z]*')
""")
remaining = cur.fetchone()[0]
print(f"\nTotal fixed: {fixed:,}")
print(f"Remaining non-standard: {remaining:,}")
if remaining:
    cur.execute("SELECT country, COUNT(*) FROM churches WHERE country IS NOT NULL AND (length(country)!=2 OR country!=upper(country) OR country GLOB '*[^A-Z]*') GROUP BY country ORDER BY COUNT(*) DESC")
    for r in cur.fetchall():
        print(f"  STILL BAD: {str(r[0]):40s} {r[1]:>10,}")

db.close()
print("Done.")
