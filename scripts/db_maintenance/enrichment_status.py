import sqlite3

db = sqlite3.connect('churches.db')
c = db.cursor()

print('=== DB OVERVIEW ===')
try:
    c.execute('SELECT COUNT(*) FROM churches')
    print(f'Total churches: {c.fetchone()[0]:,}')
except Exception as e:
    print(f'churches table: {e}')

print()
print('=== ANALYTIC TABLES ===')
for tbl in ['church_address_history', 'org_links', 'org_officers', 'arda_county_data', 
            'census_zip_data', 'tract_acs_data', 'fcc_broadcast_data', 'irs_990_data',
            'arda_counts']:
    try:
        c.execute(f'SELECT COUNT(*) FROM "{tbl}"')
        print(f'{tbl}: {c.fetchone()[0]:,}')
    except Exception as e:
        print(f'{tbl}: FAIL - {str(e)[:60]}')

print()
print('=== CHURCHES TABLE ENRICHMENT COLUMNS ===')
checks = [
    ('website', "SELECT COUNT(*) FROM churches WHERE website IS NOT NULL AND website != ''"),
    ('email', "SELECT COUNT(*) FROM churches WHERE email IS NOT NULL AND email != ''"),
    ('phone', "SELECT COUNT(*) FROM churches WHERE phone IS NOT NULL AND phone != ''"),
    ('estimated_attendance', "SELECT COUNT(*) FROM churches WHERE estimated_attendance > 0"),
    ('denomination', "SELECT COUNT(*) FROM churches WHERE denomination IS NOT NULL AND denomination != ''"),
    ('latitude', "SELECT COUNT(*) FROM churches WHERE latitude IS NOT NULL"),
    ('county_fips_5', "SELECT COUNT(*) FROM churches WHERE county_fips_5 IS NOT NULL AND county_fips_5 != ''"),
    ('has_school', "SELECT COUNT(*) FROM churches WHERE has_school IS NOT NULL AND has_school != ''"),
    ('food_desert_tract', "SELECT COUNT(*) FROM churches WHERE food_desert_tract IS NOT NULL AND food_desert_tract != ''"),
    ('address_standardized', "SELECT COUNT(*) FROM churches WHERE address_standardized IS NOT NULL AND address_standardized != ''"),
    ('website_scrape_status', "SELECT COUNT(*) FROM churches WHERE website_scrape_status IS NOT NULL AND website_scrape_status != ''"),
    ('email_scrape_status', "SELECT COUNT(*) FROM churches WHERE email_scrape_status IS NOT NULL AND email_scrape_status != ''"),
    ('attendance_confidence', "SELECT COUNT(*) FROM churches WHERE attendance_confidence > 0"),
]
for name, sql in checks:
    try:
        c.execute(sql)
        print(f'{name}: {c.fetchone()[0]:,}')
    except Exception as e:
        print(f'{name}: FAIL - {str(e)[:60]}')

print()
print('=== SOURCE DISTRIBUTION ===')
try:
    c.execute('SELECT source, COUNT(*) FROM churches GROUP BY source ORDER BY COUNT(*) DESC LIMIT 10')
    for row in c.fetchall():
        print(f'  {row[0]}: {row[1]:,}')
except Exception as e:
    print(f'Source: FAIL - {e}')

print()
print('=== TOP DENOMINATIONS ===')
try:
    c.execute("SELECT denomination, COUNT(*) FROM churches WHERE denomination IS NOT NULL AND denomination != '' GROUP BY denomination ORDER BY COUNT(*) DESC LIMIT 12")
    for row in c.fetchall():
        print(f'  {row[0]}: {row[1]:,}')
except Exception as e:
    print(f'Denom: FAIL - {e}')

# Extra: total attendance sum
try:
    c.execute('SELECT SUM(estimated_attendance) FROM churches')
    val = c.fetchone()[0]
    print(f'Total estimated attendance: {int(val):,}')
except Exception as e:
    print(f'Total attendance: FAIL - {e}')

# Extra: food desert columns
for col in ['food_desert_tract', 'food_desert_low_access', 'food_desert_low_income']:
    try:
        c.execute(f'SELECT COUNT(*) FROM churches WHERE "{col}" IS NOT NULL')
        print(f'{col}: {c.fetchone()[0]:,}')
    except:
        pass

db.close()
print()
print('Done.')
