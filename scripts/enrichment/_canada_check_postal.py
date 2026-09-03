#!/usr/bin/env python3
"""Check Canadian postal code coverage."""
import sqlite3

db = sqlite3.connect(r'E:\grid\churches.db')

cur = db.execute("SELECT zip, COUNT(*) FROM churches WHERE country=? AND zip IS NOT NULL AND zip!='' GROUP BY zip ORDER BY COUNT(*) DESC LIMIT 20", ('CA',))
print('Top 20 Canadian postal codes:')
for r in cur.fetchall():
    print(f'  {r[0]}: {r[1]}')

cur = db.execute("SELECT COUNT(*) FROM churches WHERE country=? AND zip IS NOT NULL AND zip!=''", ('CA',))
print(f'\nCanadian records WITH zip/postal code: {cur.fetchone()[0]}')

cur = db.execute("SELECT COUNT(*) FROM churches WHERE country=? AND (zip IS NULL OR zip='')", ('CA',))
print(f'Canadian records WITHOUT zip: {cur.fetchone()[0]}')

# Sample of CA zip values (first chars)
cur = db.execute("SELECT DISTINCT substr(zip,1,1) FROM churches WHERE country=? AND zip IS NOT NULL AND zip!='' ORDER BY 1", ('CA',))
prefixes = [r[0] for r in cur.fetchall()]
print(f'\nFirst-character prefixes found: {prefixes}')

# Length distribution
cur = db.execute("SELECT length(zip), COUNT(*) FROM churches WHERE country=? AND zip IS NOT NULL AND zip!='' GROUP BY length(zip) ORDER BY 1", ('CA',))
print(f'\nZip field length distribution:')
for r in cur.fetchall():
    print(f'  {r[0]} chars: {r[1]} records')

# Check if overture_canada_new.csv exists
import os
csv_path = r'E:\grid\data\overture_canada_new.csv'
if os.path.exists(csv_path):
    import csv
    with open(csv_path, 'r', encoding='utf-8') as f:
        reader = csv.reader(f)
        header = next(reader)
        print(f'\noverture_canada_new.csv columns: {header}')
        # Count lines
        f.seek(0)
        line_count = sum(1 for _ in f)
        print(f'  Lines: {line_count}')

db.close()
