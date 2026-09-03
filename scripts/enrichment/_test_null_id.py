"""Test if id is really NULL in the database."""
import sys; sys.path.insert(0, r'E:\grid')
import sqlite3
from gw_db import connect

# Test 1: Direct sqlite3 query (bypass gw_db wrapper)
conn_raw = sqlite3.connect(r'E:\grid\churches.db')
rows = conn_raw.execute("SELECT rowid, id, name, boston_pid FROM churches WHERE source='boston_property_assessment' LIMIT 5").fetchall()
print("Direct sqlite3:")
for r in rows:
    print(f"  rowid={r[0]} id={r[1]} ({type(r[1]).__name__}) name={r[2][:40]} pid={r[3]}")

# Test 2: Through gw_db
conn_gw = connect(r'E:\grid\churches.db')
rows2 = conn_gw.execute("SELECT rowid, id, name, boston_pid FROM churches WHERE source='boston_property_assessment' LIMIT 5").fetchall()
print("\nThrough gw_db:")
for r in rows2:
    print(f"  rowid={r[0]} id={r[1]} ({type(r[1]).__name__}) name={r[2][:40]} pid={r[3]}")

# Test 3: Count with id IS NULL
null_count = conn_raw.execute("SELECT COUNT(*) FROM churches WHERE id IS NULL").fetchone()[0]
print(f"\nNULL ids (raw): {null_count}")

# Test 4: Count with id IS NULL through gw_db
null_count2 = conn_gw.execute("SELECT COUNT(*) FROM churches WHERE id IS NULL").fetchone()[0]
print(f"NULL ids (gw_db): {null_count2}")

# Test 5: Check the row_factory
print(f"\nRow factory (raw): {conn_raw.row_factory}")
print(f"Row factory (gw_db): {conn_gw.row_factory}")
type(conn_gw).row_factory

conn_raw.close()
conn_gw.close()
