"""Commercial value assessment for the GRID dataset."""
import sqlite3
db = sqlite3.connect('churches.db')

print("=" * 65)
print("GRID DATASET — COMMERCIAL VALUE ASSESSMENT")
print("=" * 65)

total = db.execute("SELECT COUNT(*) FROM churches").fetchone()[0]
with_gps = db.execute("SELECT COUNT(*) FROM churches WHERE latitude IS NOT NULL").fetchone()[0]
print(f"\n  Total sites: {total:>12,}  |  GPS coverage: {with_gps:>12,} ({100*with_gps//total}%)")

print(f"\n--- CONTACT DATA ---")
for ct in ['website', 'phone', 'email']:
    n = db.execute("SELECT COUNT(DISTINCT church_id) FROM church_contact_values WHERE contact_type=?", (ct,)).fetchone()[0]
    print(f"  {ct:10s}: {n:>10,} churches")

print(f"\n--- TOP 15 COUNTRIES ---")
print(f"  {'Country':20s} {'Total':>8s} {'GPS':>8s} {'Email':>7s} {'Phone':>7s} {'Web':>8s}")
for row in db.execute("""
    SELECT country, COUNT(*) as t,
           SUM(CASE WHEN latitude IS NOT NULL THEN 1 ELSE 0 END),
           SUM(CASE WHEN id IN (SELECT DISTINCT church_id FROM church_contact_values WHERE contact_type='email') THEN 1 ELSE 0 END),
           SUM(CASE WHEN id IN (SELECT DISTINCT church_id FROM church_contact_values WHERE contact_type='phone') THEN 1 ELSE 0 END),
           SUM(CASE WHEN id IN (SELECT DISTINCT church_id FROM church_contact_values WHERE contact_type='website') THEN 1 ELSE 0 END)
    FROM churches WHERE country IS NOT NULL AND country != ''
    GROUP BY country ORDER BY t DESC LIMIT 15
"""):
    print(f"  {row[0]:20s} {row[1]:>8,} {row[2]:>8,} {row[3]:>7,} {row[4]:>7,} {row[5]:>8,}")

print(f"\n--- USA DEPTH (1,073,557 total) ---")
for row in db.execute("SELECT faith, COUNT(*) FROM churches WHERE country='US' GROUP BY faith ORDER BY 2 DESC"):
    print(f"  {row[0]:20s} {row[1]:>10,}")

ppp_n = db.execute("SELECT COUNT(*) FROM sba_ppp_loans").fetchone()[0]
print(f"\n--- PPP LOAN DATA ---")
print(f"  Loans matched: {ppp_n:,}")

print(f"\n--- ORGANIZATIONAL HIERARCHIES ---")
for row in db.execute("SELECT name FROM sqlite_master WHERE type='table' AND name LIKE '%_hierarchy' ORDER BY name"):
    n = db.execute("SELECT COUNT(*) FROM " + row[0]).fetchone()[0]
    print(f"  {row[0]:30s} {n:>10,}")

print(f"\n--- ELECTORAL & CENSUS ENRICHMENT ---")
for (name,) in db.execute("SELECT name FROM sqlite_master WHERE type='table' AND (name LIKE 'church_election_%' OR name LIKE 'church_census_%') ORDER BY name"):
    n = db.execute("SELECT COUNT(*) FROM " + name).fetchone()[0]
    print(f"  {name:35s} {n:>10,}")

try:
    arda = db.execute("SELECT COUNT(*) FROM arda_counts").fetchone()[0]
    print(f"\n--- ARDA RELIGIOUS CENSUS ---")
    print(f"  2020: {arda:,} rows")
except:
    pass

db.close()
print("\n" + "=" * 65)
