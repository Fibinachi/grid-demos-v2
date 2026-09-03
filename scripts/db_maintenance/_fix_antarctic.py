"""Fix sign-flipped coordinates below 60S — flip latitude to positive."""
import sqlite3
from gw_db import connect, Provenance

# Only AQ (Antarctica) and GS (South Georgia) legitimately extend below 60S
LEGIT_POLAR = {'AQ', 'GS'}

conn = connect()
c = conn.cursor()

c.execute("""SELECT rowid, name, country, faith, latitude, longitude, source
FROM churches WHERE latitude < -60 ORDER BY latitude""")
bogus = c.fetchall()

print(f"Found {len(bogus)} entries below 60S\n")

fixes = []
for row in bogus:
    rid, name, country, faith, lat, lon, source = row
    if country in LEGIT_POLAR:
        print(f"  KEEP  {rid:>9d} {str(country or '??'):4s} {str(name or '')[:40]:40s} ({lat:.3f}, {lon:.3f})")
        continue
    new_lat = abs(lat)
    fixes.append((rid, lat, new_lat))
    print(f"  FIX   {rid:>9d} {str(country or '??'):4s} {str(name or '')[:40]:40s} {lat:.3f} -> {new_lat:.3f}")

print(f"\n{len(fixes)} fixes, {len(bogus)-len(fixes)} kept")

with Provenance(conn, "fix_antarctic_coords.py", source="coordinate_fix",
                  fields="latitude"):
    c2 = conn.cursor()
    for rid, old_lat, new_lat in fixes:
        c2.execute("UPDATE churches SET latitude=? WHERE rowid=?", (new_lat, rid))

conn.commit()
print(f"Done — {len(fixes)} entries flipped to positive latitude.")
conn.close()
