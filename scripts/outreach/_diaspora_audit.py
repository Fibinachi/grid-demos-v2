"""Find diaspora patterns — faiths in unexpected countries."""
import sqlite3
db = sqlite3.connect('churches.db')
db.row_factory = sqlite3.Row

print("=== DIASPORA PATTERNS: faiths outside their home country ===")

# Chinese folk religion outside China
cfr = db.execute("SELECT country, COUNT(*) as n FROM churches WHERE faith='Other' AND (tradition LIKE '%Chinese%' OR tradition LIKE '%Folk%') AND country NOT IN ('CN','TW','HK','MO') GROUP BY country ORDER BY n DESC LIMIT 10").fetchall()
if cfr:
    print("\nChinese Folk shrines outside China:")
    for r in cfr: print(f"  {r['country']}: {r['n']:,}")

# Indian temples globally (key diaspora)
print("\nHindu temples (Indian diaspora), top diaspora countries:")
for r in db.execute("SELECT country, COUNT(*) as n FROM churches WHERE faith='Hindu' AND country NOT IN ('IN','NP') AND country NOT IN (SELECT country FROM churches WHERE faith='Hindu' GROUP BY country HAVING COUNT(*) > 50000) GROUP BY country ORDER BY n DESC LIMIT 15"):
    print(f"  {r['country']}: {r['n']:,}")

# Thai Buddhist temples outside Thailand
print("\nBuddhist temples (Thai diaspora), outside Thailand:")
for r in db.execute("SELECT country, COUNT(*) as n FROM churches WHERE faith='Buddhist' AND (tradition LIKE '%Theravada%' OR tradition LIKE '%Thai%') AND country NOT IN ('TH','LA','KH','MM') GROUP BY country ORDER BY n DESC LIMIT 10"):
    print(f"  {r['country']}: {r['n']:,}")

# Turkish mosques in Europe
print("\nMosques in Europe (Turkish diaspora potential):")
for r in db.execute("SELECT country, COUNT(*) as n FROM churches WHERE faith='Islam' AND country IN ('DE','FR','NL','AT','BE','CH','GB','SE','DK','NO','IT','ES') GROUP BY country ORDER BY n DESC"):
    print(f"  {r['country']}: {r['n']:,}")

# Vietnamese Buddhist temples outside Vietnam
print("\nVietnamese Buddhist diaspora:")
for r in db.execute("SELECT country, COUNT(*) as n FROM churches WHERE faith='Buddhist' AND country NOT IN ('VN') AND tradition IN ('Vietnamese','Mahayana') AND country IN ('US','CA','AU','FR','DE','GB') GROUP BY country ORDER BY n DESC"):
    print(f"  {r['country']}: {r['n']:,}")

# Korean churches globally (Korean diaspora is heavily Christian)
print("\nKorean Christian diaspora (potential):")
for r in db.execute("SELECT country, COUNT(*) as n FROM churches WHERE (tradition LIKE '%Presbyterian%' OR denomination LIKE '%Korean%' OR name LIKE '%KOREAN%') AND country != 'KR' AND country != 'US' GROUP BY country ORDER BY n DESC LIMIT 10"):
    print(f"  {r['country']}: {r['n']:,}")

# Chinese Buddhist/Taoist temples in SE Asia
print("\nChinese/Taoist temples in Southeast Asia:")
for r in db.execute("SELECT country, COUNT(*) as n FROM churches WHERE faith IN ('Taoist','Confucian') AND country NOT IN ('CN','TW','HK') GROUP BY country ORDER BY n DESC LIMIT 10"):
    print(f"  {r['country']}: {r['n']:,}")

# All faiths in Thailand (the user's specific example)
print("\nALL faiths in Thailand (Chinese shrine example):")
for r in db.execute("SELECT faith, tradition, landmark_type, COUNT(*) as n FROM churches WHERE country='TH' AND faith IS NOT NULL GROUP BY faith, tradition ORDER BY n DESC LIMIT 20"):
    print(f"  {r['faith']:15s} {str(r['tradition'])[:25]:25s} {str(r['landmark_type'])[:20]:20s} {r['n']:>8,}")

db.close()
