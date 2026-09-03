"""Fix country codes on restored LDS Presiding Bishop records."""
import sqlite3

db = sqlite3.connect(r'E:\grid\churches.db')

# Fix US-based ones that got assigned CA
fixes = {
    357265: ('Mesa', 'AZ', 'US'),
    357559: ('Sacramento', 'CA', 'US'),
    358676: ('Apple Valley', 'MN', 'US'),
    359615: ('Round Rock', 'TX', 'US'),
    786295: ('Round Rock', 'TX', 'US'),
    # 703487 (Strathcona County, AB) is correctly CA
}

for rid, (city, state, country) in fixes.items():
    cur = db.execute("UPDATE churches SET country = ?, state = ? WHERE id = ?", (country, state, rid))
    print(f"  id={rid}: → {city}, {state} {country} ({cur.rowcount} row)")

db.commit()

# Verify
print("\n=== Verification ===")
cur = db.execute("SELECT id, city, state, country FROM churches WHERE id IN (357265,357559,358676,359615,703487,786295) ORDER BY id")
for r in cur.fetchall():
    print(f"  id={r[0]} | {r[1]}, {r[2]} {r[3]}")

db.close()
