"""Look up known churches from MS CSV in the database to get ground truth coordinates."""
import sqlite3
import csv

conn = sqlite3.connect('churches.db')

with open('Churches_4106776180121190077.csv', encoding='utf-8-sig') as f:
    csv_rows = list(csv.DictReader(f))

# Distinctive churches to search
targets = [
    "SHILOH MISSIONARY BAPTIST CHURCH",
    "AVERY CHAPEL AME CHURCH", 
    "BOULEVARD BAPTIST CHURCH",
    "SOUTHAVEN COMMUNITY CHURCH",
    "GRACE ACRES BAPTIST CHURCH",
    "NEW DAY FELLOWSHIP CHURCH",
    "DESOTO WOODS BAPTIST CHURCH",
    "MIRACLE TEMPLE MINISTRIES",
]

for name in targets:
    cur = conn.execute("""
        SELECT id, name, latitude, longitude, city, state, source
        FROM churches
        WHERE name LIKE ? AND state = 'MS'
    """, (f'%{name}%',))
    rows = cur.fetchall()
    if rows:
        for r in rows:
            print(f"✓ {name}: id={r[0]}, lat={r[2]}, lon={r[3]}, city={r[4]}")
    else:
        print(f"✗ {name}: NOT FOUND in DB")

conn.close()
