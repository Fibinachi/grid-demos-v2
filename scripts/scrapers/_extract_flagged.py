"""
Extract exact flagged rowids for Category A fix.
"""
import sqlite3

DB = r'E:\grid\churches.db'
db = sqlite3.connect(DB)
c = db.cursor()

# Christian denominations that should never be Jewish
CHRISTIAN_DENOMS = [
    'BAPTIST', 'METHODIST', 'LUTHERAN', 'PRESBYTERIAN', 'ANGLICAN',
    'EPISCOPAL', 'PENTECOSTAL', 'CHRISTIAN', 'CATHOLIC', 'CONGREGATIONAL',
    'CHRISTIAN & MISSIONARY ALLIANCE', 'CHRISTIAN AND MISSIONARY ALLIANCE',
    'CHRISTIAN CHURCH', 'CHURCH OF CHRIST', 'CHURCH OF GOD',
    'UNITED METHODIST', 'SOUTHERN BAPTIST', 'ASSEMBLIES OF GOD',
    'NAZARENE', 'DISCIPLES OF CHRIST', 'EVANGELICAL FREE',
    'FOURSQUARE', 'MENNONITE', 'BRETHREN', 'SALVATION ARMY',
    'FRIENDS', 'MORAVIAN', 'REFORMED', 'WESLEYAN',
    'ADVENTIST', 'SEVENTH-DAY ADVENTIST', 'CHURCHES OF CHRIST',
    'NON-DENOMINATIONAL', 'NON DENOMINATIONAL', 'INDEPENDENT',
    'INTERDENOMINATIONAL', 'MISSIONARY CHURCH',
    'CHRISTIAN MISSIONARY ALLIANCE',
]

# Christ/Jesus-related keywords
JESUS_KEYWORDS = ['CHRIST', 'JESUS', 'MESSIAH']
JEHOVAH_KEYWORDS = ['JEHOVAH']
CALVARY_KEYWORDS = ['CALVARY']
MORMON_KEYWORDS = ['MORMON', 'LDS', 'LATTER-DAY SAINTS', 'LATTER DAY SAINTS']

all_flagged = []

print("=== A1: Christian denomination in denomination field ===")
rows = c.execute("""
    SELECT rowid, name, city, state, faith, faith_tradition, denomination
    FROM churches
    WHERE country = 'US' AND faith = 'Jewish'
    AND denomination IS NOT NULL AND denomination != ''
""").fetchall()

a1 = []
for r in rows:
    denom_upper = r[6].strip().upper()
    if denom_upper in [d.upper() for d in CHRISTIAN_DENOMS]:
        a1.append(r)
        print(f"  rowid={r[0]:>7} {r[1][:55].strip():<55} {str(r[2] or ''):<15} {str(r[3] or ''):<2} denom={r[6]}")

print(f"\nA1 total: {len(a1)}")
all_flagged.extend([r[0] for r in a1])

print("\n=== A2: Christ/Jesus in name (non-A1) ===")
christian_nondenom_ids = [r[0] for r in a1]
placeholders = ','.join('?' for _ in christian_nondenom_ids) if christian_nondenom_ids else '0'

rows = c.execute(f"""
    SELECT rowid, name, city, state, faith, faith_tradition, denomination
    FROM churches
    WHERE country = 'US' AND faith = 'Jewish'
    AND rowid NOT IN ({placeholders})
""", christian_nondenom_ids).fetchall()

a2, a3, a4, a5, a6 = [], [], [], [], []
for r in rows:
    name_upper = r[1].strip().upper() if r[1] else ''
    
    # A6: Mormon
    if any(w in name_upper for w in MORMON_KEYWORDS):
        a6.append(r)
        print(f"  A6 rowid={r[0]:>7} {r[1][:55].strip():<55} {str(r[2] or ''):<15} {str(r[3] or ''):<2}")
        continue
    
    # A3: Jehovah
    if any(w in name_upper for w in JEHOVAH_KEYWORDS):
        a3.append(r)
        print(f"  A3 rowid={r[0]:>7} {r[1][:55].strip():<55} {str(r[2] or ''):<15} {str(r[3] or ''):<2}")
        continue
    
    # A4: Calvary (non-messianic)
    if any(w in name_upper for w in CALVARY_KEYWORDS) and 'CALVARY CHAPEL' not in name_upper:
        a4.append(r)
        print(f"  A4 rowid={r[0]:>7} {r[1][:55].strip():<55} {str(r[2] or ''):<15} {str(r[3] or ''):<2}")
        continue
    
    # A5: Non-Denominational + Christ
    if ('NON-DENOMINATIONAL' in name_upper or 'NON DENOMINATIONAL' in name_upper):
        a5.append(r)
        print(f"  A5 rowid={r[0]:>7} {r[1][:55].strip():<55} {str(r[2] or ''):<15} {str(r[3] or ''):<2}")
        continue
    
    # A2: Christ/Jesus in name
    if any(w in name_upper for w in JESUS_KEYWORDS):
        a2.append(r)
        print(f"  A2 rowid={r[0]:>7} {r[1][:55].strip():<55} {str(r[2] or ''):<15} {str(r[3] or ''):<2}")
        continue

print(f"\nA2 (Christ/Jesus name): {len(a2)}")
print(f"A3 (Jehovah): {len(a3)}")
print(f"A4 (Calvary non-messianic): {len(a4)}")
print(f"A5 (Non-Denom+Christ): {len(a5)}")
print(f"A6 (Mormon): {len(a6)}")

all_flagged.extend([r[0] for r in a2])
all_flagged.extend([r[0] for r in a3])
all_flagged.extend([r[0] for r in a4])
all_flagged.extend([r[0] for r in a5])
all_flagged.extend([r[0] for r in a6])

print(f"\n=== TOTAL FLAGGED: {len(all_flagged)} ===")
print(f"Rowids: {all_flagged}")
print(f"\nPython list:")
print(f"FLAGGED_ROWIDS = {all_flagged}")

db.close()
