"""Tag PH Foursquare Gospel churches with movement=legacy field."""
import sqlite3

db = sqlite3.connect("E:/grid/churches.db")
db.row_factory = sqlite3.Row

# Count before
cursor = db.execute("SELECT COUNT(*) FROM churches WHERE country='PH' AND name LIKE '%Foursquare%'")
total = cursor.fetchone()[0]
print(f"Foursquare churches in PH: {total:,}")

# Check current tradition/legacy
cursor = db.execute("SELECT tradition, legacy, COUNT(*) as cnt FROM churches WHERE country='PH' AND name LIKE '%Foursquare%' GROUP BY tradition, legacy")
print("\nBefore:")
for r in cursor.fetchall():
    print(f"  tradition={r['tradition']:20s} legacy={str(r['legacy']):20s} count={r['cnt']:>4,}")

# Tag all Foursquare with the correct legacy
db.execute("""
    UPDATE churches SET
        tradition = 'Pentecostal',
        legacy = 'Foursquare Gospel'
    WHERE country = 'PH'
      AND name LIKE '%Foursquare%'
""")
db.commit()

# Verify
cursor = db.execute("SELECT tradition, legacy, COUNT(*) as cnt FROM churches WHERE country='PH' AND name LIKE '%Foursquare%' GROUP BY tradition, legacy")
print("\nAfter:")
for r in cursor.fetchall():
    print(f"  tradition={r['tradition']:20s} legacy={str(r['legacy']):20s} count={r['cnt']:>4,}")

# Also check globally
cursor = db.execute("SELECT country, COUNT(*) as cnt FROM churches WHERE name LIKE '%Foursquare%' GROUP BY country ORDER BY cnt DESC LIMIT 10")
print("\nGlobal Foursquare distribution:")
for r in cursor.fetchall():
    print(f"  {r['country']:5s}: {r['cnt']:>5,}")

# Tag all globally too
db.execute("""
    UPDATE churches SET
        tradition = 'Pentecostal',
        legacy = 'Foursquare Gospel'
    WHERE name LIKE '%Foursquare%'
      AND (legacy IS NULL OR legacy != 'Foursquare Gospel')
""")
db.commit()

cursor = db.execute("SELECT COUNT(*) FROM churches WHERE name LIKE '%Foursquare%' AND legacy='Foursquare Gospel'")
print(f"\nGlobal Foursquare with legacy='Foursquare Gospel': {cursor.fetchone()[0]:,}")

db.close()
print("\nDone.")
