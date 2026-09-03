"""Null out placeholder footprint values (500K sqft rows)."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from gw_db import connect, log_change

db = connect()
cur = db.cursor()

print("Cleaning placeholder footprint rows (500,000 sqft)...")

cur.execute("""
    UPDATE church_building_sqft_us
    SET building_area_sqft = NULL,
        capacity_estimate = NULL,
        parking_estimate_spots = NULL
    WHERE building_area_sqft = 500000
""")
affected = cur.rowcount
db.commit()

print(f"  NULLed {affected} rows (sqft, capacity, parking)")

# Verify
cur.execute("SELECT COUNT(*) FROM church_building_sqft_us WHERE building_area_sqft = 500000")
print(f"  Remaining 500K rows: {cur.fetchone()[0]}")
cur.execute("SELECT COUNT(*) FROM church_building_sqft_us WHERE building_area_sqft IS NULL AND capacity_estimate IS NULL")
print(f"  Total NULLed rows: {cur.fetchone()[0]}")

db.close()
print("Done.")
