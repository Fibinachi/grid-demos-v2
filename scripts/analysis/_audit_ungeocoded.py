"""Data quality check on ungeocoded US Catholic 'churches'."""
import sqlite3
c = sqlite3.connect('churches.db').cursor()

c.execute("""SELECT id, name, denomination, address, city, state, zip, source,
  CASE 
    WHEN address IS NOT NULL AND address != '' THEN 'has_address'
    WHEN city IS NOT NULL AND city != '' THEN 'has_city'
    WHEN (name IS NULL OR name = '') THEN 'no_name'
    WHEN name LIKE '%PRAYER%' OR name LIKE '%HOPE%' OR name LIKE '%DISPENSATION%' THEN 'religious_text'
    WHEN name LIKE '%EXAMINE%' OR name LIKE '%REPORT%' OR name LIKE '%UNVEILS%' THEN 'news_article'
    WHEN name LIKE '%MERGE%' OR name LIKE '%FORM%' THEN 'administrative'
    ELSE 'other_no_address'
  END as category
  FROM churches
  WHERE country='US' 
  AND (LOWER(denomination) LIKE '%catholic%' OR LOWER(denomination) LIKE '%roman%')
  AND (latitude IS NULL OR longitude IS NULL)
""")
rows = c.fetchall()

# Categorize
cats = {}
for r in rows:
    cat = r[7]  # category
    cats[cat] = cats.get(cat, 0) + 1

print(f"Total ungeocoded US Catholic: {len(rows):,}\n")
print("Categories:")
for cat, cnt in sorted(cats.items(), key=lambda x: -x[1]):
    pct = 100 * cnt / len(rows)
    print(f"  {cat:20s} {cnt:>7,} ({pct:.0f}%)")

# Show samples of each category
print("\n=== Samples by category ===")
shown = set()
for r in rows:
    cat = r[7]
    if cat not in shown:
        shown.add(cat)
        print(f"\n--- {cat} ---")
        count = 0
        for rr in rows:
            if rr[7] == cat and count < 5:
                print(f'  {rr[0]:>8} name={str(rr[1] or "")[:60]}')
                print(f'           addr={str(rr[3] or "")[:40]} city={rr[4]} state={rr[5]} source={rr[6]}')
                count += 1

# Check source distribution
print("\n=== Source distribution ===")
c.execute("""SELECT source, COUNT(*) FROM churches
  WHERE country='US' 
  AND (LOWER(denomination) LIKE '%catholic%' OR LOWER(denomination) LIKE '%roman%')
  AND (latitude IS NULL OR longitude IS NULL)
  GROUP BY source ORDER BY COUNT(*) DESC LIMIT 15""")
for r in c.fetchall():
    print(f'  {str(r[0] or "NULL"):30s} {r[1]:>7,}')

# How many look like real parishes (have address or city)?
c.execute("""SELECT COUNT(*) FROM churches
  WHERE country='US' 
  AND (LOWER(denomination) LIKE '%catholic%' OR LOWER(denomination) LIKE '%roman%')
  AND (latitude IS NULL OR longitude IS NULL)
  AND ((address IS NOT NULL AND address != '') OR (city IS NOT NULL AND city != ''))""")
print(f'\nReal parishes (with address or city): {c.fetchone()[0]:,}')

# How many have ANY useful data?
c.execute("""SELECT COUNT(*) FROM churches
  WHERE country='US' 
  AND (LOWER(denomination) LIKE '%catholic%' OR LOWER(denomination) LIKE '%roman%')
  AND (latitude IS NULL OR longitude IS NULL)
  AND name IS NOT NULL AND name != ''""")
print(f'Have name: {c.fetchone()[0]:,}')
