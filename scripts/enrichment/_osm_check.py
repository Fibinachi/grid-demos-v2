import sqlite3
db = sqlite3.connect('E:/grid/churches.db')

# Check OSM-sourced records
print("--- OSM-related sources in churches ---")
for s, c in db.execute("SELECT source, COUNT(*) FROM churches WHERE source LIKE '%osm%' OR source LIKE '%overture%' GROUP BY source ORDER BY COUNT(*) DESC"):
    print(f"  {s}: {c:,}")

print("\n--- holy_sites breakdown ---")
hs_total = db.execute("SELECT COUNT(*) FROM holy_sites").fetchone()[0]
print(f"Total: {hs_total:,}")

# Check faith/tradition distribution
print("\nBy faith:")
for f, c in db.execute("SELECT COALESCE(faith,'NULL'), COUNT(*) FROM holy_sites GROUP BY faith ORDER BY COUNT(*) DESC LIMIT 15"):
    print(f"  {f}: {c:,}")

# Check country
print("\nBy country (top 15):")
for co, c in db.execute("SELECT COALESCE(country,'NULL'), COUNT(*) FROM holy_sites GROUP BY country ORDER BY COUNT(*) DESC LIMIT 15"):
    print(f"  {co}: {c:,}")

# Check source
print("\nBy source:")
for s, c in db.execute("SELECT COALESCE(source,'NULL'), COUNT(*) FROM holy_sites GROUP BY source ORDER BY COUNT(*) DESC"):
    print(f"  {s}: {c:,}")

# Check holy_sites schema
print("\n--- holy_sites columns ---")
cols = [(r[1], r[2]) for r in db.execute("PRAGMA table_info(holy_sites)")]
for name, dtype in cols:
    print(f"  {name}: {dtype}")

# Check if any osm/overture in holy_sites
print("\n--- OSM/Wikidata overlap ---")
overlap = db.execute("""
    SELECT COUNT(DISTINCT h.id) FROM holy_sites h
    INNER JOIN churches c ON ROUND(c.latitude,3) = ROUND(h.lat,3) 
                         AND ROUND(c.longitude,3) = ROUND(h.lon,3)
    WHERE c.latitude IS NOT NULL AND h.lat IS NOT NULL
""").fetchone()[0]
print(f"holy_sites co-located with churches: {overlap:,}")

db.close()
