"""Check if imported records have real IDs."""
import sys
sys.path.insert(0, r'E:\grid')
from gw_db import connect

conn = connect(r'E:\grid\churches.db')

# Check ADAMS GEORGE WARDELL
rows = conn.execute("SELECT id, name, faith, boston_pid FROM churches WHERE name LIKE '%ADAMS GEORGE%'").fetchall()
for r in rows:
    print(f"  id={r[0]} type={type(r[0]).__name__}: {r[1][:60]} | pid={r[3]}")

# Check all records with source='boston_property_assessment' that have null id
nulls = conn.execute("SELECT COUNT(*) FROM churches WHERE source='boston_property_assessment' AND id IS NULL").fetchone()[0]
print(f"\nNull IDs: {nulls}")

# Sample some
samples = conn.execute("SELECT id, name, faith, boston_pid FROM churches WHERE source='boston_property_assessment' LIMIT 10").fetchall()
print("\nSamples:")
for s in samples:
    print(f"  id={s[0]} type={type(s[0]).__name__}: {s[1][:50]} | {s[2]} | pid={s[3]}")

conn.close()
