"""Fix messy tradition values left by deepseek global scan."""
import sqlite3
conn = sqlite3.connect(r"E:\grid\churches.db")
c = conn.cursor()

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

# Show messy traditions
c.execute(f"SELECT tradition, COUNT(*) FROM churches WHERE faith='Judaism' AND country IN ({placeholders}) AND tradition NOT IN ('Orthodox','Sephardic','Rabbinic','Conservative','Reform','Chabad','Chabad-Lubavitch (Orthodox)','Orthodox (Chabad)','Progressive','Reconstructionist','Humanistic','Karaite','Orthodox (Yeshiva)','Orthodox (Hasidic)','Sephardic','Mizrahi','Orthodox Union') AND tradition != '' GROUP BY tradition ORDER BY COUNT(*) DESC", all_countries)
rows = c.fetchall()
print(f"Messy traditions to fix ({len(rows)} variants):")
for r in rows:
    # show first example
    c.execute(f"SELECT id, name, country FROM churches WHERE faith='Judaism' AND country IN ({placeholders}) AND tradition=? LIMIT 1", all_countries + [r[0]])
    ex = c.fetchone()
    print(f"  '{r[0]}': {r[1]:>4} entries (e.g. #{ex[0]} {str(ex[1] or '')[:40]} {ex[2]})")

# Fix the messy ones
fixes = {
    'Jewish': 'Rabbinic',
    'Jewish (likely Liberal/Reform)': 'Reform',
    'Jewish (likely Orthodox)': 'Orthodox',
    'Jewish (likely Sephardic or Mizrahi)': 'Sephardic',
    'Hebrew': 'Rabbinic',
    'Secular/Cultural': 'Humanistic',
    'Secular': 'Humanistic',
}

for old, new in fixes.items():
    c.execute(f"SELECT id, tradition FROM churches WHERE faith='Judaism' AND country IN ({placeholders}) AND tradition=?", all_countries + [old])
    rows = c.fetchall()
    for row in rows:
        c.execute("UPDATE churches SET tradition=? WHERE id=?", (new, row[0]))
        c.execute("INSERT INTO enrichment_change_log (church_id, field_name, old_value, new_value, change_source) VALUES (?, 'tradition', ?, ?, 'deepseek_global_cleanup')",
                  (row[0], old, new))
    if rows:
        print(f"\nFixed {len(rows)}: '{old}' -> '{new}'")
    conn.commit()

# Messianic entries should be Christian, not Jewish
c.execute(f"SELECT id, name, country, landmark_type FROM churches WHERE faith='Judaism' AND country IN ({placeholders}) AND tradition='Messianic'", all_countries)
rows = c.fetchall()
for row in rows:
    c.execute("UPDATE churches SET faith='Christian', tradition='Messianic', landmark_type='church' WHERE id=?", (row[0],))
    c.execute("INSERT INTO enrichment_change_log (church_id, field_name, old_value, new_value, change_source) VALUES (?, 'faith', 'Judaism', 'Christian', 'deepseek_global_cleanup')", (row[0],))
    c.execute("INSERT INTO enrichment_change_log (church_id, field_name, old_value, new_value, change_source) VALUES (?, 'landmark_type', ?, 'church', 'deepseek_global_cleanup')", (row[0], row[3] or ''))
if rows:
    print(f"\nMoved {len(rows)} Messianic entries to Christian")
    conn.commit()

# Final tradition distribution
c.execute(f"SELECT tradition, COUNT(*) FROM churches WHERE faith='Judaism' AND country IN ({placeholders}) GROUP BY tradition ORDER BY COUNT(*) DESC", all_countries)
print(f"\nFinal tradition distribution:")
for r in c.fetchall():
    print(f"  {r[0] or 'NULL':30s} {r[1]:>5,}")

c.execute(f"SELECT COUNT(*) FROM churches WHERE faith='Judaism' AND country IN ({placeholders})", all_countries)
print(f"\nTotal Judaism in these regions: {c.fetchone()[0]:,}")

conn.close()
