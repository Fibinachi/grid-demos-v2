"""Simple count for grand total of flagged US Jewish records"""
import sqlite3
import sys
db = sqlite3.connect('E:\\grid\\churches.db')

# Break this into smaller queries and add results
CORE = "faith='Jewish' AND (country='US' OR state IS NOT NULL)"

# Get counts for each category separately (they'll have some overlap)
a1 = db.execute(f"""
    SELECT COUNT(DISTINCT rowid) FROM churches WHERE {CORE}
    AND denomination IN ('Pentecostal Assemblies of the World','Pentecostal Church of God',
    'Seventh-day Adventist','Seventh-day Adventist Church','Southern Baptist Convention',
    'Church of God in Christ','Church of God (Holiness)','Wesleyan Church',
    'African Methodist Episcopal Church')
""").fetchone()[0]
print(f"A1 (Christian denom): {a1}")

a2 = db.execute(f"""
    SELECT COUNT(DISTINCT rowid) FROM churches WHERE {CORE}
    AND (UPPER(name) LIKE '%JESUS%' OR UPPER(name) LIKE '%CHRIST%')
    AND UPPER(name) NOT LIKE '%CONGREGATION%'
    AND UPPER(name) NOT LIKE '%CHABAD%'
    AND UPPER(name) NOT LIKE '%BETH %'
    AND UPPER(name) NOT LIKE '%TEMPLE%'
    AND UPPER(name) NOT LIKE '%ISRAEL%'
    AND UPPER(name) NOT LIKE '%JEWISH%'
    AND UPPER(name) NOT LIKE '%SYNAGOGUE%'
""").fetchone()[0]
print(f"A2 (Christ/Jesus in name): {a2}")

a3 = db.execute(f"""
    SELECT COUNT(DISTINCT rowid) FROM churches WHERE {CORE}
    AND UPPER(name) LIKE '%JEHOV%'
""").fetchone()[0]
print(f"A3 (Jehovah): {a3}")

a4 = db.execute(f"""
    SELECT COUNT(DISTINCT rowid) FROM churches WHERE {CORE}
    AND UPPER(name) LIKE '%CALVARY%' AND UPPER(name) NOT LIKE '%MESSIAN%'
""").fetchone()[0]
print(f"A4 (Calvary non-messianic): {a4}")

a5 = db.execute(f"""
    SELECT COUNT(DISTINCT rowid) FROM churches WHERE {CORE}
    AND UPPER(denomination) LIKE '%NON-DENOM%'
    AND (UPPER(name) LIKE '%CHRIST%' OR UPPER(name) LIKE '%JESUS%')
""").fetchone()[0]
print(f"A5 (Non-Denom+Christ): {a5}")

a6 = db.execute(f"""
    SELECT COUNT(DISTINCT rowid) FROM churches WHERE {CORE}
    AND UPPER(name) LIKE '%MORMON%'
""").fetchone()[0]
print(f"A6 (Mormon): {a6}")

print(f"\nSum (has overlap): {a1+a2+a3+a4+a5+a6}")

# Now compute union using a temp table approach
db.execute("CREATE TEMP TABLE IF NOT EXISTS flagged_ids (rowid INTEGER PRIMARY KEY)")
db.execute("DELETE FROM flagged_ids")

for label, cond in [
    ("A1", "denomination IN ('Pentecostal Assemblies of the World','Pentecostal Church of God','Seventh-day Adventist','Seventh-day Adventist Church','Southern Baptist Convention','Church of God in Christ','Church of God (Holiness)','Wesleyan Church','African Methodist Episcopal Church')"),
    ("A2", "(UPPER(name) LIKE '%JESUS%' OR UPPER(name) LIKE '%CHRIST%') AND UPPER(name) NOT LIKE '%CONGREGATION%' AND UPPER(name) NOT LIKE '%CHABAD%' AND UPPER(name) NOT LIKE '%BETH %' AND UPPER(name) NOT LIKE '%TEMPLE%' AND UPPER(name) NOT LIKE '%ISRAEL%' AND UPPER(name) NOT LIKE '%JEWISH%' AND UPPER(name) NOT LIKE '%SYNAGOGUE%'"),
    ("A3", "UPPER(name) LIKE '%JEHOV%'"),
    ("A4", "UPPER(name) LIKE '%CALVARY%' AND UPPER(name) NOT LIKE '%MESSIAN%'"),
    ("A5", "UPPER(denomination) LIKE '%NON-DENOM%' AND (UPPER(name) LIKE '%CHRIST%' OR UPPER(name) LIKE '%JESUS%')"),
    ("A6", "UPPER(name) LIKE '%MORMON%'"),
]:
    db.execute(f"INSERT OR IGNORE INTO flagged_ids SELECT rowid FROM churches WHERE {CORE} AND ({cond})")
    print(f"  After {label}: {db.execute('SELECT COUNT(*) FROM flagged_ids').fetchone()[0]}")

total_distinct = db.execute("SELECT COUNT(*) FROM flagged_ids").fetchone()[0]
print(f"\nTotal DISTINCT flagged records: {total_distinct}")

total_all = db.execute(f"SELECT COUNT(*) FROM churches WHERE {CORE}").fetchone()[0]
print(f"Out of {total_all} US Jewish records ({total_distinct/total_all*100:.1f}%)")

db.close()
