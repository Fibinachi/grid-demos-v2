"""Find a known MS church in the database to use as ground truth for CRS."""
import sqlite3

db = sqlite3.connect('E:\\grid\\churches.db')
cur = db.cursor()

# 1. Christ the King Catholic - distinctive name
print("=== Christ the King Catholic ===")
cur.execute("SELECT id, name, city, state, latitude, longitude, zip FROM churches WHERE name LIKE '%Christ the King%' AND state='MS'")
for r in cur.fetchall():
    print(f"  id={r[0]}, {r[1]}, {r[2]}, {r[3]}, lat={r[4]}, lon={r[5]}, zip={r[6]}")

# 2. Shiloh Missionary Baptist
print("\n=== Shiloh Missionary Baptist ===")
cur.execute("SELECT id, name, city, state, latitude, longitude, zip FROM churches WHERE name LIKE '%Shiloh Missionary Baptist%' AND state='MS'")
for r in cur.fetchall():
    print(f"  id={r[0]}, {r[1]}, {r[2]}, {r[3]}, lat={r[4]}, lon={r[5]}, zip={r[6]}")

# 3. LDS on Goodman
print("\n=== LDS / Goodman ===")
cur.execute("SELECT id, name, city, state, latitude, longitude, zip FROM churches WHERE name LIKE '%Latter%Saint%' AND zip LIKE '386%'")
for r in cur.fetchall():
    print(f"  id={r[0]}, {r[1]}, {r[2]}, {r[3]}, lat={r[4]}, lon={r[5]}, zip={r[6]}")

# 4. Any church with 38671 ZIP
print("\n=== Any church in 38671 (first 10) ===")
cur.execute("SELECT id, name, city, state, latitude, longitude, zip FROM churches WHERE zip='38671' LIMIT 10")
for r in cur.fetchall():
    print(f"  id={r[0]}, {r[1][:50]}, {r[2]}, {r[3]}, lat={r[4]}, lon={r[5]}, zip={r[6]}")

# 5. Broad search: any Baptist church in Southaven
print("\n=== Baptist in Southaven ===")
cur.execute("SELECT id, name, city, state, latitude, longitude, zip FROM churches WHERE name LIKE '%Baptist%' AND city='Southaven' AND state='MS' LIMIT 5")
for r in cur.fetchall():
    print(f"  id={r[0]}, {r[1][:50]}, {r[2]}, {r[3]}, lat={r[4]}, lon={r[5]}, zip={r[6]}")

# 6. Try by address match - CHURCH RD
print("\n=== By address pattern ===")
cur.execute("SELECT id, name, city, state, latitude, longitude, address FROM churches WHERE address LIKE '%Church Rd%' AND city IN ('Southaven','Hernando') LIMIT 5")
for r in cur.fetchall():
    print(f"  id={r[0]}, {r[1][:50]}, {r[2]}, {r[3]}, lat={r[4]}, lon={r[5]}, addr={r[6]}")

db.close()
