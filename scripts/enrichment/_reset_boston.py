"""Reset Boston enrichment columns for re-run."""
import sys
sys.path.insert(0, r'E:\grid')
from gw_db import connect

conn = connect(r'E:\grid\churches.db')
result = conn.execute("UPDATE churches SET boston_pid = NULL, boston_property_json = NULL WHERE boston_pid IS NOT NULL OR boston_property_json IS NOT NULL")
print(f"Reset {result.rowcount} rows")
conn.commit()
