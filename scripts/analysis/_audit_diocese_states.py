"""Audit diocese assignments for cross-state anomalies."""
import sqlite3
conn = sqlite3.connect('churches.db')
c = conn.cursor()

print("=== Diocese names with highest state diversity ===")
c.execute("""
    SELECT ce.diocese, COUNT(DISTINCT ch.state) as state_count, COUNT(*) as churches
    FROM church_enrichment ce
    JOIN churches ch ON ch.id = ce.church_id
    WHERE ch.country='US' 
      AND ce.diocese IS NOT NULL AND ce.diocese != ''
      AND (LOWER(ch.denomination) LIKE '%catholic%' OR LOWER(ch.denomination) LIKE '%roman%')
    GROUP BY ce.diocese
    ORDER BY state_count DESC LIMIT 20
""")
for r in c.fetchall():
    print(f"  {r[0]:30s} {r[1]:>3} states, {r[2]:>7,} churches")

print("\n=== Potentially wrong: LA diocese churches outside CA ===")
c.execute("""
    SELECT ce.diocese, ch.state, COUNT(*) as cnt
    FROM church_enrichment ce
    JOIN churches ch ON ch.id = ce.church_id
    WHERE ch.country='US' 
      AND (LOWER(ch.denomination) LIKE '%catholic%' OR LOWER(ch.denomination) LIKE '%roman%')
      AND ce.diocese LIKE '%Los Angeles%'
    GROUP BY ce.diocese, ch.state ORDER BY cnt DESC
""")
for r in c.fetchall():
    print(f"  {r[0]:30s} {r[1]:5s} {r[2]:>6,}")

print("\n=== Diocese 'Charleston' churches outside SC ===")
c.execute("""
    SELECT ce.diocese, ch.state, COUNT(*) as cnt
    FROM church_enrichment ce
    JOIN churches ch ON ch.id = ce.church_id
    WHERE ch.country='US' 
      AND (LOWER(ch.denomination) LIKE '%catholic%' OR LOWER(ch.denomination) LIKE '%roman%')
      AND ce.diocese = 'Charleston'
    GROUP BY ce.diocese, ch.state ORDER BY cnt DESC
""")
for r in c.fetchall():
    print(f"  {r[0]:30s} {r[1]:5s} {r[2]:>6,}")

print("\n=== Top diocese/state combos that seem wrong ===")
# Dioceses named after cities that appear in wrong states
city_states = {
    'Los Angeles': 'CA', 'San Francisco': 'CA', 'San Diego': 'CA',
    'New York': 'NY', 'Brooklyn': 'NY', 'Buffalo': 'NY',
    'Chicago': 'IL', 'Boston': 'MA', 'Miami': 'FL',
    'Detroit': 'MI', 'Seattle': 'WA', 'Denver': 'CO',
    'Phoenix': 'AZ', 'Atlanta': 'GA', 'Houston': 'TX',
    'Dallas': 'TX', 'Philadelphia': 'PA', 'Baltimore': 'MD',
    'Washington': 'DC', 'Newark': 'NJ', 'Cleveland': 'OH',
    'St. Louis': 'MO', 'Portland': 'OR',
}
for city, expected_state in city_states.items():
    c.execute(f"""
        SELECT ch.state, COUNT(*) FROM church_enrichment ce
        JOIN churches ch ON ch.id = ce.church_id
        WHERE ch.country='US' AND ce.diocese LIKE '%{city}%'
          AND ch.state != '{expected_state}'
          AND (LOWER(ch.denomination) LIKE '%catholic%' OR LOWER(ch.denomination) LIKE '%roman%')
        GROUP BY ch.state
    """)
    wrong = c.fetchall()
    if wrong:
        print(f"\n  '{city}' diocese churches in wrong states:")
        for state, cnt in wrong:
            print(f"    {state}: {cnt:,}")

# Check 273 unique diocese issue
c.execute("""
    SELECT COUNT(DISTINCT ce.diocese) 
    FROM church_enrichment ce
    JOIN churches ch ON ch.id = ce.church_id
    WHERE ch.country='US' AND ce.diocese IS NOT NULL AND ce.diocese != ''
      AND (LOWER(ch.denomination) LIKE '%catholic%' OR LOWER(ch.denomination) LIKE '%roman%')
""")
print(f"\nUnique diocese names (US Catholic): {c.fetchone()[0]}")

# What non-standard diocese names are there?
c.execute("""
    SELECT ce.diocese, COUNT(*) as cnt
    FROM church_enrichment ce
    JOIN churches ch ON ch.id = ce.church_id
    WHERE ch.country='US' AND ce.diocese IS NOT NULL AND ce.diocese != ''
      AND (LOWER(ch.denomination) LIKE '%catholic%' OR LOWER(ch.denomination) LIKE '%roman%')
      AND ce.diocese NOT LIKE '%Diocese of%'
      AND ce.diocese NOT LIKE '%Archdiocese%'
    GROUP BY ce.diocese ORDER BY cnt DESC LIMIT 20
""")
print("\nNon-standard diocese names (not 'Diocese of X' or 'Archdiocese of X'):")
for r in c.fetchall():
    print(f"  {r[0]:40s} {r[1]:>6,}")

conn.close()
