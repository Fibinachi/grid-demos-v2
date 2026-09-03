"""SBC food desert analysis using ZIP-level ACS data."""
import sqlite3
conn = sqlite3.connect('churches.db')
c = conn.cursor()

# How many SBC directory churches have ZIP-level poverty data?
c.execute("""
    SELECT COUNT(1) FROM churches c
    JOIN census_zip_data cz ON cz.zip5 = c.zip AND cz.year = 2022
    WHERE c.classification_source IN ('sbc_directory','sbc_scrape')
    AND cz.poverty_rate > 20
""")
print(f"SBC directory churches in high-poverty ZIPS (>20%): {c.fetchone()[0]:,}")

print("\nTop 20 SBC churches in highest-poverty ZIPS:")
print()
c.execute("""
    SELECT c.name, c.city, c.state, 
           cz.poverty_rate, cz.median_hh_income, 
           cz.pct_bachelors, cz.snap_pct
    FROM churches c
    JOIN census_zip_data cz ON cz.zip5 = c.zip AND cz.year = 2022
    WHERE c.classification_source IN ('sbc_directory','sbc_scrape')
    AND cz.poverty_rate BETWEEN 10 AND 60  -- Sanity filter on ACS data
    AND cz.median_hh_income BETWEEN 10000 AND 250000
    ORDER BY cz.poverty_rate DESC
    LIMIT 20
""")
for r in c.fetchall():
    print(f"  {r[0][:40]:40s} {r[1]+', '+r[2]:20s} {r[3]:.1f}%  ${r[4]:,.0f}  BA:{r[5]:.0f}%  SNAP:{r[6]:.0f}%")

c.execute("""
    SELECT COUNT(1) FROM churches c
    JOIN census_zip_data cz ON cz.zip5 = c.zip AND cz.year = 2022
    WHERE c.classification_source IN ('sbc_directory','sbc_scrape')
    AND cz.poverty_rate BETWEEN 10 AND 60
    AND cz.median_hh_income BETWEEN 10000 AND 250000
    AND cz.poverty_rate > 20
""")
print(f"\nSBC churches in high-poverty ZIPS (clean data): {c.fetchone()[0]:,}")

c.execute("""
    SELECT AVG(cz.poverty_rate), AVG(cz.median_hh_income)
    FROM churches c
    JOIN census_zip_data cz ON cz.zip5 = c.zip AND cz.year = 2022
    WHERE c.classification_source IN ('sbc_directory','sbc_scrape')
    AND cz.poverty_rate BETWEEN 10 AND 60
    AND cz.median_hh_income BETWEEN 10000 AND 250000
    AND cz.poverty_rate > 20
""")
r = c.fetchone()
print(f"Avg poverty: {r[0]:.1f}%  |  Avg income: ${r[1]:,.0f}")

conn.close()
