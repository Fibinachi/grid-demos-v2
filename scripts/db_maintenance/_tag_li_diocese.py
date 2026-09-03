import sqlite3
from datetime import datetime, timezone
conn = sqlite3.connect('E:/grid/churches.db')
c = conn.cursor()
c.execute("SELECT rowid FROM churches WHERE country='LI'")
ids = [r[0] for r in c.fetchall()]
for rid in ids:
    c.execute("SELECT church_id FROM church_enrichment WHERE church_id=?", (rid,))
    if c.fetchone():
        c.execute("UPDATE church_enrichment SET diocese='Archdiocese of Vaduz' WHERE church_id=?", (rid,))
    else:
        c.execute("INSERT INTO church_enrichment (church_id, diocese) VALUES (?, 'Archdiocese of Vaduz')", (rid,))
c.execute("""INSERT INTO provenance_log(source,script_name,started_at,completed_at,churches_updated,fields_populated,status,notes)
    VALUES(?,?,?,?,?,?,?,?)""",
    ("manual","tag_li_diocese.py",datetime.now(timezone.utc).isoformat(),
     datetime.now(timezone.utc).isoformat(),len(ids),"diocese","completed",
     f"LI: {len(ids)} records tagged Archdiocese of Vaduz"))
conn.commit()
print(f"Tagged {len(ids)} LI records")
conn.close()
