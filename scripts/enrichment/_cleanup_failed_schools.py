"""Clean up failed school imports (null IDs from previous run)."""
import sys; sys.path.insert(0, r'E:\grid')
from gw_db import connect
conn = connect(r'E:\grid\churches.db')
deleted = conn.execute("DELETE FROM churches WHERE id IS NULL AND source='boston_nonpublic_schools'").rowcount
print(f"Deleted {deleted} failed records")
conn.commit()
conn.close()
