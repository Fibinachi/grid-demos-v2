"""Check rowids and fix NULL ID issue."""
import sys; sys.path.insert(0, r'E:\grid')
from gw_db import connect

conn = connect(r'E:\grid\churches.db')

# Check records with source='boston_property_assessment'
rows = conn.execute("SELECT rowid, id, boston_pid, name FROM churches WHERE source='boston_property_assessment' LIMIT 10").fetchall()
print("Rows from property assessment:")
for r in rows:
    print(f"  rowid={r[0]} id={r[1]} pid={r[2]} name={r[3][:40]}")

# Check all
total = conn.execute("SELECT COUNT(*) FROM churches WHERE source='boston_property_assessment'").fetchone()[0]
print(f"\nTotal with source='boston_property_assessment': {total}")

# Try with last_insert_rowid()
conn.execute("INSERT INTO churches (name, faith) VALUES ('test_rowid', 'TEST')")
rid = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
print(f"\nTest insert rowid: {rid}")
conn.execute("DELETE FROM churches WHERE rowid = ?", (rid,))
conn.commit()

# Check min/max rowids for property assessment records
result = conn.execute("SELECT MIN(rowid), MAX(rowid), COUNT(*) FROM churches WHERE source='boston_property_assessment'").fetchone()
print(f"\nProperty assessment: min_rowid={result[0]} max_rowid={result[1]} count={result[2]}")

# Are they really missing IDs?
result2 = conn.execute("SELECT COUNT(*) FROM churches WHERE source='boston_property_assessment' AND id IS NULL").fetchone()
print(f"With NULL id: {result2[0]}")

result3 = conn.execute("SELECT COUNT(*) FROM churches WHERE source='boston_property_assessment' AND id IS NOT NULL").fetchone()
print(f"With non-NULL id: {result3[0]}")

conn.close()
