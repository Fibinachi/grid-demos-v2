"""Verify ACT heritage geocoding status."""
import sqlite3
db = sqlite3.connect('E:/grid/churches.db')
cur = db.execute(
    "SELECT id, city, latitude, longitude, geocode_source "
    "FROM churches WHERE source='act_heritage_register' ORDER BY city"
)
rows = cur.fetchall()
null = [r for r in rows if r[2] is None]
print(f"Total: {len(rows)}, Missing lat/lon: {len(null)}")
for r in rows:
    status = "OK" if r[2] is not None else "MISSING"
    print(f"  [{status}] id={r[0]} {r[1]:12s} lat={r[2]} lon={r[3]} src={r[4]}")
db.close()
