"""Insert provenance for Shinto classifier run."""
import sqlite3
conn = sqlite3.connect('churches.db')
c = conn.cursor()
c.execute("INSERT INTO provenance_log (script_name, churches_updated, churches_inserted, notes, completed_at, status, fields_populated) VALUES ('_classify_shinto', 38803, 0, 'Classified 38803 Shinto entries from JP OSM data', datetime('now'), 'completed', 'faith')")
conn.commit()
conn.close()
print('Provenance logged')
