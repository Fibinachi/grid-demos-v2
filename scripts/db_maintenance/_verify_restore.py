"""Verify restored corp records."""
import sqlite3

db = sqlite3.connect(r'E:\grid\churches.db')

print("=== LDS President ===")
cur = db.execute("SELECT id, name, city, state, country, latitude, longitude FROM churches WHERE name LIKE '%CORPORATION OF THE PRESIDENT%'")
for r in cur.fetchall():
    print(f"  id={r[0]} | {r[5]:.4f}, {r[6]:.4f} | {r[2]}, {r[3]} {r[4]}")

print("\n=== LDS Presiding Bishop ===")
cur = db.execute("SELECT id, name, city, state, country, latitude, longitude FROM churches WHERE name LIKE '%CORPORATION OF THE PRESIDING BISHOP%'")
for r in cur.fetchall():
    print(f"  id={r[0]} | {r[1][:60]} | {r[2]}, {r[3]} {r[4]} | {r[5]:.4f}, {r[6]:.4f}")

print("\n=== RC/Episcopal corps with coords ===")
cur = db.execute("SELECT id, name, city, state, country, latitude, longitude FROM churches WHERE (name LIKE '%EPISCOPAL CORPORATION%' OR name LIKE '%CATHOLIC EPISCOPAL%') AND latitude IS NOT NULL AND latitude != 0")
for r in cur.fetchall():
    print(f"  id={r[0]} | {r[1][:60]} | {r[2]}, {r[3]} {r[4]} | {r[5]:.4f}, {r[6]:.4f}")

print("\n=== Total corporation records in DB ===")
cur = db.execute("SELECT COUNT(*) FROM churches WHERE name LIKE '%CORPORATION%'")
print(f"  {cur.fetchone()[0]}")

db.close()
