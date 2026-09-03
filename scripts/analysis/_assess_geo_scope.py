"""Quick assessment of geo enrichment scope"""
import sqlite3

conn = sqlite3.connect('E:\\grid\\churches.db')
c = conn.cursor()

total = c.execute('SELECT COUNT(*) FROM churches').fetchone()[0]
print(f'Total churches: {total:,}')

gps = c.execute('SELECT COUNT(*) FROM churches WHERE latitude IS NOT NULL AND longitude IS NOT NULL').fetchone()[0]
print(f'Total with GPS: {gps:,} ({gps/total*100:.1f}%)')

no_country = c.execute("SELECT COUNT(*) FROM churches WHERE latitude IS NOT NULL AND longitude IS NOT NULL AND (country IS NULL OR country = '')").fetchone()[0]
print(f'GPS but no country: {no_country:,}')

no_state = c.execute("SELECT COUNT(*) FROM churches WHERE latitude IS NOT NULL AND longitude IS NOT NULL AND country IS NOT NULL AND country != '' AND (state IS NULL OR state = '')").fetchone()[0]
print(f'GPS+country but no state: {no_state:,}')

# Check what countries have state coverage in state_borders
conn2 = sqlite3.connect('E:\\grid\\data\\natural_earth\\world_borders.db')
c2 = conn2.cursor()
c2.execute('SELECT DISTINCT country_name FROM state_borders ORDER BY country_name')
countries = [r[0] for r in c2.fetchall()]
print(f'\nAdmin 1 countries: {countries}')

# Check if iso_a2 is in state_borders
c2.execute('PRAGMA table_info(state_borders)')
print('\nstate_borders columns:')
for col in c2.fetchall():
    print(f'  {col[1]:20s} {col[2]:15s}')

conn.close()
conn2.close()
