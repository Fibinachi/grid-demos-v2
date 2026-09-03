import sqlite3
db = sqlite3.connect('E:/grid/churches.db')
db.execute("""
    INSERT INTO provenance_log(source, script_name, started_at, completed_at,
        churches_updated, status, notes)
    VALUES ('schema_normalize', 'normalize_crm_tables',
        datetime('now'), datetime('now'), 0, 'completed',
        'Split churches 256-col mega-table into core 50 cols + church_contacts(30cols,801K) + church_operations(47cols,384K) + church_enrichment(132cols,413K). Dropped 203 redundant columns.')
""")
db.commit()
# Show recent provenance
for r in db.execute("SELECT source, script_name, completed_at, status FROM provenance_log ORDER BY rowid DESC LIMIT 5"):
    print(f"  {r[0]:25s} {r[1]:30s} {r[2]} {r[3]}")
db.close()
print("Logged.")
