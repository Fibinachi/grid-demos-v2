import sqlite3, re, json
from pathlib import Path

conn = sqlite3.connect('E:/grid/wpa.db')
cur = conn.cursor()

# Show sample cleaned entries
print("=== Sample cleaned entries ===")
for row in cur.execute("SELECT church_name FROM wpa_churches WHERE LENGTH(church_name) BETWEEN 20 AND 80 LIMIT 30").fetchall():
    print(f"  {row[0]}")