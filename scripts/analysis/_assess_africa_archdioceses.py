"""
Assess feasibility of assigning African Catholic churches to archdioceses.
"""
import sqlite3, json
c = sqlite3.connect('churches.db')
c.row_factory = sqlite3.Row

african_countries = ['NG','ZA','KE','ET','TZ','UG','GH','CM','CI','SN','ML','BF','BJ','TG','ZM','ZW','MZ','AO','NA','BW','MW','CD','CG','GA','GQ','ST','SL','LR','GN','GW','MR','NE','TD','CF','SS','SD','ER','DJ','SO','RW','BI','ZM','ZW','MW','MZ','AO','NA','BW','ZA','LS','SZ','KM','MG','MU','SC','CV','GM','SH']
placeholders = ','.join(['?'] * len(african_countries))

# 1. Total African Catholic churches
r = c.execute(f"SELECT COUNT(*) AS cnt FROM churches WHERE country IN ({placeholders}) AND faith='Christian' AND LOWER(denomination) LIKE '%catholic%'", african_countries).fetchone()
total = r['cnt']
print(f'Total African Catholic churches: {total}')

# 2. How many have city data?
r = c.execute(f"SELECT COUNT(*) AS cnt FROM churches WHERE country IN ({placeholders}) AND faith='Christian' AND LOWER(denomination) LIKE '%catholic%' AND city IS NOT NULL AND city != ''", african_countries).fetchone()
has_city = r['cnt']
print(f'With city data: {has_city} ({has_city/total*100:.1f}%)')

# 3. How many have GPS?
r = c.execute(f"SELECT COUNT(*) AS cnt FROM churches WHERE country IN ({placeholders}) AND faith='Christian' AND LOWER(denomination) LIKE '%catholic%' AND latitude IS NOT NULL AND longitude IS NOT NULL", african_countries).fetchone()
has_gps = r['cnt']
print(f'With GPS coords: {has_gps} ({has_gps/total*100:.1f}%)')

# 4. How many have city AND GPS?
r = c.execute(f"SELECT COUNT(*) AS cnt FROM churches WHERE country IN ({placeholders}) AND faith='Christian' AND LOWER(denomination) LIKE '%catholic%' AND city IS NOT NULL AND city != '' AND latitude IS NOT NULL", african_countries).fetchone()
has_both = r['cnt']
print(f'With both city + GPS: {has_both} ({has_both/total*100:.1f}%)')

# 5. Per-country breakdown
print('\nCatholic churches per African country:')
for row in c.execute(f"""
    SELECT country, COUNT(*) AS cnt, 
           SUM(CASE WHEN city IS NOT NULL AND city != '' THEN 1 ELSE 0 END) AS with_city,
           SUM(CASE WHEN latitude IS NOT NULL THEN 1 ELSE 0 END) AS with_gps
    FROM churches 
    WHERE country IN ({placeholders}) 
    AND faith='Christian' AND LOWER(denomination) LIKE '%catholic%'
    GROUP BY country ORDER BY cnt DESC
""", african_countries):
    print(f'  {row["country"]}: {row["cnt"]} churches ({row["with_city"]} city, {row["with_gps"]} GPS)')

# 6. Top cities per country (sample Nigeria)
print('\nTop Nigerian cities with Catholic churches:')
for row in c.execute("""
    SELECT city, COUNT(*) AS cnt FROM churches 
    WHERE country='NG' AND faith='Christian' AND LOWER(denomination) LIKE '%catholic%'
    AND city IS NOT NULL AND city != ''
    GROUP BY city ORDER BY cnt DESC LIMIT 30
"""):
    print(f'  {row["city"]}: {row["cnt"]}')

# 7. Check if we can fetch African archdioceses from web
print('\n\n=== Feasibility Summary ===')
print(f'Churches to assign: {total}')
print(f'  With city -> can map to archdiocese by city: {has_city} ({has_city/total*100:.1f}%)')
print(f'  With GPS -> can map by proximity: {has_gps} ({has_gps/total*100:.1f}%)')
print(f'  With both -> best precision: {has_both} ({has_both/total*100:.1f}%)')

# Estimate how many archdioceses needed
countries_with_catholics = [r['country'] for r in c.execute(f"""
    SELECT DISTINCT country FROM churches 
    WHERE country IN ({placeholders}) 
    AND faith='Christian' AND LOWER(denomination) LIKE '%catholic%'
""", african_countries)]
print(f'Countries with Catholic churches: {len(countries_with_catholics)}')

c.close()
