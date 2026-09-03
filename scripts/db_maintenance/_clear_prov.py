import sqlite3
db = sqlite3.connect('E:/grid/churches.db')
cnt = db.execute("SELECT COUNT(*) FROM provenance_log WHERE source LIKE 'wikidata_%'").fetchone()[0]
print(f"Stale provenance: {cnt}")
db.execute("DELETE FROM provenance_log WHERE source LIKE 'wikidata_%'")
db.commit()
print("Cleared.")
db.close()
