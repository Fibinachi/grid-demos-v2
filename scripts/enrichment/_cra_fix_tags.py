import sqlite3, pandas as pd

# Fix the tagging — only mark truly closed (BN not in 2018 CSV at all)
df2018 = pd.read_csv('E:/grid/data/cra/cra_2018_identification.csv', 
                     encoding='utf-8', usecols=['BN'])
bns_2018_all = set(df2018['BN'].dropna())

db = sqlite3.connect('E:/grid/churches.db')

# Clear overbroad tags
db.execute("UPDATE churches SET notes = REPLACE(notes, '; likely_closed_cra_2011_only', '') WHERE source='cra_2011'")
db.execute("UPDATE churches SET notes = REPLACE(notes, 'likely_closed_cra_2011_only', '') WHERE source='cra_2011'")
db.execute("UPDATE churches SET notes = NULL WHERE notes = '' AND source='cra_2011'")
print("Cleared old tags")

# Tag truly closed
cra2011 = db.execute("SELECT id, cra_bn FROM churches WHERE source='cra_2011' AND cra_bn IS NOT NULL").fetchall()
tagged = 0
for cid, bn in cra2011:
    if bn not in bns_2018_all:
        db.execute("UPDATE churches SET notes = COALESCE(notes || '; ', '') || 'likely_closed_cra_2011_only' WHERE id = ?", (cid,))
        tagged += 1

db.commit()
print(f"Tagged {tagged} churches as truly closed (BN not in 2018 CSV)")

# Verify
verify = db.execute("SELECT COUNT(*) FROM churches WHERE source='cra_2011' AND notes LIKE '%likely_closed%'").fetchone()[0]
print(f"Verified: {verify} churches tagged")
db.close()
