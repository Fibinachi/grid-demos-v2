"""Remove obvious secular businesses. Keeps churches, schools, Inc. orgs."""
import sqlite3, datetime

DB = 'churches.db'
conn = sqlite3.connect(DB, timeout=30)
c = conn.cursor()

religious = [
    "%church%","%chapel%","%ministr%","%fellowship%","%worship%",
    "%temple%","%mosque%","%synagogue%","%parish%","%diocese%",
    "%cathedral%","%basilica%","%monastery%","%convent%","%abbey%",
    "%priory%","%seminary%","%presbytery%","%rectory%",
    "%iglesia%","%eglise%","%kirche%",
    "%catholic%","%orthodox%","%baptist%","%methodist%","%lutheran%",
    "%presbyterian%","%episcopal%","%anglican%","%pentecostal%",
    "%adventist%","%nazarene%","%mennonite%","%evangelical%",
    "%gospel%","%jesus%","%christ%","%bible%",
    "%saint%","%holy%","%blessed%","%prayer%",
    "%school%","%academy%","%college%","%university%",
    "%cemetery%","%burial%","%funeral%",
]
safe = " AND ".join([f"LOWER(name) NOT LIKE '{s}'" for s in religious])

targets = [
    ("Coffee", "LOWER(name) LIKE '%coffee%'"),
    ("Restaurant/Bakery", "LOWER(name) LIKE '%restaurant%' OR LOWER(name) LIKE '%bakery%' OR LOWER(name) LIKE '%diner%' OR LOWER(name) LIKE '%pizza%' OR LOWER(name) LIKE '%grill%'"),
    ("Brewery/Bar", "LOWER(name) LIKE '%brew%' OR LOWER(name) LIKE '%bar%' OR LOWER(name) LIKE '%pub%' OR LOWER(name) LIKE '%tavern%'"),
    ("Hotel/Motel", "LOWER(name) LIKE '%hotel%' OR LOWER(name) LIKE '%motel%' OR LOWER(name) LIKE '% inn%' OR LOWER(name) LIKE '%lodge%' OR LOWER(name) LIKE '%resort%'"),
    ("Retail", "LOWER(name) LIKE '%store%' OR LOWER(name) LIKE '% shop%' OR LOWER(name) LIKE '%market%' OR LOWER(name) LIKE '%mart%'"),
    ("Salon/Spa", "LOWER(name) LIKE '%salon%' OR LOWER(name) LIKE '%spa%' OR LOWER(name) LIKE '%barber%' OR LOWER(name) LIKE '%nails%'"),
    ("Auto", "LOWER(name) LIKE '%auto%' OR LOWER(name) LIKE '%tire%' OR LOWER(name) LIKE '%car wash%' OR LOWER(name) LIKE '%dealership%' OR LOWER(name) LIKE '%garage%'"),
    ("Gym", "LOWER(name) LIKE '%gym%' OR LOWER(name) LIKE '%fitness%' OR LOWER(name) LIKE '%crossfit%'"),
    ("Realty", "LOWER(name) LIKE '%realty%' OR LOWER(name) LIKE '%real estate%'"),
    ("Insurance", "LOWER(name) LIKE '%insurance%'"),
    ("Dental/Medical", "LOWER(name) LIKE '%dental%' OR LOWER(name) LIKE '%pharmacy%' OR LOWER(name) LIKE '%clinic%'"),
    ("Construction", "LOWER(name) LIKE '%construction%' OR LOWER(name) LIKE '%contractor%' OR LOWER(name) LIKE '%plumbing%' OR LOWER(name) LIKE '%electric%' OR LOWER(name) LIKE '%roofing%' OR LOWER(name) LIKE '%hvac%' OR LOWER(name) LIKE '%landscaping%'"),
    ("Cleaning", "LOWER(name) LIKE '%cleaning%' OR LOWER(name) LIKE '%janitorial%' OR LOWER(name) LIKE '%maid%'"),
    ("Trucking/Transport", "LOWER(name) LIKE '%trucking%' OR LOWER(name) LIKE '%logistics%'"),
    ("Printing", "LOWER(name) LIKE '%printing%'"),
]

total = 0
for label, where_clause in targets:
    sql = "DELETE FROM churches WHERE (faith IS NULL OR faith='') AND (" + where_clause + ") AND (" + safe + ")"
    try:
        c.execute(sql)
        if c.rowcount > 0:
            print(f"  {label}: {c.rowcount}")
            total += c.rowcount
    except Exception as e:
        print(f"  ERROR in {label}: {e}")
        print(f"  SQL (first 200): {sql[:200]}")

conn.commit()
print(f"\nRemoved: {total:,}")
c.execute("SELECT COUNT(*) FROM churches WHERE faith IS NULL OR faith=''")
print(f"Remaining NULL-faith: {c.fetchone()[0]:,}")

c.execute("""INSERT INTO provenance_log (source, script_name, started_at, completed_at,
    churches_updated, churches_inserted, fields_populated, status, notes)
    VALUES ('manual','_clean_biz.py',?,?,0,0,'deleted','completed',?)""",
    (datetime.datetime.now().isoformat(), datetime.datetime.now().isoformat(),
     f'Removed {total} secular businesses. Kept Inc/Corp/LLC and church schools.'))
conn.commit()
conn.close()
