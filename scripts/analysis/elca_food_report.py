"""Clean ELCA food+poverty report for Adam DeHoek pitch."""
import sqlite3
from datetime import datetime

conn = sqlite3.connect('churches.db')
conn.row_factory = sqlite3.Row
c = conn.cursor()

c.execute("""
    SELECT id, name, city, state, zip,
           COALESCE(food_desert_low_inc_low_access_1_10, 0) as fd_lowinc,
           COALESCE(food_desert_poverty_rate, 0) as poverty_rate,
           COALESCE(food_desert_median_family_income, 0) as fd_income,
           COALESCE(census_median_hh_income, 0) as income,
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

dt = datetime.now().strftime("%B %d, %Y")
print("Top 25 ELCA Churches in High-Need Food Deserts")
print("Generated: " + dt)
print("=" * 70)
print()

needs_pantry = 0
has_pantry = 0

for i, r in enumerate(rows, 1):
    name = r['name']
    city = r['city']
    state = r['state']
    zipcode = r['zip'] or ''
    pct = r['poverty_rate']
    inc = r['fd_income'] if r['fd_income'] else r['income']
    lowinc = "YES" if r['food_desert_low_inc_tract'] else "no"
    noveh = "YES" if r['no_vehicle'] else "no"
    pantry = "** NO food pantry **" if not r['has_food_pantry'] else "HAS food pantry"
    if r['has_food_pantry']:
        has_pantry += 1
    else:
        needs_pantry += 1
    w = r['website'] or ''
    p = r['phone'] or ''

    print("  " + str(i).rjust(2) + ". " + name)
    print("      " + city + ", " + state + " " + zipcode)
    print("      Tract poverty: " + f"{pct:.1f}%" + "  |  Median income: $" + f"{inc:,.0f}")
    print("      Low-income tract: " + lowinc + "  |  No vehicle: " + noveh)
    print("      " + pantry)
    print("      " + w + "  " + p)
    print()

print("=" * 70)
print("Summary: " + str(len(rows)) + " ELCA churches identified")
print("  " + str(needs_pantry) + " without food pantries (gap)")
print("  " + str(has_pantry) + " with food pantries (model programs)")
print("=" * 70)

conn.close()
