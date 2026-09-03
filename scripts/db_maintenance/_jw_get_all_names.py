"""Export all unique JW-related names for analysis."""
import sqlite3, json

conn = sqlite3.connect(r'E:\grid\churches.db')
c = conn.cursor()

# Get all unique names with counts, city status, country
rows = c.execute("""
    SELECT name, COUNT(*) as cnt,
           SUM(CASE WHEN city IS NOT NULL AND city != '' AND city != 'None' THEN 1 ELSE 0 END) as has_city,
           country
    FROM churches 
    WHERE (name LIKE '%Kingdom%Hall%' OR name LIKE '%Jehovah%' OR name LIKE '%Jehova%'
       OR name LIKE '%Salon%Reino%' OR name LIKE '%Salon%Reino%' OR name LIKE '%Salao%Reino%'
       OR name LIKE '%Salao%Reino%' OR name LIKE '%Assembly%Hall%Jehov%'
       OR name LIKE '%Testigos%Jehova%' OR name LIKE '%Testemunha%Jeova%'
       OR name LIKE '%Witnesses%' OR name LIKE '%Witness%Kingdom%')
    AND name NOT LIKE '%Universal%' AND name NOT LIKE '%IURD%'
    GROUP BY name
    ORDER BY cnt DESC
""").fetchall()

print(f'Total unique names: {len(rows)}')
print(f'Total entries: {sum(r[1] for r in rows):,}')
print()

for name, cnt, has_city, country in rows:
    # Sample countries (first 3)
    print(f'[{cnt:4d}][c:{has_city:4d}] {name[:120]}')

conn.close()
