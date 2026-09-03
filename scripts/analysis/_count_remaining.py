import sqlite3

db = sqlite3.connect(r'E:\grid\churches.db')

checks = [
    ("ST. remaining", "SELECT COUNT(*) FROM churches WHERE name LIKE '% ST.%'"),
    ("ST (bare) remaining", "SELECT COUNT(*) FROM churches WHERE name LIKE '% ST %' AND name NOT LIKE '% STREET %' AND name NOT LIKE '% ST.%'"),
    ("MT. remaining", "SELECT COUNT(*) FROM churches WHERE name LIKE '% MT.%'"),
    ("MT (bare) remaining", "SELECT COUNT(*) FROM churches WHERE name LIKE '% MT %' AND name NOT LIKE '% MT.%'"),
    ("FT. remaining", "SELECT COUNT(*) FROM churches WHERE name LIKE '% FT.%'"),
    ("FT (bare) remaining", "SELECT COUNT(*) FROM churches WHERE name LIKE '% FT %' AND name NOT LIKE '% FT.%'"),
    ("CTR remaining", "SELECT COUNT(*) FROM churches WHERE name LIKE '% CTR %'"),
    ("INC/INC. remaining", "SELECT COUNT(*) FROM churches WHERE name LIKE '% INC' OR name LIKE '% INC.'"),
    ("Possessive-S candidates", "SELECT COUNT(*) FROM churches WHERE (name LIKE '% SAINT % S' OR name LIKE 'SAINT % S') AND name NOT LIKE '% INC' AND name NOT LIKE '% INC.'"),
]

for label, sql in checks:
    c = db.execute(sql)
    print(f"{label:40s} {c.fetchone()[0]:>10,}")

db.close()
