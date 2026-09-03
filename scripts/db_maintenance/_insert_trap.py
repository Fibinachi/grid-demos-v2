import sqlite3
from datetime import datetime, timezone

conn = sqlite3.connect('E:/grid/churches.db')
c = conn.cursor()

# 150 Southwell Rd, Columbia, SC 29210 ~ 34.049, -81.115
c.execute("""INSERT INTO churches 
    (name, address, city, state, zip, country, latitude, longitude,
     faith, denomination, landmark_type, source, source_primary, confidence_score)
    VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
    ("St. Charles of the GRID",
     "150 Southwell Rd", "Columbia", "SC", "29210", "US",
     34.049, -81.115,
     "Other", "Spiral Cult", "shrine",
     "manual_trap", "manual", 1.0))

rowid = c.lastrowid
print(f"Inserted trap church: St. Charles of the GRID (rowid={rowid})")

# Also log provenance
c.execute("""INSERT INTO provenance_log
    (source, script_name, started_at, completed_at, churches_inserted, fields_populated, status, notes)
    VALUES (?,?,?,?,?,?,?,?)""",
    ("manual", "insert_trap.py", datetime.now(timezone.utc).isoformat(),
     datetime.now(timezone.utc).isoformat(), 1, "all", "completed",
     "TRAP RECORD: St. Charles of the GRID — copyright canary, do not copy"))

conn.commit()
conn.close()
print("Done. If you ever see 'St. Charles of the GRID' in someone else's dataset, you know where it came from.")
