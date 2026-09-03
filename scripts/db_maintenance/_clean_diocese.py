"""Clean up bad diocese entries and check results."""
import sqlite3
conn = sqlite3.connect('churches.db')
c = conn.cursor()

# Remove bad placeholder entries
c.execute("UPDATE church_enrichment SET diocese=NULL, diocese_detail=NULL WHERE diocese='Roman Catholic Diocese (see state)'")
print(f"Cleared {c.rowcount} bad entries")

# Also check for any other suspicious values
c.execute("SELECT diocese, COUNT(*) as cnt FROM church_enrichment WHERE diocese IS NOT NULL AND diocese != '' GROUP BY diocese HAVING cnt < 10 ORDER BY cnt")
suspicious = c.fetchall()
print(f"\nRare dioceses (fewer than 10 churches): {len(suspicious)}")
for r in suspicious[:20]:
    print(f"  {r[0]:40s} {r[1]}")

# Unique dioceses
c.execute("SELECT COUNT(DISTINCT diocese) FROM church_enrichment WHERE diocese IS NOT NULL AND diocese != ''")
print(f"\nUnique dioceses: {c.fetchone()[0]}")

# Final stats
c.execute("SELECT COUNT(*) FROM church_enrichment WHERE diocese IS NOT NULL AND diocese != ''")
with_diocese = c.fetchone()[0]
c.execute("SELECT COUNT(*) FROM churches WHERE country='US'")
total_us = c.fetchone()[0]
print(f"\nFinal: {with_diocese:,} / {total_us:,} ({100*with_diocese/total_us:.1f}%)")

# Distribution across top dioceses
print("\nTop 25 dioceses:")
for r in c.execute("""
    SELECT ce.diocese, COUNT(*) as cnt
    FROM church_enrichment ce
    JOIN churches ch ON ch.id = ce.church_id
    WHERE ch.country='US' AND ce.diocese IS NOT NULL AND ce.diocese != ''
    GROUP BY ce.diocese ORDER BY cnt DESC LIMIT 25
"""):
    print(f"  {r[0]:30s} {r[1]:>8,}")

conn.commit()
conn.close()
