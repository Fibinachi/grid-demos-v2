"""Revert address-mangled SAINT, then survey address-in-name patterns."""
import sqlite3
import re

db = sqlite3.connect(r'E:\grid\churches.db')

# 1. Revert rowid=214216: find original from provenance or reconstruct
cur = db.execute("SELECT name FROM churches WHERE rowid = 214216")
name = cur.fetchone()[0]
print(f"rowid=214216 current name: {name}")

# The ST->SAINT expansion would have hit "ST" word boundary.
# Let's check if we can find the original in the address-like segment
# The name has "S KING SAINT" which should be "S KING ST" (South King Street)
# Check: does the name have "SAINT" followed by a digit or at end of address-like pattern?
# "S KING SAINT STE 1264" - that "SAINT" between KING and STE is the corrupted "ST"
new_name = name.replace(' S KING SAINT ', ' S KING ST ')
print(f"Reverting to: {new_name}")
db.execute("UPDATE churches SET name = ? WHERE rowid = 214216", (new_name,))
db.commit()

# 2. Survey: how many names have embedded addresses?
# Patterns that suggest address-in-name:
# - Contains a number followed by street-like word (e.g., "1234 Main St", "10616 Metromont Pkwy")
# - Contains city, state ZIP pattern (e.g., "CHARLOTTE, NC 28269")
# - Contains "STE" or "SUITE" followed by a number
# - Contains an intersection (e.g., "Main & Oak", "Main and Oak")
print("\n=== Address-in-Name Survey ===")
# Using Python regex (SQLite has no REGEXP function)
print("\nLoading sample of names for pattern analysis...")
cur = db.execute("SELECT rowid, name FROM churches WHERE LENGTH(name) > 50")
long_names = cur.fetchall()
print(f"Records with names >50 chars: {len(long_names)}")

# Count ZIP codes in names
zip_count = 0
city_state_count = 0
street_num_count = 0
suite_count = 0
intersection_count = 0
comma_country_count = 0
total = len(long_names)

zip_re = re.compile(r'\b\d{5}(-\d{4})?\b')
city_st_re = re.compile(r',\s*[A-Z]{2}\s+\d{5}')
street_num_re = re.compile(r'\b\d{1,5}\s+(?:NORTH|SOUTH|EAST|WEST|N\.?\s*|S\.?\s*|E\.?\s*|W\.?\s*)?[A-Z]')
suite_re = re.compile(r'\b(?:STE|SUITE|SUIT|UNIT|RM|ROOM)\b', re.IGNORECASE)
intersection_re = re.compile(r'\b(?:AND|&|AT|/@)\s')
comma_us = re.compile(r',\s*(?:US[A\b]|UNITED STATES)', re.IGNORECASE)

long_names_sample = long_names[:1000] if len(long_names) > 1000 else long_names

for rowid, name in long_names_sample:
    if zip_re.search(name):
        zip_count += 1
    if city_st_re.search(name):
        city_state_count += 1
    if street_num_re.search(name):
        street_num_count += 1
    if suite_re.search(name):
        suite_count += 1
    if intersection_re.search(name):
        intersection_count += 1
    if comma_us.search(name):
        comma_country_count += 1

print(f"\nSampled {len(long_names_sample)} long names:")
print(f"  Has ZIP code: {zip_count} ({zip_count/len(long_names_sample)*100:.1f}%)")
print(f"  Has city,ST ZIP: {city_state_count} ({city_state_count/len(long_names_sample)*100:.1f}%)")
print(f"  Has street number+name: {street_num_count} ({street_num_count/len(long_names_sample)*100:.1f}%)")
print(f"  Has suite/unit: {suite_count} ({suite_count/len(long_names_sample)*100:.1f}%)")
print(f"  Has intersection: {intersection_count} ({intersection_count/len(long_names_sample)*100:.1f}%)")
print(f"  Has ', US': {comma_country_count}")

# Show some examples
print("\n=== Examples of address-in-name ===")
cur = db.execute("""
    SELECT rowid, name FROM churches
    WHERE name LIKE '%STE %' OR name LIKE '%SUITE %'
    LIMIT 15
""")
for r in cur.fetchall():
    print(f"  rowid={r[0]}: {r[1][:120]}")

db.close()
