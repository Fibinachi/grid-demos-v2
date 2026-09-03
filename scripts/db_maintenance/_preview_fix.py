"""Preview the 216 records to plan faith_tradition mapping"""
import sqlite3
db = sqlite3.connect('E:\\grid\\churches.db')
CORE = "faith='Jewish' AND (country='US' OR state IS NOT NULL)"

# Get all distinct faith_tradition and denomination combos for flagged records
print("=== Current faith_tradition distribution among flagged records ===\n")

categories = [
    ("A1 Christian denom", "denomination IN ('Pentecostal Assemblies of the World','Pentecostal Church of God','Seventh-day Adventist','Seventh-day Adventist Church','Southern Baptist Convention','Church of God in Christ','Church of God (Holiness)','Wesleyan Church','African Methodist Episcopal Church')"),
    ("A2 Christ/Jesus name", "(UPPER(name) LIKE '%JESUS%' OR UPPER(name) LIKE '%CHRIST%') AND UPPER(name) NOT LIKE '%CONGREGATION%' AND UPPER(name) NOT LIKE '%CHABAD%' AND UPPER(name) NOT LIKE '%BETH %' AND UPPER(name) NOT LIKE '%TEMPLE%' AND UPPER(name) NOT LIKE '%ISRAEL%' AND UPPER(name) NOT LIKE '%JEWISH%' AND UPPER(name) NOT LIKE '%SYNAGOGUE%'"),
    ("A3 Jehovah", "UPPER(name) LIKE '%JEHOV%'"),
    ("A4 Calvary non-messianic", "UPPER(name) LIKE '%CALVARY%' AND UPPER(name) NOT LIKE '%MESSIAN%'"),
    ("A5 Non-Denom+Christ", "UPPER(denomination) LIKE '%NON-DENOM%' AND (UPPER(name) LIKE '%CHRIST%' OR UPPER(name) LIKE '%JESUS%')"),
    ("A6 Mormon", "UPPER(name) LIKE '%MORMON%'"),
]

all_flagged = set()
for label, cond in categories:
    rows = db.execute(f"""
        SELECT faith_tradition, COUNT(*) as c 
        FROM churches WHERE {CORE} AND ({cond})
        GROUP BY faith_tradition ORDER BY c DESC
    """).fetchall()
    print(f'\n{label}:')
    for ft, c in rows:
        ft_display = ft or 'NULL'
        print(f'  {ft_display:25s}  {c}')
    
    # Also sample records for A2 to see what names look like
    if label == "A2 Christ/Jesus name":
        print(f'\n  Sample records:')
        samples = db.execute(f"""
            SELECT rowid, name, denomination, faith_tradition
            FROM churches WHERE {CORE} AND ({cond})
            ORDER BY name LIMIT 20
        """).fetchall()
        for r in samples:
            print(f'    {r[0]}: "{r[1][:60]}" denom={r[2] or "NULL":20s} ft={r[3] or "NULL"}')

    # Get rowids for union
    rids = set(r[0] for r in db.execute(f"SELECT rowid FROM churches WHERE {CORE} AND ({cond})").fetchall())
    all_flagged.update(rids)

print(f'\n\nTotal distinct flagged: {len(all_flagged)}')

db.close()
