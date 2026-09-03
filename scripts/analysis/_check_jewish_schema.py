"""Quick schema check for Judaism map."""
import sqlite3

db = sqlite3.connect('E:/grid/churches.db')
c = db.cursor()

# What faith values exist for Judaism?
c.execute("SELECT faith, COUNT(*) FROM churches WHERE faith LIKE '%Jew%' OR faith LIKE '%juda%' GROUP BY faith")
for r in c.fetchall():
    print('faith:', r)

# Check tradition column name
c.execute("SELECT name FROM pragma_table_info('churches') WHERE name LIKE '%tradition%' OR name LIKE '%faith_trad%'")
for r in c.fetchall():
    print('tradition col:', r)

# Judaism count
c.execute("SELECT COUNT(*) FROM churches WHERE faith = 'Judaism'")
print('Judaism count:', c.fetchone()[0])

# Tradition distribution
c.execute("SELECT tradition, COUNT(*) FROM churches WHERE faith = 'Judaism' GROUP BY tradition ORDER BY COUNT(*) DESC LIMIT 20")
for r in c.fetchall():
    print('tradition:', r)

# Check faith_tradition too
c.execute("SELECT faith_tradition, COUNT(*) FROM churches WHERE faith = 'Judaism' AND faith_tradition IS NOT NULL AND faith_tradition != '' GROUP BY faith_tradition ORDER BY COUNT(*) DESC LIMIT 20")
for r in c.fetchall():
    print('faith_tradition:', r)

# Check if faith = 'Jewish' still exists
c.execute("SELECT COUNT(*) FROM churches WHERE faith = 'Jewish'")
print('faith=Jewish count:', c.fetchone()[0])

# Check null coordinates
c.execute("SELECT COUNT(*) FROM churches WHERE faith='Judaism' AND (latitude IS NULL OR latitude = 0 OR longitude IS NULL OR longitude = 0)")
print('Judaism null coords:', c.fetchone()[0])

# Check null tradition
c.execute("SELECT COUNT(*) FROM churches WHERE faith='Judaism' AND (tradition IS NULL OR tradition = '' OR tradition = 'Unknown')")
print('Judaism null/unknown tradition:', c.fetchone()[0])

db.close()
