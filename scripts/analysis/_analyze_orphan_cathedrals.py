"""Analyze the 246 orphaned cathedral entries to understand matching options."""
import sqlite3

db = sqlite3.connect("churches.db")
c = db.cursor()

# What fields do the orphaned cathedrals have?
c.execute("""
    SELECT COUNT(*) FROM catholic_hierarchy
    WHERE cath_type = 'cathedral' AND parent_id IS NULL
""")
print(f"Orphaned cathedrals: {c.fetchone()[0]}")

# Fields availability
fields = ['city', 'state', 'country', 'lat', 'lon', 'diocese', 'archdiocese', 'province', 'territory_id', 'church_id', 'name']
for f in fields:
    c.execute(f"""
        SELECT COUNT(*) FROM catholic_hierarchy
        WHERE cath_type = 'cathedral' AND parent_id IS NULL
        AND {f} IS NOT NULL AND {f} != ''
    """)
    count = c.fetchone()[0]
    print(f"  Has {f}: {count}")

# Sample entries
print()
print("=== Sample orphaned cathedrals ===")
c.execute("""
    SELECT id, name, city, state, country, diocese, archdiocese, province, territory_id
    FROM catholic_hierarchy
    WHERE cath_type = 'cathedral' AND parent_id IS NULL
    LIMIT 20
""")
for r in c.fetchall():
    print(f"  #{r[0]:5d} {r[1][:50]:50s} | {r[2] or '?':20s} {r[3] or '?'} {r[4] or '?'} | dio={r[5] or 'N/A':20s} arch={r[6] or 'N/A':20s} prov={r[7] or 'N/A':20s} tid={r[8]}")

# Check: do these have church_id, and if so, do the linked churches have enrichment?
c.execute("""
    SELECT COUNT(*) FROM catholic_hierarchy ch
    JOIN churches ct ON ch.church_id = ct.id
    JOIN church_enrichment e ON e.church_id = ct.id
    WHERE ch.cath_type = 'cathedral' AND ch.parent_id IS NULL
""")
print(f"\n  Orphans with enrichment data: {c.fetchone()[0]}")

# What enrichment fields do they have?
c.execute("""
    SELECT e.diocese, e.diocese_detail, e.deanery, COUNT(*) as cnt
    FROM catholic_hierarchy ch
    JOIN churches ct ON ch.church_id = ct.id
    JOIN church_enrichment e ON e.church_id = ct.id
    WHERE ch.cath_type = 'cathedral' AND ch.parent_id IS NULL
    GROUP BY e.diocese, e.diocese_detail, e.deanery
    LIMIT 20
""")
print("\n  Enrichment data for orphans:")
for r in c.fetchall():
    print(f"    diocese={r[0] or 'N/A':30s} detail={r[1] or 'N/A':30s} deanery={r[2] or 'N/A':20s} cnt={r[3]}")

# Also check: what does the name look like? "Cathedral of X" - can we extract diocese name?
print()
print("=== Name patterns of orphans ===")
c.execute("""
    SELECT DISTINCT 
        CASE 
            WHEN name LIKE 'Cathedral of%' THEN 'Cathedral of ...'
            WHEN name LIKE 'Cathedral Church%' THEN 'Cathedral Church ...'
            WHEN name LIKE 'St%' THEN 'Saint ...'
            WHEN name LIKE 'Basilica%' THEN 'Basilica ...'
            WHEN name LIKE 'Holy%' THEN 'Holy ...'
            WHEN name LIKE 'Our Lady%' THEN 'Our Lady ...'
            WHEN name LIKE 'Catedral%' THEN 'Catedral ...'
            WHEN name LIKE 'Duomo%' THEN 'Duomo ...'
            ELSE 'Other'
        END as pattern,
        COUNT(*) as cnt
    FROM catholic_hierarchy
    WHERE cath_type = 'cathedral' AND parent_id IS NULL
    GROUP BY pattern
    ORDER BY cnt DESC
""")
for r in c.fetchall():
    print(f"  {r[0]:30s} {r[1]}")

# Country distribution
print()
print("=== Country distribution of orphans ===")
c.execute("""
    SELECT country, COUNT(*) as cnt
    FROM catholic_hierarchy
    WHERE cath_type = 'cathedral' AND parent_id IS NULL
    GROUP BY country
    ORDER BY cnt DESC
    LIMIT 20
""")
for r in c.fetchall():
    print(f"  {r[0] or 'NULL':20s} {r[1]}")

db.close()
