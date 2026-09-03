"""Fix last remaining messy tradition."""
import sqlite3
conn = sqlite3.connect(r"E:\grid\churches.db")
c = conn.cursor()

# Fix the last one
c.execute("SELECT id, tradition FROM churches WHERE tradition='Jewish (likely Orthodox or Sephardic)'")
row = c.fetchone()
if row:
    # Check what kind of name it is
    c.execute("SELECT name, city, country, landmark_type FROM churches WHERE id=?", (row[0],))
    info = c.fetchone()
    print(f"Fixing #{row[0]}: {info[0]}, {info[1]}, {info[2]} | type={info[3]}")
    # Use Sephardic for Brazil (likely)
    c.execute("UPDATE churches SET tradition='Sephardic' WHERE id=?", (row[0],))
    c.execute("INSERT INTO enrichment_change_log (church_id, field_name, old_value, new_value, change_source) VALUES (?, 'tradition', ?, 'Sephardic', 'deepseek_global_cleanup')",
              (row[0], row[1]))
    conn.commit()
    print("  -> Sephardic")

# Verify no more messy traditions
all_countries = [
    'AR','Argentina','BO','Bolivia','BR','Brazil','CL','Chile','CO','Colombia',
    'EC','Ecuador','GY','Guyana','PY','Paraguay','PE','Peru','SR','Suriname',
    'UY','Uruguay','VE','Venezuela','GF','French Guiana','FK','Falkland Islands',
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
    'AU','Australia','NZ','New Zealand','PG','Papua New Guinea','FJ','Fiji',
    'SB','Solomon Islands','VU','Vanuatu','WS','Samoa','TO','Tonga',
    'FM','Micronesia','MH','Marshall Islands','PW','Palau','KI','Kiribati',
    'TV','Tuvalu','NR','Nauru','NC','New Caledonia','PF','French Polynesia',
    'CK','Cook Islands','WF','Wallis and Futuna','AS','American Samoa',
    'GU','Guam','MP','Northern Mariana Islands','TL','Timor-Leste',
    'CI'
]
placeholders = ','.join('?' for _ in all_countries)
c.execute(f"SELECT tradition, COUNT(*) FROM churches WHERE faith='Judaism' AND country IN ({placeholders}) AND tradition NOT IN ('Orthodox','Sephardic','Rabbinic','Conservative','Reform','Chabad','Chabad-Lubavitch (Orthodox)','Orthodox (Chabad)','Progressive','Reconstructionist','Humanistic','Karaite','Orthodox (Yeshiva)','Orthodox (Hasidic)','Mizrahi','Orthodox Union','') AND tradition != '' GROUP BY tradition ORDER BY COUNT(*) DESC", all_countries)
remaining = c.fetchall()
if remaining:
    print(f"\nStill messy traditions:")
    for r in remaining:
        print(f"  '{r[0]}': {r[1]}")
else:
    print(f"\nAll traditions clean!")

c.execute(f"SELECT COUNT(*) FROM churches WHERE faith='Judaism' AND country IN ({placeholders}) AND (landmark_type IS NULL OR landmark_type IN ('','church','chapel','cathedral','mosque','abbey','shrine'))", all_countries)
print(f"Problematic landmark_types: {c.fetchone()[0]}")

conn.close()
