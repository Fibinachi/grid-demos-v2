"""Log provenance for Phase 1 — school landmark_type fixes."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from gw_db import connect, Provenance

conn = connect()
with Provenance(conn, script_name="fix_schools_phase1.py", source="pss_schools",
                action="enriched", fields="landmark_type") as prov:
    prov.churches_updated = 1922
    prov.records_attempted = 1922
    prov.records_matched = 1922
print("Provenance logged.")
conn.close()
