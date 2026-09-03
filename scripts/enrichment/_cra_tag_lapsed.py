import sqlite3, pandas as pd

# Compute diff in pandas
df2018 = pd.read_csv('E:/grid/data/cra/cra_2018_identification.csv',
                     encoding='utf-8', usecols=['BN'])
bns_2018 = set(df2018['BN'].dropna())
print(f"2018 BNs: {len(bns_2018):,}")

db = sqlite3.connect('E:/grid/churches.db')
bns_2011 = set(r[0] for r in db.execute(
    "SELECT cra_bn FROM churches WHERE source='cra_2011' AND cra_bn IS NOT NULL"
).fetchall())
lapsed = bns_2011 - bns_2018
print(f"2011 BNs: {len(bns_2011):,}  Lapsed: {len(lapsed):,}")

# Clear old tags
db.execute("UPDATE churches SET notes = REPLACE(REPLACE(COALESCE(notes,''), 'cra_registration_lapsed_2011_2018', ''), 'likely_closed_cra_2011_only', '') WHERE notes IS NOT NULL")
db.execute("UPDATE churches SET notes = NULL WHERE TRIM(notes, '; ') = ''")

# Batch tag
lapsed_list = list(lapsed)
tagged = 0
for i in range(0, len(lapsed_list), 500):
    chunk = lapsed_list[i:i+500]
    ph = ','.join(['?'] * len(chunk))
    db.execute(f"UPDATE churches SET notes=COALESCE(notes||'; ','')||'cra_registration_lapsed_2011_2018' WHERE source='cra_2011' AND cra_bn IN ({ph})", chunk)
    tagged += db.execute("SELECT changes()").fetchone()[0]
    if i % 2000 == 0:
        print(f"  {i:,}/{len(lapsed_list):,}")

db.commit()
v = db.execute("SELECT COUNT(*) FROM churches WHERE notes LIKE '%lapsed%'").fetchone()[0]
print(f"Tagged: {tagged:,}  Verified: {v:,}")

stats = db.execute("SELECT COUNT(*), SUM(CASE WHEN country='CA' THEN 1 ELSE 0 END), SUM(CASE WHEN source='cra_2011' THEN 1 ELSE 0 END), SUM(CASE WHEN source='cra_2018' THEN 1 ELSE 0 END) FROM churches").fetchone()
print(f"Total: {stats[0]:,} | CA: {stats[1]:,} | CRA 2011: {stats[2]:,} | CRA 2018: {stats[3]:,}")
db.close()
