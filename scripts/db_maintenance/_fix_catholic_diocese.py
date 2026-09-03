"""Fix: NULL out diocese for non-Catholic churches in church_enrichment.
Only ~41K US churches are Catholic — the rest shouldn't have Catholic diocese assignments."""
import sqlite3
from gw_db import connect, Provenance

conn = connect()
c = conn.cursor()

# Catholic denomination patterns
catholic_patterns = [
    "catholic", "roman catholic", "roman cath", "eastern catholic",
    "byzantine catholic", "maronite catholic", "melkite", "ukrainian catholic",
    "syro-malabar", "syro-malankara", "chaldean catholic", "armenian catholic",
    "coptic catholic", "ethiopian catholic", "ruthenian catholic",
    "latin catholic", "greek catholic", "syrian catholic",
]

# Build LIKE clauses
like_clauses = " OR ".join([f"LOWER(ch.denomination) LIKE '%{p}%'" for p in catholic_patterns])
# Also include where faith='Catholic' (but faith uses 'Christian' mostly)
# Also check for NULL denomination but name suggests Catholic
sql = f"""
    SELECT COUNT(*) FROM church_enrichment ce
    JOIN churches ch ON ch.id = ce.church_id
    WHERE ch.country='US' 
      AND ce.diocese IS NOT NULL AND ce.diocese != ''
      AND NOT ({like_clauses})
"""
c.execute(sql)
non_catholic_with_diocese = c.fetchone()[0]
print(f"Non-Catholic churches with diocese: {non_catholic_with_diocese:,}")

# NULL them out
print("Clearing diocese for non-Catholic churches...")
with Provenance(conn, "_fix_catholic_diocese.py", source="manual_fix",
                action="cleaned", fields="diocese,diocese_detail,province,province_detail"):
    c.execute(f"""
        UPDATE church_enrichment 
        SET diocese = NULL, diocese_detail = NULL, province = NULL, province_detail = NULL
        WHERE church_id IN (
            SELECT ce.church_id FROM church_enrichment ce
            JOIN churches ch ON ch.id = ce.church_id
            WHERE ch.country='US' 
              AND ce.diocese IS NOT NULL AND ce.diocese != ''
              AND NOT ({like_clauses})
        )
    """)
    print(f"  Cleared {c.rowcount:,} entries")
    conn.commit()

# Final stats
c.execute("""
    SELECT COUNT(*) FROM church_enrichment ce 
    JOIN churches ch ON ch.id=ce.church_id 
    WHERE ch.country='US' AND ce.diocese IS NOT NULL AND ce.diocese != ''
""")
final_with_diocese = c.fetchone()[0]
c.execute("SELECT COUNT(*) FROM churches WHERE country='US'")
total_us = c.fetchone()[0]
c.execute("""
    SELECT COUNT(*) FROM churches 
    WHERE country='US' AND (LOWER(denomination) LIKE '%catholic%' OR LOWER(denomination) LIKE '%roman%')
""")
catholic_us = c.fetchone()[0]

print(f"\n=== FINAL ===")
print(f"Catholic US churches: {catholic_us:,}")
print(f"Diocese assigned: {final_with_diocese:,}")
print(f"Coverage of Catholic churches: {100*final_with_diocese/catholic_us:.1f}%")
print(f"Coverage of all US churches: {100*final_with_diocese/total_us:.1f}%")

# Top dioceses now
print("\nTop 15 dioceses (should be reasonable Catholic counts):")
for r in c.execute("""
    SELECT ce.diocese, COUNT(*) as cnt
    FROM church_enrichment ce
    JOIN churches ch ON ch.id = ce.church_id
    WHERE ch.country='US' AND ce.diocese IS NOT NULL AND ce.diocese != ''
    GROUP BY ce.diocese ORDER BY cnt DESC LIMIT 15
"""):
    print(f"  {r[0]:30s} {r[1]:>7,}")

conn.close()
