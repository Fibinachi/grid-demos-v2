"""Add capacity_estimate to church_building_sqft_us (building_sqft / 15).

Does NOT modify the churches table — data stays in the join table.
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from gw_db import connect
from datetime import datetime
import sqlite3

db = connect()
c = db.cursor()

print("=" * 60)
print("Add capacity_estimate to church_building_sqft_us")
print("=" * 60)

# Add column
try:
    c.execute("ALTER TABLE church_building_sqft_us ADD COLUMN capacity_estimate INTEGER")
    print("  Added capacity_estimate column")
except sqlite3.OperationalError:
    print("  capacity_estimate already exists")

# Compute: 15 sqft per seat (standard assembly occupancy)
c.execute("""
    UPDATE church_building_sqft_us 
    SET capacity_estimate = CAST(ROUND(building_area_sqft / 15.0) AS INTEGER)
    WHERE building_area_sqft IS NOT NULL AND building_area_sqft > 0
""")
db.commit()

# Stats
c.execute("""
    SELECT COUNT(*), ROUND(AVG(capacity_estimate),0), ROUND(AVG(building_area_sqft),0),
           MIN(capacity_estimate), MAX(capacity_estimate)
    FROM church_building_sqft_us WHERE capacity_estimate > 0
""")
total, avg_cap, avg_sqft, min_cap, max_cap = c.fetchone()
print(f"  {total:,} rows | Avg: {avg_cap:,.0f} seats ({avg_sqft:,.0f} sqft)")
print(f"  Range: {min_cap:,} – {max_cap:,} seats")

# Distribution
print()
print("SIZE TIERS:")
for label, lo, hi in [
    ('Micro (<100)', 0, 99),
    ('Small (100-299)', 100, 299),
    ('Medium (300-749)', 300, 749),
    ('Large (750-1,499)', 750, 1499),
    ('Mega (1,500-2,999)', 1500, 2999),
    ('Giga (3,000+)', 3000, 999999),
]:
    c.execute("""
        SELECT COUNT(*) FROM church_building_sqft_us 
        WHERE capacity_estimate > 0 AND capacity_estimate BETWEEN ? AND ?
    """, (lo, hi))
    cnt = c.fetchone()[0]
    pct = cnt / total * 100
    bar = '█' * int(pct / 2)
    print(f"  {label:25s} {cnt:>8,} ({pct:>5.1f}%) {bar}")

# Top 10
print()
print("TOP 10 BY CAPACITY:")
c.execute("""
    SELECT name, city, state, tradition, 
           ROUND(building_area_sqft,0) as sqft, capacity_estimate, parking_estimate_spots
    FROM church_building_sqft_us
    WHERE capacity_estimate > 0
    ORDER BY capacity_estimate DESC LIMIT 10
""")
for r in c.fetchall():
    print(f"  {(r[0] or '')[:40]:40s} {(r[1] or '')[:15]:15s} {r[2] or '':3s}  "
          f"{r[5]:>6,} seats | {r[4]:>9,.0f} sqft | {r[6] or 0:>5,} parking")

db.close()
print("\nDone — capacity_estimate added to church_building_sqft_us (join table only).")

# Provenance
db2 = sqlite3.connect(r'E:\grid\churches.db')
now = datetime.now().isoformat()
db2.execute("""
    INSERT INTO provenance_log (source, script_name, started_at, completed_at,
                                 churches_updated, fields_populated, records_attempted, status)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
""", ('overture_maps', 'add_capacity.py', now, now, total, 'capacity_estimate', total, 'completed'))
db2.commit()
db2.close()
