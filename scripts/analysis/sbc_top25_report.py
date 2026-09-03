"""SBC top 25 national + SC — clean data for Amy Thompson pitch."""
import sqlite3
conn = sqlite3.connect('churches.db')
c = conn.cursor()

print("=" * 70)
print("TOP 25 SBC CHURCHES IN HIGHEST-POVERTY ZIPS (NATIONAL)")
print("=" * 70)
print()

c.execute("""
    SELECT c.name, c.city, c.state, c.zip,
           cz.poverty_rate, cz.median_hh_income,
           c.website, c.phone, c.id
    FROM churches c
    JOIN census_zip_data cz ON cz.zip5 = c.zip AND cz.year = 2022
    WHERE c.classification_source IN ('sbc_directory','sbc_scrape')
    AND cz.poverty_rate BETWEEN 15 AND 60
    AND cz.median_hh_income BETWEEN 10000 AND 250000
    AND c.city != '' AND c.state != ''
    ORDER BY cz.poverty_rate DESC
    LIMIT 25
""")

for i, r in enumerate(c.fetchall(), 1):
    name, city, state, zipcode = r[0], r[1], r[2], r[3]
    pct, inc = r[4], r[5]
    web, phone = (r[6] or ''), (r[7] or '')
    print(f"  {i:>2}. {name}")
    print(f"      {city}, {state} {zipcode}")
    print(f"      ZIP poverty: {pct:.1f}%  |  Median income: ${inc:,.0f}")
    print(f"      {web}  {phone}")
    print()

# Count national
c.execute("""
    SELECT COUNT(1) FROM churches c
    JOIN census_zip_data cz ON cz.zip5 = c.zip AND cz.year = 2022
    WHERE c.classification_source IN ('sbc_directory','sbc_scrape')
    AND cz.poverty_rate BETWEEN 15 AND 60
    AND cz.median_hh_income BETWEEN 10000 AND 250000
    AND cz.poverty_rate > 20
""")
nat_count = c.fetchone()[0]

c.execute("""
    SELECT AVG(cz.poverty_rate), AVG(cz.median_hh_income)
    FROM churches c
    JOIN census_zip_data cz ON cz.zip5 = c.zip AND cz.year = 2022
    WHERE c.classification_source IN ('sbc_directory','sbc_scrape')
    AND cz.poverty_rate BETWEEN 15 AND 60
    AND cz.median_hh_income BETWEEN 10000 AND 250000
    AND cz.poverty_rate > 20
""")
r = c.fetchone()
print(f"  National total: {nat_count:,} SBC churches in high-poverty ZIPS")
print(f"  Avg poverty: {r[0]:.1f}%  |  Avg income: ${r[1]:,.0f}")
print()

print("=" * 70)
print("TOP 25 SBC CHURCHES IN HIGHEST-POVERTY ZIPS (SOUTH CAROLINA)")
print("=" * 70)
print()

c.execute("""
    SELECT c.name, c.city, c.zip,
           cz.poverty_rate, cz.median_hh_income,
           c.website, c.phone, c.id
    FROM churches c
    JOIN census_zip_data cz ON cz.zip5 = c.zip AND cz.year = 2022
    WHERE c.classification_source IN ('sbc_directory','sbc_scrape')
    AND c.state = 'SC'
    AND cz.poverty_rate BETWEEN 10 AND 60
    AND cz.median_hh_income BETWEEN 10000 AND 250000
    AND c.city != ''
    ORDER BY cz.poverty_rate DESC
    LIMIT 25
""")

for i, r in enumerate(c.fetchall(), 1):
    name, city, zipcode = r[0], r[1], r[2]
    pct, inc = r[3], r[4]
    web, phone = (r[5] or ''), (r[6] or '')
    print(f"  {i:>2}. {name}")
    print(f"      {city}, SC {zipcode}")
    print(f"      ZIP poverty: {pct:.1f}%  |  Median income: ${inc:,.0f}")
    print(f"      {web}  {phone}")
    print()

# SC summary
c.execute("""
    SELECT COUNT(1), AVG(cz.poverty_rate), AVG(cz.median_hh_income)
    FROM churches c
    JOIN census_zip_data cz ON cz.zip5 = c.zip AND cz.year = 2022
    WHERE c.classification_source IN ('sbc_directory','sbc_scrape')
    AND c.state = 'SC'
    AND cz.poverty_rate BETWEEN 10 AND 60
    AND cz.median_hh_income BETWEEN 10000 AND 250000
""")
r = c.fetchone()
print(f"  SC total SBC churches with poverty data: {r[0]:,}")
print(f"  SC avg poverty: {r[1]:.1f}%  |  SC avg income: ${r[2]:,.0f}")

c.execute("""
    SELECT COUNT(1) FROM churches c
    JOIN census_zip_data cz ON cz.zip5 = c.zip AND cz.year = 2022
    WHERE c.classification_source IN ('sbc_directory','sbc_scrape')
    AND c.state = 'SC'
    AND cz.poverty_rate > 20
""")
sc_pov = c.fetchone()[0]
print(f"  SC SBC churches in high-poverty ZIPS (>20%): {sc_pov:,}")

conn.close()
