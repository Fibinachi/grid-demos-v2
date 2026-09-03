import sqlite3
db = sqlite3.connect('E:/grid/churches.db')

# Check classification of CRA churches vs all CA
for label, where in [
    ("CRA 2018", "source='cra_2018'"),
    ("CRA 2011", "source='cra_2011'"),
    ("All Canada", "country='CA'"),
    ("All US", "country IS NULL OR country='US'"),
]:
    total = db.execute(f"SELECT COUNT(*) FROM churches WHERE {where}").fetchone()[0]
    has_denom = db.execute(f"SELECT COUNT(*) FROM churches WHERE {where} AND denomination IS NOT NULL AND denomination != ''").fetchone()[0]
    has_family = db.execute(f"SELECT COUNT(*) FROM churches WHERE {where} AND family IS NOT NULL AND family != ''").fetchone()[0]
    has_subtrad = db.execute(f"SELECT COUNT(*) FROM churches WHERE {where} AND subtradition IS NOT NULL").fetchone()[0]
    has_classification = db.execute(f"SELECT COUNT(*) FROM churches WHERE {where} AND classification_source IS NOT NULL").fetchone()[0]
    has_coords = db.execute(f"SELECT COUNT(*) FROM churches WHERE {where} AND latitude IS NOT NULL AND latitude != 0").fetchone()[0]
    
    print(f"\n{label} ({total:,} total):")
    print(f"  Has denomination:    {has_denom:,} ({100*has_denom/max(total,1):.0f}%)")
    print(f"  Has family:          {has_family:,} ({100*has_family/max(total,1):.0f}%)")
    print(f"  Has subtradition:    {has_subtrad:,} ({100*has_subtrad/max(total,1):.0f}%)")
    print(f"  Has class_source:    {has_classification:,} ({100*has_classification/max(total,1):.0f}%)")
    print(f"  Has coordinates:     {has_coords:,} ({100*has_coords/max(total,1):.0f}%)")

# Breakdown of CRA denomination labels
print("\n--- CRA 2018 denomination breakdown ---")
for d, c in db.execute("SELECT denomination, COUNT(*) FROM churches WHERE source='cra_2018' GROUP BY denomination ORDER BY COUNT(*) DESC"):
    print(f"  {d}: {c:,}")

print("\n--- CRA 2011 denomination breakdown ---")
for d, c in db.execute("SELECT denomination, COUNT(*) FROM churches WHERE source='cra_2011' GROUP BY denomination ORDER BY COUNT(*) DESC"):
    print(f"  {d}: {c:,}")

# Check if any have the name-based classifier results
print("\n--- Classification sources on CRA data ---")
for s, c in db.execute("SELECT classification_source, COUNT(*) FROM churches WHERE source IN ('cra_2018','cra_2011') AND classification_source IS NOT NULL GROUP BY classification_source"):
    print(f"  {s}: {c:,}")

db.close()
