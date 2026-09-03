"""
Check state of Category A flagged records - how many still need fixing.
Counts all Category A records (Christian false positives wrongly tagged Jewish).
"""
import sqlite3

DB = r'E:\grid\churches.db'
db = sqlite3.connect(DB)
c = db.cursor()

# The 25 dupe rowids confirmed earlier
DUPE_ROWIDS = [530702, 560691, 691629, 808542, 809793, 255377, 112013, 599571,
               744282, 526421, 687783, 419785, 622301, 711973, 532207, 690472,
               647561, 779295, 798597, 463685, 655885, 717033, 580193, 695540, 398260]

# Check dupes
placeholders = ','.join('?' for _ in DUPE_ROWIDS)
rows = c.execute(f"""
    SELECT rowid, name, city, state, faith, faith_tradition, denomination, source
    FROM churches
    WHERE rowid IN ({placeholders})
    AND faith = 'Jewish'
""", DUPE_ROWIDS).fetchall()

print(f"=== 25 Dupe Records: {len(rows)} still Jewish ===")
for r in rows:
    print(f"  rowid={r[0]:>7} {str(r[1])[:55].strip():<55} {str(r[2] or ''):<15} {str(r[3] or ''):<2} ft={r[5]} denom={r[6]} src={r[7]}")

# Now get full Category A count using prudent criteria
# A1: Clear Christian denominations
print("\n=== Category A1: Christian Denomination ===")
rows = c.execute("""
    SELECT rowid, name, city, state, faith, faith_tradition, denomination, landmark_type
    FROM churches
    WHERE country = 'US' AND faith = 'Jewish'
    AND UPPER(denomination) IN (
        'BAPTIST', 'METHODIST', 'LUTHERAN', 'PRESBYTERIAN', 'ANGLICAN',
        'EPISCOPAL', 'PENTECOSTAL', 'CATHOLIC', 'CONGREGATIONAL',
        'CHRISTIAN & MISSIONARY ALLIANCE', 'CHRISTIAN AND MISSIONARY ALLIANCE',
        'CHRISTIAN CHURCH', 'CHURCH OF CHRIST', 'CHURCH OF GOD',
        'UNITED METHODIST', 'SOUTHERN BAPTIST', 'ASSEMBLIES OF GOD',
        'NAZARENE', 'DISCIPLES OF CHRIST', 'EVANGELICAL FREE',
        'FOURSQUARE', 'MENNONITE', 'BRETHREN', 'SALVATION ARMY',
        'FRIENDS', 'MORAVIAN', 'REFORMED', 'WESLEYAN',
        'ADVENTIST', 'SEVENTH-DAY ADVENTIST', 'CHURCHES OF CHRIST',
        'CHRISTIAN MISSIONARY ALLIANCE',
        'MISSIONARY CHURCH', 'WESLEYAN CHURCH', 'FREE METHODIST',
        'EVANGELICAL COVENANT', 'EVANGELICAL CHURCH'
    )
""").fetchall()

a1_ids = set()
for r in rows:
    a1_ids.add(r[0])
print(f"A1: {len(rows)}")

# A2: Christ/Jesus in name (excluding Messianic/Beth/Corpus Christi city noise)
print("\n=== Category A2: Christ/Jesus in Name (excluding Beth Messiah, Corpus Christi, etc.) ===")
a1_placeholders = ','.join('?' for _ in a1_ids) if a1_ids else '0'
rows = c.execute(f"""
    SELECT rowid, name, city, state, faith, faith_tradition, denomination
    FROM churches
    WHERE country = 'US' AND faith = 'Jewish'
    AND rowid NOT IN ({a1_placeholders})
""", list(a1_ids)).fetchall()

# Smart filtering
a2_ids = set()
for r in rows:
    name_upper = str(r[1]).upper().strip() if r[1] else ''
    city_upper = str(r[2]).upper().strip() if r[2] else ''
    
    # Skip if 'Corpus Christi' is the CITY, not the name
    if 'CORPUS CHRISTI' in name_upper and city_upper == 'CORPUS CHRISTI':
        continue
    
    has_christ = any(w in name_upper for w in [
        'CHRIST', 'JESUS', 'JEHOVAH', 'CALVARY', 'MORMON', 'LDS',
        'LATTER-DAY', 'LATTER DAY',
    ])
    if has_christ:
        a2_ids.add(r[0])

print(f"A2: {len(a2_ids)}")

total = len(a1_ids) + len(a2_ids)
print(f"\n=== TOTAL Category A records still Jewish: {total} ===")

# Check what percentage of dupe rowids are in this set
dupe_in_cat_a = set(DUPE_ROWIDS) & (a1_ids | a2_ids)
print(f"Dupes in Category A: {len(dupe_in_cat_a)} of {len(DUPE_ROWIDS)}")
print(f"Dupe rowids in Category A: {sorted(dupe_in_cat_a)}")

db.close()
