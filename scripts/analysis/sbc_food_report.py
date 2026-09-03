"""SBC food desert analysis for Amy Thompson pitch."""
import sqlite3
from datetime import datetime

conn = sqlite3.connect(r'E:\grid\churches.db')
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
    WHERE denomination = 'Southern Baptist Convention'
      AND city != '' AND city IS NOT NULL
      AND name NOT LIKE '%housing%' AND name NOT LIKE '%social service%'
      AND name NOT LIKE '%foundation%' AND name NOT LIKE '%realty%'
      AND name NOT LIKE '%administrative%'
      AND name NOT LIKE '%residential%'
      AND (food_desert_low_inc_tract = 1 OR food_desert_poverty_rate > 20)
      AND has_food_pantry = 0
    ORDER BY (COALESCE(food_desert_low_inc_low_access_1_10, 0) * 3
            + CASE WHEN COALESCE(food_desert_poverty_rate, 0) > 30 THEN 3
                   WHEN COALESCE(food_desert_poverty_rate, 0) > 20 THEN 2
                   WHEN COALESCE(food_desert_poverty_rate, 0) > 15 THEN 1 ELSE 0 END
            + COALESCE(food_desert_no_vehicle_flag, 0) * 2) DESC
    LIMIT 20
""")

rows = c.fetchall()

dt = datetime.now().strftime("%B %d, %Y")
print("SBC FOOD DESERT ANALYSIS — Top 20")
print("Generated: " + dt)
print("=" * 75)
print()

for i, r in enumerate(rows, 1):
    name = r['name']
    city = r['city']
    state = r['state']
    pct = r['poverty_rate']
    inc = r['fd_income']
    lowinc = "YES" if r['food_desert_low_inc_tract'] else "no"
    noveh = "YES" if r['no_vehicle'] else "no"
    w = r['website'] or ''

    print(f"  {i:>2}. {name}")
    print(f"      {city}, {state}")
    print(f"      Tract poverty: {pct:.1f}%  |  Median income: ${inc:,.0f}")
    print(f"      Low-income tract: {lowinc}  |  No vehicle: {noveh}")
    print(f"      {w}")
    print()

states = set(r['state'] for r in rows)
avg_pov = sum(r['poverty_rate'] for r in rows) / len(rows)
no_pantry = sum(1 for r in rows if not r['has_food_pantry'])
print("=" * 75)
print(f"Summary: {len(rows)} SBC churches identified")
print(f"  All without detected food pantries")
print(f"  Avg tract poverty: {avg_pov:.1f}%")
print(f"  States: {', '.join(sorted(states))}")

conn.close()
