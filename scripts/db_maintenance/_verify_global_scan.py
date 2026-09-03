"""Verify global scan and fix any regressions."""
import sqlite3
conn = sqlite3.connect(r"E:\grid\churches.db")
c = conn.cursor()

all_countries = [
    # South America
    'AR','Argentina','BO','Bolivia','BR','Brazil','CL','Chile','CO','Colombia',
    'EC','Ecuador','GY','Guyana','PY','Paraguay','PE','Peru','SR','Suriname',
    'UY','Uruguay','VE','Venezuela','GF','French Guiana','FK','Falkland Islands',
    # Africa
    'ZA','South Africa','NG','Nigeria','KE','Kenya','EG','Egypt','MA','Morocco',
    'DZ','Algeria','TN','Tunisia','LY','Libya','SD','Sudan','SS','South Sudan',
    'ET','Ethiopia','ER','Eritrea','GH','Ghana','SN','Senegal',
    'UG','Uganda','TZ','Tanzania','ZM','Zambia','ZW','Zimbabwe','MW','Malawi',
    'MZ','Mozambique','AO','Angola','NA','Namibia','BW','Botswana','RW','Rwanda',
    'BI','Burundi','CD','DRC','CG','Congo','GA','Gabon','CM','Cameroon',
    'CF','CAR','TD','Chad','NE','Niger','ML','Mali','BF','Burkina Faso',
    'BJ','Benin','TG','Togo','SL','Sierra Leone','LR','Liberia','GN','Guinea',
    'GM','Gambia','MR','Mauritania','CV','Cape Verde','ST','Sao Tome',
    'GQ','Equatorial Guinea','GW','Guinea-Bissau','KM','Comoros','MG','Madagascar',
    'SC','Seychelles','MU','Mauritius','SZ','Eswatini','LS','Lesotho','DJ','Djibouti',
    'SO','Somalia','SH','St Helena','RE','Reunion','YT','Mayotte',
    # Australia/Oceania
    'AU','Australia','NZ','New Zealand','PG','Papua New Guinea','FJ','Fiji',
    'SB','Solomon Islands','VU','Vanuatu','WS','Samoa','TO','Tonga',
    'FM','Micronesia','MH','Marshall Islands','PW','Palau','KI','Kiribati',
    'TV','Tuvalu','NR','Nauru','NC','New Caledonia','PF','French Polynesia',
    'CK','Cook Islands','WF','Wallis and Futuna','AS','American Samoa',
    'GU','Guam','MP','Northern Mariana Islands','TL','Timor-Leste',
    'CI',"Cote d'Ivoire"
]

placeholders = ','.join('?' for _ in all_countries)

# 1. Check for chabad regression
c.execute(f"SELECT COUNT(*) FROM churches WHERE faith='Judaism' AND country IN ({placeholders}) AND landmark_type='chabad'", all_countries)
n = c.fetchone()[0]
print(f"'chabad' (should be 0): {n}")
if n:
    c.execute(f"UPDATE churches SET landmark_type='chabad_house' WHERE faith='Judaism' AND country IN ({placeholders}) AND landmark_type='chabad'", all_countries)
    print(f"  Fixed: {c.rowcount}")
    conn.commit()

# 2. Check for other normalization issues
for old, new in [('community center', 'community_center'), ('senior home', 'senior_home'), ('temple', 'synagogue'), ('mikvah', 'mikveh')]:
    params = all_countries + [old]
    c.execute(f"SELECT COUNT(*) FROM churches WHERE faith='Judaism' AND country IN ({placeholders}) AND landmark_type=?", params)
    n = c.fetchone()[0]
    if n:
        print(f"'{old}' (should be 0): {n}")
        uparams = [new] + all_countries + [old]
        c.execute(f"UPDATE churches SET landmark_type=? WHERE faith='Judaism' AND country IN ({placeholders}) AND landmark_type=?", uparams)
        print(f"  Fixed: {c.rowcount}")
        conn.commit()

# 3. Final type distribution
c.execute(f"SELECT landmark_type, COUNT(*) FROM churches WHERE faith='Judaism' AND country IN ({placeholders}) GROUP BY landmark_type ORDER BY COUNT(*) DESC", all_countries)
print("\nFinal type distribution:")
for r in c.fetchall():
    print(f"  {r[0] or 'NULL':25s} {r[1]:>5,}")

# 4. Problematic check
c.execute(f"SELECT COUNT(*) FROM churches WHERE faith='Judaism' AND country IN ({placeholders}) AND (landmark_type IS NULL OR landmark_type IN ('','church','chapel','cathedral','mosque','abbey','shrine'))", all_countries)
print(f"\nStill problematic: {c.fetchone()[0]}")

# 5. Tradition distribution
c.execute(f"SELECT tradition, COUNT(*) FROM churches WHERE faith='Judaism' AND country IN ({placeholders}) GROUP BY tradition ORDER BY COUNT(*) DESC", all_countries)
print("\nTradition distribution:")
for r in c.fetchall():
    print(f"  {r[0] or 'NULL':25s} {r[1]:>5,}")

# 6. Verify provenance
c.execute("SELECT COUNT(*) FROM enrichment_change_log WHERE change_source='deepseek_global_scan'")
print(f"\nEnrichment log entries (deepseek_global_scan): {c.fetchone()[0]:,}")

c.execute("SELECT id, notes FROM provenance_log WHERE script_name='scan_global_jewish_deepseek'")
row = c.fetchone()
if row:
    print(f"Provenance log: #{row[0]} - {row[1]}")
else:
    print("Provenance log: NOT FOUND")

conn.close()
