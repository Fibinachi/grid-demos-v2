"""Extra stats for doc update."""
import sqlite3, os

conn = sqlite3.connect(r"e:\grid\churches.db")
c = conn.cursor()

c.execute("SELECT COUNT(*) FROM enrichment_change_log")
print(f"Enrichment changes logged: {c.fetchone()[0]:,}")

c.execute("SELECT faith, COUNT(*) FROM churches WHERE faith IN ('Hellenism','Roman','Pagan') GROUP BY faith")
for r in c.fetchall():
    print(f"{r[0]}: {r[1]:,}")

c.execute("SELECT COUNT(*) FROM churches WHERE latitude IS NOT NULL AND longitude IS NOT NULL")
print(f"With coordinates: {c.fetchone()[0]:,}")

c.execute("SELECT COUNT(*) FROM churches WHERE country='US' AND denomination LIKE '%Catholic%'")
print(f"US Catholic (any Catholic denom): {c.fetchone()[0]:,}")

c.execute("SELECT COUNT(DISTINCT diocese) FROM church_enrichment WHERE diocese IS NOT NULL")
print(f"Unique diocese values: {c.fetchone()[0]:,}")

c.execute("""
    SELECT COUNT(*) FROM churches c 
    JOIN church_enrichment e ON c.id=e.church_id 
    WHERE c.country='US' AND e.diocese IS NOT NULL
""")
print(f"US churches with diocese: {c.fetchone()[0]:,}")

c.execute("PRAGMA integrity_check")
print(f"Integrity: {c.fetchone()[0]}")

conn.close()

wal = os.path.getsize(r"e:\grid\churches.db-wal") if os.path.exists(r"e:\grid\churches.db-wal") else 0
shm = os.path.getsize(r"e:\grid\churches.db-shm") if os.path.exists(r"e:\grid\churches.db-shm") else 0
print(f"WAL: {wal/1024/1024:.1f} MB")
print(f"SHM: {shm/1024:.1f} KB")

# Honorific temples check
conn2 = sqlite3.connect(r"e:\grid\churches.db")
c2 = conn2.cursor()
c2.execute("SELECT COUNT(*) FROM churches WHERE faith='Hindu' AND country='IN'")
print(f"Hindu temples in India: {c2.fetchone()[0]:,}")
c2.execute("SELECT COUNT(*) FROM churches WHERE faith='Hindu' AND country='IN' AND source='holy_sites_import'")
print(f"  from holy_sites_import: {c2.fetchone()[0]:,}")
conn2.close()
