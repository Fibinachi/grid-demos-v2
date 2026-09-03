"""Check what's currently in name_original and understand transliteration needs."""

import sqlite3

db = sqlite3.connect("E:\\grid\\churches.db")

# Sample name_original contents
print("=== name_original samples ===")
cur = db.execute("SELECT name, name_original FROM churches WHERE name_original IS NOT NULL AND name_original != '' LIMIT 30")
for r in cur:
    print(f"  name={r[0][:70]}")
    print(f"  orig={r[1][:70]}")
    print()

# Are there records where name has non-roman but name_original is empty?
# Quick check: Arabic
cur = db.execute("SELECT COUNT(*) FROM churches WHERE name LIKE '%' || char(0x0600) || '%' AND (name_original IS NULL OR name_original = '')")
count_arabic_missing = cur.fetchone()[0]
print(f"Arabic names missing name_original: {count_arabic_missing}")

# CJK
cur = db.execute("SELECT COUNT(*) FROM churches WHERE name LIKE '%' || char(0x4E00) || '%' AND (name_original IS NULL OR name_original = '')")
count_cjk_missing = cur.fetchone()[0]
print(f"CJK names missing name_original: {count_cjk_missing}")

# Check if normalized_name contains transliterations
print("\n=== normalized_name on non-roman names ===")
cur = db.execute("""
    SELECT name, normalized_name FROM churches 
    WHERE (name_original IS NULL OR name_original = '')
    AND normalized_name IS NOT NULL AND normalized_name != ''
    LIMIT 10
""")
for r in cur:
    print(f"  name={r[0][:70]}")
    print(f"  norm={r[1][:70]}")
    print()

db.close()
