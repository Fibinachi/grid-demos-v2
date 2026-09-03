"""
Check address quality of null-GPS records to determine what geocoding approaches work.
"""
import sqlite3

db = sqlite3.connect('E:/grid/churches.db')

def q(qry):
    return db.execute(qry).fetchone()[0]

print("=== Address Quality for Null-GPS Records ===")
print()

# How many null-GPS have each level of address detail?
total_null = q("SELECT COUNT(1) FROM churches WHERE latitude IS NULL AND longitude IS NULL")
print(f"Total null-GPS records: {total_null:,}")
print()

with_street = q("SELECT COUNT(1) FROM churches WHERE latitude IS NULL AND longitude IS NULL AND address IS NOT NULL AND address != ''")
with_city    = q("SELECT COUNT(1) FROM churches WHERE latitude IS NULL AND longitude IS NULL AND city IS NOT NULL AND city != ''")
with_state   = q("SELECT COUNT(1) FROM churches WHERE latitude IS NULL AND longitude IS NULL AND state IS NOT NULL AND state != ''")
with_zip     = q("SELECT COUNT(1) FROM churches WHERE latitude IS NULL AND longitude IS NULL AND zip IS NOT NULL AND zip != ''")
us_only      = q("SELECT COUNT(1) FROM churches WHERE latitude IS NULL AND longitude IS NULL AND country='US'")

print(f"Null-GPS with:")
print(f"  Street address: {with_street:,}")
print(f"  City:           {with_city:,}")
print(f"  State:          {with_state:,}")
print(f"  ZIP:            {with_zip:,}")
print(f"  US country:     {us_only:,}")
print()

# Geocodable via different methods
us_full_addr = q("SELECT COUNT(1) FROM churches WHERE latitude IS NULL AND longitude IS NULL AND country='US' AND address IS NOT NULL AND address != '' AND city IS NOT NULL AND city != '' AND state IS NOT NULL AND state != ''")
us_city_state = q("SELECT COUNT(1) FROM churches WHERE latitude IS NULL AND longitude IS NULL AND country='US' AND city IS NOT NULL AND city != '' AND state IS NOT NULL AND state != ''")
us_state_only = q("SELECT COUNT(1) FROM churches WHERE latitude IS NULL AND longitude IS NULL AND country='US' AND state IS NOT NULL AND state != '' AND (city IS NULL OR city = '')")

print(f"Geocodable US records:")
print(f"  Street + city + state (Census street): {us_full_addr:,}")
print(f"  City + state (ZIP centroid):           {us_city_state:,}")
print(f"  State only (state centroid):           {us_state_only:,}")
print()

# Non-US breakdown
non_us = q("SELECT COUNT(1) FROM churches WHERE latitude IS NULL AND longitude IS NULL AND (country IS NULL OR country != 'US')")
print(f"Non-US null-GPS: {non_us:,}")
for r in db.execute("""
    SELECT COALESCE(country,'NULL'), COUNT(1) 
    FROM churches WHERE latitude IS NULL AND longitude IS NULL 
    AND (country IS NULL OR country != 'US')
    GROUP BY country ORDER BY COUNT(1) DESC
""").fetchall():
    print(f"  {r[0]}: {r[1]:,}")

# How many have lat/lon in church_addresses but not churches?
addr_copy = q("""
    SELECT COUNT(DISTINCT c.rowid) FROM churches c
    JOIN church_addresses ca ON ca.church_rowid = c.rowid
    WHERE c.latitude IS NULL AND c.longitude IS NULL
    AND ca.latitude IS NOT NULL AND ca.longitude IS NOT NULL
""")
print(f"\nQuick win — lat/lon in church_addresses, not in churches: {addr_copy:,}")

db.close()
