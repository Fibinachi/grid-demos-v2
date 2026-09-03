"""Gather all current stats for documentation update."""
import sqlite3, os

DB = r"e:\grid\churches.db"
conn = sqlite3.connect(DB, timeout=30)
c = conn.cursor()

results = {}

# Total churches
c.execute("SELECT COUNT(*) FROM churches")
results["total"] = c.fetchone()[0]

# Countries
c.execute("SELECT COUNT(DISTINCT country) FROM churches WHERE country IS NOT NULL AND country != ''")
results["countries"] = c.fetchone()[0]

# Denominations
c.execute("SELECT COUNT(DISTINCT denomination) FROM churches WHERE denomination IS NOT NULL AND denomination != ''")
results["denominations"] = c.fetchone()[0]

# Unique faiths
c.execute("SELECT faith, COUNT(*) as cnt FROM churches WHERE faith IS NOT NULL AND faith != '' GROUP BY faith ORDER BY cnt DESC")
results["faiths"] = c.fetchall()

# Top 15 countries
c.execute("SELECT country, COUNT(*) as cnt FROM churches WHERE country IS NOT NULL AND country != '' GROUP BY country ORDER BY cnt DESC LIMIT 15")
results["top_countries"] = c.fetchall()

# Provenance / source distribution
c.execute("SELECT source, COUNT(*) as cnt FROM churches WHERE source IS NOT NULL AND source != '' GROUP BY source ORDER BY cnt DESC LIMIT 15")
results["sources"] = c.fetchall()

# DB file size
size_bytes = os.path.getsize(DB)
wal_path = DB + "-wal"
wal_bytes = os.path.getsize(wal_path) if os.path.exists(wal_path) else 0
results["db_size_mb"] = round(size_bytes / (1024*1024), 1)
results["wal_size_mb"] = round(wal_bytes / (1024*1024), 1)

# Faith totals
print("=== FAITH BREAKDOWN ===")
for row in results["faiths"]:
    print(f"  {(row[0] or 'NULL'):20s} {row[1]:>10,}")

print(f"\n=== OVERVIEW ===")
print(f"  Total churches:     {results['total']:>10,}")
print(f"  Countries:          {results['countries']:>10,}")
print(f"  Denomination vals:  {results['denominations']:>10,}")
print(f"  DB file size:       {results['db_size_mb']:>8.1f} MB")
print(f"  WAL file size:      {results['wal_size_mb']:>8.1f} MB")

print(f"\n=== TOP 15 COUNTRIES ===")
for row in results["top_countries"]:
    print(f"  {row[0] or '(blank)':20s} {row[1]:>10,}")

print(f"\n=== TOP SOURCES ===")
for row in results["sources"]:
    print(f"  {(row[0] or 'blank'):45s} {row[1]:>10,}")

# Also check some enrichment stats
c.execute("SELECT COUNT(*) FROM church_enrichment")
results["enrichment_rows"] = c.fetchone()[0]

c.execute("SELECT COUNT(*) FROM provenance_log")
results["provenance_ops"] = c.fetchone()[0]

print(f"\n  Enrichment rows:    {results['enrichment_rows']:>10,}")
print(f"  Provenance ops:     {results['provenance_ops']:>10,}")

conn.close()
