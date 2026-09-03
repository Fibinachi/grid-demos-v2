"""Check US Hindu and Muslim data for outreach."""
import sqlite3
db = sqlite3.connect('churches.db')
db.row_factory = sqlite3.Row

print("=== US HINDU ===")
total = db.execute("SELECT COUNT(*) as n FROM churches WHERE faith='Hindu' AND country='US'").fetchone()['n']
gps = db.execute("SELECT COUNT(*) as n FROM churches WHERE faith='Hindu' AND country='US' AND latitude IS NOT NULL").fetchone()['n']
print(f"Total: {total:,} | GPS: {gps:,} ({100*gps//total}%)")
print("\nTraditions:")
for r in db.execute("SELECT tradition, COUNT(*) as n FROM churches WHERE faith='Hindu' AND country='US' AND tradition IS NOT NULL GROUP BY tradition ORDER BY n DESC LIMIT 15"):
    print(f"  {r['tradition']}: {r['n']:,}")
print("\nTop states:")
for r in db.execute("SELECT state, COUNT(*) as n FROM churches WHERE faith='Hindu' AND country='US' AND state IS NOT NULL GROUP BY state ORDER BY n DESC LIMIT 10"):
    print(f"  {r['state']}: {r['n']:,}")
for r in db.execute("SELECT cv.contact_type, COUNT(DISTINCT cv.church_id) as n FROM church_contact_values cv JOIN churches c ON c.id=cv.church_id WHERE c.faith='Hindu' AND c.country='US' GROUP BY cv.contact_type"):
    print(f"  {r['contact_type']}: {r['n']:,}")

print("\n=== US ISLAM ===")
total = db.execute("SELECT COUNT(*) as n FROM churches WHERE faith='Islam' AND country='US'").fetchone()['n']
gps = db.execute("SELECT COUNT(*) as n FROM churches WHERE faith='Islam' AND country='US' AND latitude IS NOT NULL").fetchone()['n']
print(f"Total: {total:,} | GPS: {gps:,} ({100*gps//total}%)")
print("\nTraditions:")
for r in db.execute("SELECT tradition, COUNT(*) as n FROM churches WHERE faith='Islam' AND country='US' AND tradition IS NOT NULL GROUP BY tradition ORDER BY n DESC LIMIT 15"):
    print(f"  {r['tradition']}: {r['n']:,}")
print("\nTop states:")
for r in db.execute("SELECT state, COUNT(*) as n FROM churches WHERE faith='Islam' AND country='US' AND state IS NOT NULL GROUP BY state ORDER BY n DESC LIMIT 10"):
    print(f"  {r['state']}: {r['n']:,}")
for r in db.execute("SELECT cv.contact_type, COUNT(DISTINCT cv.church_id) as n FROM church_contact_values cv JOIN churches c ON c.id=cv.church_id WHERE c.faith='Islam' AND c.country='US' GROUP BY cv.contact_type"):
    print(f"  {r['contact_type']}: {r['n']:,}")

print("\n=== GLOBAL ISLAM ===")
total_g = db.execute("SELECT COUNT(*) as n FROM churches WHERE faith='Islam'").fetchone()['n']
countries = db.execute("SELECT COUNT(DISTINCT country) as n FROM churches WHERE faith='Islam'").fetchone()['n']
print(f"Total: {total_g:,} | Countries: {countries}")
print("Top countries:")
for r in db.execute("SELECT country, COUNT(*) as n FROM churches WHERE faith='Islam' GROUP BY country ORDER BY n DESC LIMIT 10"):
    print(f"  {r['country']}: {r['n']:,}")
trads_g = db.execute("SELECT COUNT(DISTINCT tradition) as n FROM churches WHERE faith='Islam' AND tradition IS NOT NULL").fetchone()['n']
print(f"Traditions: {trads_g}")

print("\n=== GLOBAL HINDU ===")
total_g = db.execute("SELECT COUNT(*) as n FROM churches WHERE faith='Hindu'").fetchone()['n']
countries = db.execute("SELECT COUNT(DISTINCT country) as n FROM churches WHERE faith='Hindu'").fetchone()['n']
print(f"Total: {total_g:,} | Countries: {countries}")
for r in db.execute("SELECT country, COUNT(*) as n FROM churches WHERE faith='Hindu' GROUP BY country ORDER BY n DESC LIMIT 10"):
    print(f"  {r['country']}: {r['n']:,}")

db.close()
