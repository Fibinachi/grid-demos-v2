"""Explore LDS Ward and Stake patterns precisely"""
import sqlite3
import re

db = sqlite3.connect('E:\\grid\\churches.db')
c = db.cursor()

# Find proper LDS Wards - "X Ward" or "X Ward, Y" or "X WARD" etc
# SQLite doesn't have REGEXP by default, so let's do it in Python

print("=== All entries with 'Ward' or 'Ward' as standalone word ===")
c.execute("""SELECT id, name, city, state, country, denomination, latitude, longitude
  FROM churches 
  WHERE (name LIKE '%Ward%' OR name LIKE '%WARD%')
  AND faith='Christian'
  ORDER BY name""")
all_wards = c.fetchall()
print(f"Total entries with '%Ward%': {len(all_wards)}")

# Categorize
proper_wards = []  # "X Ward" or "X Ward, Y" etc
stake_centers = []
other = []

for row in all_wards:
    name = row[1]
    # Check pattern: ends with " Ward" or contains " Ward " or starts with "Ward "
    # Also "WARD" variants
    if re.search(r'\bWard\b', name) or re.search(r'\bWARD\b', name):
        proper_wards.append(row)
    elif re.search(r'\bStake\b', name) or re.search(r'\bSTAKE\b', name):
        stake_centers.append(row)
    else:
        other.append(row)

print(f"\nProper Wards (has 'Ward' as word): {len(proper_wards)}")
print(f"Stake Centers: {len(stake_centers)}")
print(f"Other: {len(other)}")

print("\n=== Sample Proper Wards (first 50) ===")
for w in proper_wards[:50]:
    print(f"  {w[0]}: {w[1]} | {w[2]}, {w[3]} {w[4]} | denom={w[5]}")

print("\n=== Stake entries ===")
c.execute("""SELECT id, name, city, state, country, denomination
  FROM churches WHERE name LIKE '%Stake%' AND faith='Christian'
  ORDER BY name LIMIT 50""")
for row in c.fetchall():
    print(f"  {row[0]}: {row[1]} | {row[2]}, {row[3]} {row[4]} | denom={row[5]}")

print("\n=== LDS Temples with coordinates ===")
c.execute("""SELECT id, name, city, state, country, latitude, longitude
  FROM churches 
  WHERE name LIKE '%Temple%' 
  AND (denomination LIKE '%Latter%Day%' OR denomination LIKE '%LDS%' OR denomination LIKE '%Mormon%')
  AND latitude IS NOT NULL
  ORDER BY country""")
temples = c.fetchall()
print(f"Total LDS temples: {len(temples)}")
for t in temples:
    print(f"  {t[1]} | {t[2]}, {t[3]} {t[4]} | {t[5]}, {t[6]}")

# Also what about "Branch" in LDS context?
c.execute("""SELECT id, name, city, state, country FROM churches
  WHERE name LIKE '%Branch%' 
  AND (denomination LIKE '%Latter%Day%' OR denomination LIKE '%LDS%' OR denomination LIKE '%Mormon%')
  LIMIT 30""")
branches = c.fetchall()
print(f"\n=== LDS Branches ({len(branches)}) ===")
for b in branches:
    print(f"  {b[1]} | {b[2]}, {b[3]} {b[4]}")

# What about "Meetinghouse" / "Meeting house"
c.execute("""SELECT id, name, city, state, country FROM churches
  WHERE (name LIKE '%Meetinghouse%' OR name LIKE '%Meeting house%' OR name LIKE '%Meeting House%')
  AND (denomination LIKE '%Latter%Day%' OR denomination LIKE '%LDS%' OR denomination LIKE '%Mormon%')
  LIMIT 20""")
mhs = c.fetchall()
print(f"\n=== LDS Meetinghouses ({len(mhs)}) ===")
for m in mhs:
    print(f"  {m[1]} | {m[2]}, {m[3]} {m[4]}")

db.close()
