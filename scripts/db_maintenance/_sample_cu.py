import sqlite3
conn = sqlite3.connect('churches.db')

# Count
total = conn.execute("SELECT COUNT(*) FROM churches WHERE source='churchunion_scraper'").fetchone()[0]
print(f'=== {total:,} ChurchUnion churches ===')

# Show 100 random samples
rows = conn.execute("""
    SELECT id, name, address, city, state, county_name, 
           latitude, longitude, geocode_source, county_fips, tract_fips
    FROM churches 
    WHERE source = 'churchunion_scraper'
    ORDER BY RANDOM()
    LIMIT 100
""").fetchall()

print(f'Showing {len(rows)} random samples:\n')
print(f'{"ID":>7}  {"Name":40s}  {"City":15s}  {"ST":3s}  {"County":18s}  {"Lat":>9}  {"Lon":>9}  {"GeoSource":15s}  {"FIPS":6s}  {"Tract"}')
print('-' * 160)

for r in rows:
    fid, name, addr, city, state, county, lat, lon, gs, cfips, tfips = r
    print(f'{fid:>7}  {name[:40]:40s}  {city or "?":15s}  {state or "??":3s}  {county or "?":18s}  {lat or "":>9}  {lon or "":>9}  {gs or "?":15s}  {cfips or "":6s}  {tfips or ""}')

conn.close()
