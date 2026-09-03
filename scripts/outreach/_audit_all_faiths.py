"""Audit ALL faith groups for outreach gaps — who has good data we haven't pitched?"""
import sqlite3
db = sqlite3.connect('churches.db')
db.row_factory = sqlite3.Row

print("=== ALL FAITHS — COVERAGE AUDIT ===")
for r in db.execute("""
    SELECT faith, COUNT(*) as total,
           SUM(CASE WHEN latitude IS NOT NULL THEN 1 ELSE 0 END) as with_gps,
           ROUND(100.0 * SUM(CASE WHEN latitude IS NOT NULL THEN 1 ELSE 0 END) / COUNT(*), 1) as gps_pct,
           COUNT(DISTINCT country) as countries
    FROM churches
    WHERE faith IS NOT NULL AND faith != ''
    GROUP BY faith
    ORDER BY total DESC
"""):
    print(f"{r['faith']:30s} {r['total']:>8,} sites  {r['with_gps']:>8,} GPS  {r['gps_pct']:>5.1f}%  {r['countries']:>3} countries")

print("\n=== TRADITION DEPTH (faiths with 5+ traditions) ===")
for r in db.execute("""
    SELECT faith, COUNT(DISTINCT tradition) as traditions, COUNT(*) as total
    FROM churches WHERE tradition IS NOT NULL AND tradition != ''
    GROUP BY faith HAVING traditions >= 3
    ORDER BY traditions DESC
"""):
    print(f"{r['faith']:30s} {r['traditions']:>4} traditions  {r['total']:>8,} sites")

print("\n=== UNIQUE LANDMARK TYPES PER FAITH ===")
for r in db.execute("""
    SELECT faith, COUNT(DISTINCT landmark_type) as types, COUNT(*) as total
    FROM churches WHERE landmark_type IS NOT NULL AND landmark_type != ''
    GROUP BY faith HAVING types >= 3
    ORDER BY types DESC LIMIT 15
"""):
    print(f"{r['faith']:30s} {r['types']:>3} types  {r['total']:>8,} sites")

# Check which faiths have hierarchy data
print("\n=== HIERARCHY COVERAGE ===")
hierarchies = ['catholic_hierarchy','baptist_hierarchy','lutheran_hierarchy','lds_hierarchy','jw_hierarchy','sa_hierarchy','chabad_hierarchy','moravian_hierarchy','bahai_hierarchy']
for h in hierarchies:
    try:
        n = db.execute(f"SELECT COUNT(*) as n FROM {h}").fetchone()['n']
        faith = h.replace('_hierarchy','').title()
        print(f"{faith:30s} {n:>8,} records")
    except: pass

# Check what we have for the "Other" faith bucket
print("\n=== OTHER FAITH BREAKDOWN ===")
for r in db.execute("""
    SELECT tradition, COUNT(*) as n FROM churches
    WHERE faith='Other' AND tradition IS NOT NULL
    GROUP BY tradition ORDER BY n DESC LIMIT 15
"""):
    print(f"  {r['tradition']}: {r['n']:,}")

# Bahai
print("\n=== BAHAI COVERAGE ===")
for r in db.execute("SELECT COUNT(*) as n, COUNT(*) as gps FROM churches WHERE faith='Bahai'"):
    print(f"  Total: {r['n']:,}")
for r in db.execute("SELECT country, COUNT(*) as n FROM churches WHERE faith='Bahai' GROUP BY country ORDER BY n DESC LIMIT 5"):
    print(f"  {r['country']}: {r['n']:,}")

# Sikh
print("\n=== SIKH COVERAGE ===")
for r in db.execute("SELECT COUNT(*) as n, COUNT(*) as gps FROM churches WHERE faith='Sikh'"):
    print(f"  Total: {r['n']:,}")
for r in db.execute("SELECT country, COUNT(*) as n FROM churches WHERE faith='Sikh' GROUP BY country ORDER BY n DESC LIMIT 5"):
    print(f"  {r['country']}: {r['n']:,}")

# Shinto
print("\n=== SHINTO COVERAGE ===")
for r in db.execute("SELECT COUNT(*) as n FROM churches WHERE faith='Shinto'"):
    print(f"  Total: {r['n']:,}")
for r in db.execute("SELECT country, COUNT(*) as n FROM churches WHERE faith='Shinto' GROUP BY country ORDER BY n DESC LIMIT 5"):
    print(f"  {r['country']}: {r['n']:,}")

# Taoist
print("\n=== TAOIST COVERAGE ===")
for r in db.execute("SELECT COUNT(*) as n FROM churches WHERE faith='Taoist'"):
    print(f"  Total: {r['n']:,}")
for r in db.execute("SELECT country, COUNT(*) as n FROM churches WHERE faith='Taoist' GROUP BY country ORDER BY n DESC LIMIT 5"):
    print(f"  {r['country']}: {r['n']:,}")

# Buddhist - we know this is big
print("\n=== BUDDHIST COVERAGE ===")
for r in db.execute("SELECT COUNT(*) as n FROM churches WHERE faith='Buddhist'"):
    print(f"  Total: {r['n']:,}")
for r in db.execute("SELECT COUNT(DISTINCT tradition) as n FROM churches WHERE faith='Buddhist' AND tradition IS NOT NULL"):
    print(f"  Traditions: {r['n']}")
for r in db.execute("SELECT country, COUNT(*) as n FROM churches WHERE faith='Buddhist' GROUP BY country ORDER BY n DESC LIMIT 5"):
    print(f"  {r['country']}: {r['n']:,}")
for r in db.execute("SELECT COUNT(*) as n FROM churches WHERE faith='Buddhist' AND country='US'"):
    print(f"  US: {r['n']:,}")

db.close()
