"""Deeper look at why city matching failed + what CAN match."""
import sqlite3

db = sqlite3.connect("churches.db")
c = db.cursor()

# Why did city matching return 0? Check a few examples
examples = [
    ("Prague", "CZ"),
    ("Dresden", "DE"),
    ("Antwerp", "BE"),
    ("Salzburg", "AT"),
    ("Bendigo", "AU"),
]

print("=== Checking why city matching failed ===")
for city, country in examples:
    # Check hierarchy for dioceses in that city
    c.execute("""
        SELECT id, name, cath_type, city, country 
        FROM catholic_hierarchy 
        WHERE cath_type IN ('diocese','archdiocese') 
        AND LOWER(city) = LOWER(?) AND country = ?
    """, (city, country))
    matches = c.fetchall()
    print(f"\nCity={city}, Country={country}:")
    if matches:
        for m in matches:
            print(f"  MATCH: {m}")
    else:
        # Try with LIKE
        c.execute("""
            SELECT id, name, cath_type, city, country 
            FROM catholic_hierarchy 
            WHERE cath_type IN ('diocese','archdiocese') 
            AND LOWER(city) LIKE ? AND country = ?
        """, (f'%{city.lower()}%', country))
        matches2 = c.fetchall()
        if matches2:
            for m in matches2:
                print(f"  LIKE match: {m}")
        else:
            print(f"  NO diocese found in {city}")
            # Check what's in this country
            c.execute("""
                SELECT id, name, cath_type, city 
                FROM catholic_hierarchy 
                WHERE cath_type IN ('diocese','archdiocese') AND country = ?
                LIMIT 5
            """, (country,))
            dioceses = c.fetchall()
            for d in dioceses:
                print(f"  Diocese in {country}: {d}")

# Better approach: name-based matching
print("\n\n=== Name-based matching potential ===")
print("Can we match 'Cathedral of X' → 'Diocese of X'?")
c.execute("""
    SELECT ch.id, ch.name, ch.city, ch.country
    FROM catholic_hierarchy ch
    WHERE ch.cath_type = 'cathedral' AND ch.parent_id IS NULL
    AND ch.country IN ('US','GB','AU','CA','IE')
    LIMIT 20
""")
for r in c.fetchall():
    name = r[1] or ""
    city = r[2] or ""
    country = r[4] if len(r) > 4 else ""
    
    # Try to extract a diocese name from cathedral name
    # Pattern: "Cathedral of X" or "X Cathedral"
    words = name.replace("Cathedral", "|").split("|")
    # The non-cathedral part might be the diocese name
    print(f"  {name[:55]:55s} | city={city or '?'}")
    
    # Try matching: find diocese whose name ends with the city
    if city:
        c.execute("""
            SELECT id, name FROM catholic_hierarchy
            WHERE cath_type IN ('diocese','archdiocese')
            AND (LOWER(name) LIKE ? OR LOWER(name) LIKE ?)
            AND country = ?
            LIMIT 1
        """, (f'%{city.lower()}%', f'%{city.lower()} diocese', country))
        match = c.fetchone()
        if match:
            print(f"    → MATCH by city in name: {match[1]} (id={match[0]})")
        else:
            print(f"    → No match by city")

db.close()
