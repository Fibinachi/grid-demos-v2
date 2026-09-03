import sqlite3
from datetime import datetime, timezone

conn = sqlite3.connect('E:/grid/churches.db')
c = conn.cursor()

c.execute("""SELECT rowid, name, denomination FROM churches 
    WHERE country='LI' AND (denomination IS NULL OR denomination = '')""")
rows = c.fetchall()
print(f"{len(rows)} LI records to classify:\n")

fixed = 0
for rowid, name, _ in rows:
    nl = name.lower()
    if any(w in nl for w in ["katholische", "kath", "pfarrkirche", "pfarrei", "pfarramt",
        "st. flori", "st. laurenti", "st. nikolaus", "st. martin", "st. sebastian",
        "st. fridolin", "dux-kappel", "sankt", "kathedrale"]):
        denom = "Roman Catholic"
    elif any(w in nl for w in ["reformierte", "evangelische", "evangelical"]):
        denom = "Protestant"
    else:
        denom = None
    
    if denom:
        c.execute("UPDATE churches SET denomination=? WHERE rowid=?", (denom, rowid))
        fixed += 1
        print(f"  {name[:50]:50s} → {denom}")

# Also tag the mosques
c.execute("UPDATE churches SET denomination='Sunni Islam' WHERE country='LI' AND faith='Islam' AND (denomination IS NULL OR denomination='')")
m_fixed = c.rowcount

# Add city = Vaduz for null cities
c.execute("UPDATE churches SET city='Vaduz' WHERE country='LI' AND (city IS NULL OR city='')")
c_fixed = c.rowcount

# Log
c.execute("""INSERT INTO provenance_log(source,script_name,started_at,completed_at,churches_updated,fields_populated,status,notes)
    VALUES(?,?,?,?,?,?,?,?)""",
    ("manual","classify_li.py",datetime.now(timezone.utc).isoformat(),
     datetime.now(timezone.utc).isoformat(),fixed+m_fixed+c_fixed,
     "denomination,city","completed",f"LI: {fixed} churches + {m_fixed} mosques + {c_fixed} cities"))

conn.commit()

c.execute("SELECT name, denomination, city FROM churches WHERE country='LI' ORDER BY faith, denomination")
print(f"\nFinal LI ({c.execute('SELECT COUNT(*) FROM churches WHERE country=?',('LI',)).fetchone()[0]} records):")
for r in c.fetchall():
    print(f"  {r[0][:45]:45s} | {str(r[1]):20s} | {r[2]}")
conn.close()
print(f"\nDone: {fixed} denominations + {m_fixed} mosque tags + {c_fixed} cities")
