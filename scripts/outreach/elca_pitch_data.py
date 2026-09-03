"""Generate CSV report + email draft for Adam DeHoek."""
import sqlite3, os, csv
from datetime import datetime

conn = sqlite3.connect('churches.db')
conn.row_factory = sqlite3.Row
c = conn.cursor()

c.execute("""
    SELECT id, name, city, state, zip,
           COALESCE(food_desert_low_inc_low_access_1_10, 0) as fd_lowinc,
           COALESCE(food_desert_poverty_rate, 0) as poverty_rate,
           COALESCE(food_desert_median_family_income, 0) as fd_income,
           has_food_pantry,
           food_desert_low_inc_tract,
           COALESCE(food_desert_no_vehicle_flag, 0) as no_vehicle,
           website, phone
    FROM churches 
    WHERE denomination = 'Evangelical Lutheran Church in America'
      AND city != '' AND city IS NOT NULL
      AND name NOT LIKE '%housing%' AND name NOT LIKE '%social service%'
      AND name NOT LIKE '%foundation%' AND name NOT LIKE '%realty%'
      AND name NOT LIKE '%administrative%' AND name NOT LIKE '%campus ministry%'
      AND name NOT LIKE '%residential%' AND name NOT LIKE '%community service%'
      AND (food_desert_low_inc_tract = 1 OR food_desert_poverty_rate > 15)
    ORDER BY (COALESCE(food_desert_low_inc_low_access_1_10, 0) * 3
            + CASE WHEN COALESCE(food_desert_poverty_rate, 0) > 25 THEN 3
                   WHEN COALESCE(food_desert_poverty_rate, 0) > 18 THEN 2
                   WHEN COALESCE(food_desert_poverty_rate, 0) > 12 THEN 1 ELSE 0 END
            + COALESCE(food_desert_no_vehicle_flag, 0) * 2) DESC
    LIMIT 25
""")

rows = c.fetchall()

# CSV
reports_dir = os.path.join(os.getcwd(), 'data', 'reports')
os.makedirs(reports_dir, exist_ok=True)
csv_path = os.path.join(reports_dir, 'elca_food_desert_top25.csv')

with open(csv_path, 'w', newline='') as f:
    w = csv.writer(f)
    w.writerow(['Rank','Church','City','State','ZIP','Tract Poverty %',
                'Median Income','Low-Income Tract','No Vehicle Access',
                'Has Food Pantry','Website','Phone'])
    for i, r in enumerate(rows, 1):
        w.writerow([i, r['name'], r['city'], r['state'], r['zip'],
                   round(r['poverty_rate'],1), r['fd_income'],
                   'Yes' if r['food_desert_low_inc_tract'] else 'No',
                   'Yes' if r['no_vehicle'] else 'No',
                   'Yes' if r['has_food_pantry'] else 'No',
                   r['website'] or '', r['phone'] or ''])

print(f"CSV: {csv_path}")

# Top 5 stats for the pitch
worst = rows[0]
print(f"\nWorst church: {worst['name']} in {worst['city']}, {worst['state']}")
print(f"  Poverty: {worst['poverty_rate']:.1f}%, Income: ${worst['fd_income']:,.0f}")

avg_pov = sum(r['poverty_rate'] for r in rows) / len(rows)
print(f"Avg poverty across 25: {avg_pov:.1f}%")

pct_no_pantry = sum(1 for r in rows if not r['has_food_pantry']) / len(rows) * 100
print(f"No food pantry: {pct_no_pantry:.0f}%")

pct_lowinc = sum(1 for r in rows if r['food_desert_low_inc_tract']) / len(rows) * 100
print(f"Low-income tract: {pct_lowinc:.0f}%")

states = set(r['state'] for r in rows)
print(f"States represented: {', '.join(sorted(states))}")

pct_noveh = sum(1 for r in rows if r['no_vehicle']) / len(rows) * 100
print(f"No vehicle access: {pct_noveh:.0f}%")

conn.close()
