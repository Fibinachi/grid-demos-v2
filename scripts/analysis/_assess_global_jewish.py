"""Assess Judaism entries in South America, Africa, Australia/Oceania."""
import sqlite3
conn = sqlite3.connect(r"E:\grid\churches.db")
c = conn.cursor()

# South America
sa_countries = [
    'AR','Argentina','BO','Bolivia','BR','Brazil','CL','Chile','CO','Colombia',
    'EC','Ecuador','GY','Guyana','PY','Paraguay','PE','Peru','SR','Suriname',
    'UY','Uruguay','VE','Venezuela','GF','French Guiana','FK','Falkland Islands'
]

# Africa
af_countries = [
    'ZA','South Africa','NG','Nigeria','KE','Kenya','EG','Egypt','MA','Morocco',
    'DZ','Algeria','TN','Tunisia','LY','Libya','SD','Sudan','SS','South Sudan',
    'ET','Ethiopia','ER','Eritrea','GH','Ghana','CI',"Cote d'Ivoire",'SN','Senegal',
    'UG','Uganda','TZ','Tanzania','ZM','Zambia','ZW','Zimbabwe','MW','Malawi',
    'MZ','Mozambique','AO','Angola','NA','Namibia','BW','Botswana','RW','Rwanda',
    'BI','Burundi','CD','DRC','CG','Congo','GA','Gabon','CM','Cameroon',
    'CF','CAR','TD','Chad','NE','Niger','ML','Mali','BF','Burkina Faso',
    'BJ','Benin','TG','Togo','SL','Sierra Leone','LR','Liberia','GN','Guinea',
    'GM','Gambia','MR','Mauritania','CV','Cape Verde','ST','Sao Tome',
    'GQ','Equatorial Guinea','GW','Guinea-Bissau','KM','Comoros','MG','Madagascar',
    'SC','Seychelles','MU','Mauritius','SZ','Eswatini','LS','Lesotho','DJ','Djibouti',
    'SO','Somalia','SH','St Helena','RE','Reunion','YT','Mayotte'
]

# Australia/Oceania
oc_countries = [
    'AU','Australia','NZ','New Zealand','PG','Papua New Guinea','FJ','Fiji',
    'SB','Solomon Islands','VU','Vanuatu','WS','Samoa','TO','Tonga',
    'FM','Micronesia','MH','Marshall Islands','PW','Palau','KI','Kiribati',
    'TV','Tuvalu','NR','Nauru','NC','New Caledonia','PF','French Polynesia',
    'CK','Cook Islands','WF','Wallis and Futuna','AS','American Samoa',
    'GU','Guam','MP','Northern Mariana Islands','TL','Timor-Leste'
]

regions = [
    ("South America", sa_countries),
    ("Africa", af_countries),
    ("Australia/Oceania", oc_countries),
]

grand_total = 0
for region_name, countries in regions:
    placeholders = ','.join('?' for _ in countries)
    c.execute(f"SELECT COUNT(*) FROM churches WHERE faith='Judaism' AND country IN ({placeholders})", countries)
    total = c.fetchone()[0]
    grand_total += total
    print(f"\n{'='*60}")
    print(f"=== {region_name}: {total:,} entries ===")
    print(f"{'='*60}")
    
    if total == 0:
        continue
    
    # By country
    c.execute(f"SELECT country, COUNT(*) FROM churches WHERE faith='Judaism' AND country IN ({placeholders}) GROUP BY country ORDER BY COUNT(*) DESC", countries)
    print(f"\n  By country:")
    for r in c.fetchall():
        print(f"    {r[0]:25s} {r[1]:>6,}")
    
    # By landmark_type
    c.execute(f"SELECT COALESCE(landmark_type,'NULL'), COUNT(*) FROM churches WHERE faith='Judaism' AND country IN ({placeholders}) GROUP BY landmark_type ORDER BY COUNT(*) DESC", countries)
    print(f"\n  By landmark_type:")
    for r in c.fetchall():
        marker = "  PROBLEM" if r[0] in ('church','chapel','cathedral','mosque','abbey','shrine','NULL','') else ""
        print(f"    {r[0]:25s} {r[1]:>6,}{marker}")
    
    # Problematic
    c.execute(f"SELECT COUNT(*) FROM churches WHERE faith='Judaism' AND country IN ({placeholders}) AND (landmark_type IS NULL OR landmark_type IN ('','church','chapel','cathedral','mosque','abbey','shrine'))", countries)
    prob = c.fetchone()[0]
    print(f"\n  Problematic (NULL/church/etc): {prob}")
    if prob > 0:
        c.execute(f"SELECT id, name, city, country, landmark_type FROM churches WHERE faith='Judaism' AND country IN ({placeholders}) AND (landmark_type IS NULL OR landmark_type IN ('','church','chapel','cathedral','mosque','abbey','shrine')) ORDER BY country, name LIMIT 30", countries)
        for r in c.fetchall():
            print(f"    #{r[0]:>8} {str(r[1] or '')[:40]:40s} {str(r[2] or '')[:20]:20s} {str(r[3] or '')[:12]:12s} type={r[4]}")

print(f"\n\nGrand total: {grand_total:,}")
conn.close()
