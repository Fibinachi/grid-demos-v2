import sqlite3
from gw_db import connect, Provenance

conn = connect()
c = conn.cursor()

# Find Antarctic chapels
c.execute("SELECT rowid, id, name, country, faith, denomination FROM churches WHERE latitude < -60 ORDER BY latitude")
chapels = c.fetchall()
print("Antarctic chapels:")
for r in chapels:
    print(f"  rowid={r[0]} id={r[1]} {r[3]:3s} {str(r[2])[:50]} [{r[4]}] {r[5]}")

# Assign hierarchy
# Chapel of the Snows (1307573) -> US Military Archdiocese
# Chapel of Blessed Virgin (1619743, 1890082) -> Rio Gallegos, Argentina  
# Trinity Church (1884100) -> Russian Orthodox, Patriarchate of Moscow

mapping = {
    1307573: {"diocese": "Archdiocese for the Military Services, USA",
              "province": "Military Ordinariate",
              "conference": "United States",
              "rite": "Latin",
              "notes": "Antarctica - McMurdo Station"},
    1619743: {"diocese": "Rio Gallegos",
              "archdiocese": "Bahia Blanca",
              "province": "Bahia Blanca",
              "conference": "Argentina",
              "rite": "Latin", 
              "notes": "Antarctica - Marambio Base"},
    1890082: {"diocese": "Rio Gallegos",
              "archdiocese": "Bahia Blanca", 
              "province": "Bahia Blanca",
              "conference": "Argentina",
              "rite": "Latin",
              "notes": "Antarctica - Marambio Base (duplicate)"},
    1884100: {"diocese": "Patriarchate of Moscow",
              "province": "Moscow Patriarchate",
              "conference": "Russia",
              "rite": "Byzantine",
              "denomination_note": "Russian Orthodox",
              "notes": "Antarctica - King George Island, Trinity Church"},
}

with Provenance(conn, "assign_antarctic_hierarchy.py", source="manual_hierarchy",
                  fields="diocese,province,conference,rite"):
    c2 = conn.cursor()
    for rowid_, fields in mapping.items():
        # Get church_id (may be NULL)
        c2.execute("SELECT id FROM churches WHERE rowid=?", (rowid_,))
        church_id = c2.fetchone()[0]
        
        # Upsert church_enrichment
        c2.execute("SELECT 1 FROM church_enrichment WHERE church_id=?", (church_id or rowid_,))
        exists = c2.fetchone()
        
        if exists:
            c2.execute("""UPDATE church_enrichment SET diocese=?, province=?, conference=?, rite=?, 
                          notes=CASE WHEN notes IS NULL THEN ? ELSE notes || '; ' || ? END,
                          last_updated=datetime('now')
                          WHERE church_id=?""",
                       (fields.get("diocese"), fields.get("province"), fields.get("conference"),
                        fields.get("rite"), fields.get("notes"), fields.get("notes"),
                        church_id or rowid_))
        else:
            c2.execute("""INSERT INTO church_enrichment (church_id, diocese, province, conference, rite, notes, last_updated)
                          VALUES (?,?,?,?,?,?,datetime('now'))""",
                       (church_id or rowid_, fields.get("diocese"), fields.get("province"),
                        fields.get("conference"), fields.get("rite"), fields.get("notes")))
        
        print(f"  {fields['diocese']:45s} <- {str(chapels[0])}")
        
conn.commit()
conn.close()
print("\nDone - Antarctic chapels assigned to their hierarchies.")
