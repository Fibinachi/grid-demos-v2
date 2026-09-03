"""Tag Foursquare Gospel with CFTLM: Christian/Christian/Pentecostal/Foursquare Gospel."""
import sqlite3

DB = "E:/grid/churches.db"
db = sqlite3.connect(DB)
db.row_factory = sqlite3.Row

# PH
db.execute("""UPDATE churches SET tradition='Pentecostal', legacy='Foursquare Gospel'
    WHERE country='PH' AND name LIKE '%Foursquare%' AND landmark_type!='data_artifact'""")
ph = db.execute("SELECT COUNT(*) FROM churches WHERE country='PH' AND legacy='Foursquare Gospel'").fetchone()[0]

# Worldwide
db.execute("""UPDATE churches SET tradition=COALESCE(tradition,'Pentecostal'), legacy='Foursquare Gospel'
    WHERE name LIKE '%Foursquare%' AND legacy IS NULL""")
world = db.execute("SELECT COUNT(*) FROM churches WHERE legacy='Foursquare Gospel'").fetchone()[0]

db.commit()

# Verify
c = db.execute("SELECT faith,tradition,legacy,COUNT(*) FROM churches WHERE legacy='Foursquare Gospel' GROUP BY 1,2,3")
for r in c.fetchall():
    print(f"  {str(r[0]):15s} {str(r[1]):15s} {str(r[2]):20s} => {r[3]:,}")

print(f"\nPH: {ph:,} | Worldwide: {world:,}")
print("CFTLM: Christian → Christian → Pentecostal → Foursquare Gospel")
db.close()
