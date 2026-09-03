"""Explore name fields in churches.db to plan transliteration."""

import sqlite3
import re

db = sqlite3.connect("E:\\grid\\churches.db")

# 1. Check name_original
cur = db.execute("SELECT COUNT(*) FROM churches WHERE name_original IS NOT NULL AND name_original != ''")
print(f"Records with name_original populated: {cur.fetchone()[0]}")

# 2. Check normalized_name
cur = db.execute("SELECT COUNT(*) FROM churches WHERE normalized_name IS NOT NULL AND normalized_name != ''")
print(f"Records with normalized_name populated: {cur.fetchone()[0]}")

# 3. Sample normalized_name values
print("\n=== Sample normalized_name (first 20) ===")
for r in db.execute("SELECT name, normalized_name FROM churches WHERE normalized_name IS NOT NULL AND normalized_name != '' LIMIT 20"):
    print(f"  name={r[0][:70]!r}")
    print(f"  norm={r[1][:70]!r}")
    print()

# 4. Check which scripts are in the name field
# Define non-roman regex patterns
scripts = {
    "Cyrillic": re.compile(r'[\u0400-\u04FF]'),
    "Greek": re.compile(r'[\u0370-\u03FF]'),
    "Arabic": re.compile(r'[\u0600-\u06FF]'),
    "Hebrew": re.compile(r'[\u0590-\u05FF]'),
    "Devanagari": re.compile(r'[\u0900-\u097F]'),
    "CJK": re.compile(r'[\u4E00-\u9FFF\u3400-\u4DBF]'),
    "Hiragana": re.compile(r'[\u3040-\u309F]'),
    "Katakana": re.compile(r'[\u30A0-\u30FF]'),
    "Hangul": re.compile(r'[\uAC00-\uD7AF]'),
    "Thai": re.compile(r'[\u0E00-\u0E7F]'),
    "Tamil": re.compile(r'[\u0B80-\u0BFF]'),
    "Gurmukhi": re.compile(r'[\u0A00-\u0A7F]'),
    "Bengali": re.compile(r'[\u0980-\u09FF]'),
    "Georgian": re.compile(r'[\u10A0-\u10FF]'),
    "Armenian": re.compile(r'[\u0530-\u058F]'),
    "Myanmar": re.compile(r'[\u1000-\u109F]'),
    "Khmer": re.compile(r'[\u1780-\u17FF]'),
    "Lao": re.compile(r'[\u0E80-\u0EFF]'),
    "Sinhala": re.compile(r'[\u0D80-\u0DFF]'),
    "Tibetan": re.compile(r'[\u0F00-\u0FFF]'),
    "Ethiopic": re.compile(r'[\u1200-\u137F]'),
}

print("\n=== Script detection in name field ===")
print("(Using Python-side detection due to SQLite REGEXP limitations)")

# Do Python-side counting instead with a cursor
print("(Using Python-side detection due to SQLite REGEXP limitations)")
counts = {}
name_rows = db.execute("SELECT id, name FROM churches WHERE name IS NOT NULL AND name != ''")
processed = 0
non_roman_ids = []

for row in name_rows:
    rid, rname = row
    processed += 1
    found_scripts = []
    for sname, spattern in scripts.items():
        if spattern.search(rname):
            found_scripts.append(sname)
    if found_scripts:
        non_roman_ids.append((rid, rname[:80], found_scripts))
        key = "+".join(sorted(found_scripts))
        counts[key] = counts.get(key, 0) + 1

print(f"\nProcessed {processed} name rows")
print(f"\nRecords with non-Roman script in name: {len(non_roman_ids)}")
print(f"\n=== Script breakdown ===")
for key in sorted(counts, key=counts.get, reverse=True):
    print(f"  {key:40s} {counts[key]:>8,}")

# Show some examples of each major script
print("\n=== Examples by script type ===")
shown = set()
for rid, rname, scripts_found in non_roman_ids:
    key = "+".join(sorted(scripts_found))
    if key not in shown:
        print(f"\n  [{key}] id={rid}")
        print(f"    {rname}")
        shown.add(key)
        if len(shown) >= 20:
            break

db.close()
