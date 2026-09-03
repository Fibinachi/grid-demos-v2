"""Check actual schema for id column."""
import sys; sys.path.insert(0, r'E:\grid')
import sqlite3
conn = sqlite3.connect(r'E:\grid\churches.db')

# Get full CREATE TABLE
schema = conn.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='churches'").fetchone()
print(schema[0])

# Check pragma
print("\n--- PRAGMA table_info ---")
for c in conn.execute("PRAGMA table_info(churches)").fetchall():
    print(f"  {c}")
