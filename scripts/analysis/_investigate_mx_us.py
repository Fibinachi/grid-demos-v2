"""Investigate MX-labeled records that are really in the US"""
import sqlite3

db = sqlite3.connect(r"E:\grid\churches.db")
c = db.cursor()

# Total MX records
c.execute("SELECT COUNT(*) FROM churches WHERE country='MX'")
total_mx = c.fetchone()[0]
print(f"Total country='MX' records: {total_mx:,}")

# MX records with latitude in US range (roughly 25-50 N)
c.execute("""
    SELECT COUNT(*) FROM churches 
    WHERE country='MX' 
    AND latitude BETWEEN 24 AND 50 
    AND longitude BETWEEN -125 AND -65
""")
us_coords = c.fetchone()[0]
print(f"MX records with US-ish coords (lat 24-50, lon -125 to -65): {us_coords:,}")

# More precise: MX records north of the US-Mexico border (~32.5°N in most areas)
c.execute("""
    SELECT COUNT(*) FROM churches 
    WHERE country='MX' 
    AND latitude >= 31.5
    AND longitude BETWEEN -125 AND -65
""")
north_of_border = c.fetchone()[0]
print(f"MX records north of ~31.5°N (definitely US or Canada): {north_of_border:,}")

# MX records north of 25°N but with longitude clearly in US
c.execute("""
    SELECT COUNT(*) FROM churches 
    WHERE country='MX' 
    AND latitude BETWEEN 25 AND 32
    AND longitude BETWEEN -125 AND -100
""")
sw_us_zone = c.fetchone()[0]
print(f"MX records lat 25-32, lon -125 to -100 (SW US zone): {sw_us_zone:,}")

# Total MX records that are likely US
c.execute("""
    SELECT COUNT(*) FROM churches 
    WHERE country='MX' 
    AND latitude >= 25
    AND longitude BETWEEN -125 AND -65
""")
likely_us = c.fetchone()[0]
print(f"\nTotal MX records likely US (lat>=25, lon -125 to -65): {likely_us:,}")

# Check MX records south of border too
c.execute("SELECT COUNT(*) FROM churches WHERE country='MX' AND latitude < 25")
south_mx = c.fetchone()[0]
print(f"MX records south of 25°N (probably really Mexico): {south_mx:,}")

# source breakdown of the likely-US MX records
c.execute("""
    SELECT source, COUNT(*) as cnt FROM churches 
    WHERE country='MX' 
    AND latitude >= 25
    AND longitude BETWEEN -125 AND -65
    GROUP BY source ORDER BY cnt DESC
""")
print("\n=== Source breakdown of likely-US MX records ===")
for r in c.fetchall():
    print(f"  {str(r[0])[:35]:35s}  {r[1]:>8,}")

# Sample them
c.execute("""
    SELECT rowid, name, source, city, state, latitude, longitude 
    FROM churches 
    WHERE country='MX' 
    AND latitude >= 30
    AND longitude BETWEEN -125 AND -80
    LIMIT 20
""")
print("\n=== Sample MX records with US coords (lat>=30) ===")
for r in c.fetchall():
    print(f"  rowid={r[0]} name={str(r[1])[:50]:50s} src={r[2]:20s} city={str(r[3] or '')[:20]:20s} st={r[4]}  lat={r[5]:.4f} lon={r[6]:.4f}")

# Also check: how many MX records have US state codes?
c.execute("""
    SELECT COUNT(*) FROM churches 
    WHERE country='MX' AND state IN ('AL','AK','AZ','AR','CA','CO','CT','DE','FL','GA',
    'HI','ID','IL','IN','IA','KS','KY','LA','ME','MD','MA','MI','MN','MS','MO','MT',
    'NE','NV','NH','NJ','NM','NY','NC','ND','OH','OK','OR','PA','RI','SC','SD','TN',
    'TX','UT','VT','VA','WA','WV','WI','WY')
""")
us_state_count = c.fetchone()[0]
print(f"\nMX records with a US state code: {us_state_count:,}")

# MX records with a US state that are also north of border
c.execute("""
    SELECT COUNT(*) FROM churches 
    WHERE country='MX' 
    AND state IN ('AL','AK','AZ','AR','CA','CO','CT','DE','FL','GA',
    'HI','ID','IL','IN','IA','KS','KY','LA','ME','MD','MA','MI','MN','MS','MO','MT',
    'NE','NV','NH','NJ','NM','NY','NC','ND','OH','OK','OR','PA','RI','SC','SD','TN',
    'TX','UT','VT','VA','WA','WV','WI','WY')
    AND latitude >= 25
""")
us_state_north = c.fetchone()[0]
print(f"MX records with US state + lat>=25: {us_state_north:,}")

# What denomination/faith are these mislabeled records?
c.execute("""
    SELECT faith, COUNT(*) as cnt FROM churches 
    WHERE country='MX' 
    AND latitude >= 25
    AND longitude BETWEEN -125 AND -65
    GROUP BY faith ORDER BY cnt DESC LIMIT 10
""")
print("\n=== Faith breakdown of likely-US MX records ===")
for r in c.fetchall():
    print(f"  {str(r[0] or 'NULL'):20s}  {r[1]:>8,}")

db.close()
