"""Assess the 246 orphaned cathedral entries in catholic_hierarchy.
These are proper Catholic cathedrals from ecclesiastical_territories data
that have no enrichment.diocese to link them to their parent diocese."""
import sqlite3

db = sqlite3.connect("churches.db")
c = db.cursor()

print("=== 246 Orphaned Cathedral Entries ===")
print()

# Get them
c.execute("""
    SELECT ch.id, ch.name, ch.city, ch.state, ch.country,
           ch.lat, ch.lon
    FROM catholic_hierarchy ch
    WHERE ch.cath_type = 'cathedral' AND ch.parent_id IS NULL
    ORDER BY ch.country, ch.city
""")
rows = c.fetchall()
print(f"Total orphaned: {len(rows)}")

# Country breakdown
country_counts = {}
for r in rows:
    country = r[4] or "??"
    country_counts[country] = country_counts.get(country, 0) + 1

print(f"\nCountry breakdown (top 20):")
for country, cnt in sorted(country_counts.items(), key=lambda x: -x[1])[:20]:
    print(f"  {country:30s} {cnt}")

print(f"\nTotal countries represented: {len(country_counts)}")

# Sample entries
print(f"\n=== Sample entries ===")
for r in rows[:30]:
    print(f"  id={r[0]:5d} | {r[1][:50]:50s} | {r[2] or '?':20s} | {r[4] or '?'}")

# Check: do any of these cathedral names contain the diocese name?
# We can try matching by: city name in cathedral name vs diocese city
# Or: cathedral named after saint -> diocese named after same saint
print(f"\n=== Name pattern analysis ===")
# Check how many have a clear city in their name
city_in_name = 0
saint_named = 0
for r in rows:
    name = (r[1] or "").lower()
    city = (r[2] or "").lower()
    if city and city in name:
        city_in_name += 1
    if "st." in name or "saint" in name:
        saint_named += 1

print(f"  City mentioned in cathedral name: {city_in_name}")
print(f"  Saint-named cathedrals: {saint_named}")

# Try matching: for orphaned cathedrals with a city, find a diocese in the same city
print(f"\n=== City-based matching potential ===")
matched_by_city = 0
for r in rows:
    city = r[2]
    country = r[4]
    if not city or not country:
        continue
    c.execute("""
        SELECT id, name FROM catholic_hierarchy
        WHERE cath_type IN ('diocese', 'archdiocese')
        AND LOWER(city) = LOWER(?) AND country = ?
        LIMIT 1
    """, (city, country))
    if c.fetchone():
        matched_by_city += 1

print(f"  Orphaned cathedrals whose city matches a diocese city: {matched_by_city}")

# Try city+country match from churches table enrichment
print(f"\n=== Using church's enrichment data (fallback) ===")
c.execute("""
    SELECT COUNT(*) FROM catholic_hierarchy ch
    JOIN churches ct ON ch.church_id = ct.id
    JOIN church_enrichment e ON e.church_id = ct.id
    WHERE ch.cath_type = 'cathedral' AND ch.parent_id IS NULL
    AND e.diocese IS NOT NULL AND e.diocese != ''
""")
print(f"  Orphaned cathedrals that actually HAVE enrichment.diocese (should be 0): {c.fetchone()[0]}")

# Check: do these churches have ANY enrichment at all?
c.execute("""
    SELECT COUNT(*) FROM catholic_hierarchy ch
    JOIN churches ct ON ch.church_id = ct.id
    LEFT JOIN church_enrichment e ON e.church_id = ct.id
    WHERE ch.cath_type = 'cathedral' AND ch.parent_id IS NULL
    AND e.church_id IS NULL
""")
no_enc = c.fetchone()[0]
print(f"  Orphaned cathedrals with NO enrichment row at all: {no_enc}")

c.execute("""
    SELECT COUNT(*) FROM catholic_hierarchy ch
    JOIN churches ct ON ch.church_id = ct.id
    JOIN church_enrichment e ON e.church_id = ct.id
    WHERE ch.cath_type = 'cathedral' AND ch.parent_id IS NULL
""")
has_enc = c.fetchone()[0]
print(f"  Orphaned cathedrals WITH enrichment row (but no diocese): {has_enc}")

# What enrichment fields are available for these?
print(f"\n=== Available enrichment fields for orphaned cathedrals ===")
c.execute("""
    SELECT e.diocese FROM catholic_hierarchy ch
    JOIN churches ct ON ch.church_id = ct.id
    JOIN church_enrichment e ON e.church_id = ct.id
    WHERE ch.cath_type = 'cathedral' AND ch.parent_id IS NULL
    LIMIT 5
""")
for r in c.fetchall():
    print(f"  diocese={r[0]}")

# Also check: what are the church names for these?
print(f"\n=== Church names for orphaned cathedrals (sample) ===")
c.execute("""
    SELECT ct.name, ct.city, ct.country
    FROM catholic_hierarchy ch
    JOIN churches ct ON ch.church_id = ct.id
    WHERE ch.cath_type = 'cathedral' AND ch.parent_id IS NULL
    LIMIT 15
""")
for r in c.fetchall():
    print(f"  {r[0][:60]:60s} | {r[1] or '?'}, {r[2] or '?'}")

db.close()
