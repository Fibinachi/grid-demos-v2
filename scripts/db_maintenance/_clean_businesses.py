"""Remove secular businesses. Keeps church schools, ministries, etc."""
import sqlite3, datetime

DB = 'churches.db'
conn = sqlite3.connect(DB, timeout=30)
c = conn.cursor()

# Religious keywords — records with ANY of these are SAFE (keep)
religious_safe = [
    "%church%", "%ministr%", "%fellowship%", "%worship%", "%temple%",
    "%mosque%", "%synagogue%", "%chapel%", "%parish%", "%diocese%",
    "%cathedral%", "%basilica%", "%monastery%", "%convent%", "%abbey%",
    "%priory%", "%seminary%", "%presbytery%", "%rectory%",
    "%iglesia%", "%eglise%", "%kirche%",
    "%catholic%", "%orthodox%", "%baptist%", "%methodist%", "%lutheran%",
    "%presbyterian%", "%episcopal%", "%anglican%", "%pentecostal%",
    "%adventist%", "%nazarene%", "%mennonite%", "%evangelical%",
    "%gospel%", "%jesus%", "%christ%", "%bible%", "%scripture%",
    "%saint%", "%holy%", "%blessed%", "%prayer%",
    "%school%", "%academy%", "%college%", "%university%",
    "%cemetery%", "%burial%",
]

safe_clause = " AND ".join([f"LOWER(name) NOT LIKE '{s}'" for s in religious_safe])

business_keywords = [
    "%coffee%", "%brew%co%", "%restaurant%", "%bakery%", "%diner%",
    "%cafe%", "%pizza%", "%grill%",
    "%hotel%", "%motel%", "% inn%", "%lodge%", "%resort%",
    "%store%", "% shop%", "%market%", "%mart%",
    "%salon%", "%spa%", "%barber%", "%nails%",
    "%realty%", "%real estate%", "%insurance%",
    "%law %", "%attorney%", "%legal%",
    "%dental%", "%pharmacy%", "%doctor%", "%clinic%",
    "%construction%", "%contractor%", "%plumbing%", "%electric%",
    "%roofing%", "%hvac%", "%landscaping%",
    "%cleaning%", "%janitorial%", "%maid%",
    "%trucking%", "%transport%", "%logistics%",
    "%software%", "%consulting%", "%marketing%", "%advertising%",
    "%printing%", "%publishing%",
    "%funeral%", "%mortuary%", "%cremation%",
    "%gym%", "%fitness%", "%crossfit%",
    "%auto%", "%tire%", "%car wash%", "%dealership%",
    "%garage%",
]

total = 0
for biz_pattern in business_keywords:
    c.execute(f"""DELETE FROM churches 
        WHERE (faith IS NULL OR faith='') 
        AND LOWER(name) LIKE '{biz_pattern}'
        AND ({safe_clause})""")
    if c.rowcount > 0:
        print(f"  {biz_pattern}: {c.rowcount}")
        total += c.rowcount

conn.commit()
print(f"\nRemoved: {total:,}")
c.execute("SELECT COUNT(*) FROM churches WHERE faith IS NULL OR faith=''")
print(f"Remaining NULL-faith: {c.fetchone()[0]:,}")

c.execute("""INSERT INTO provenance_log (source, script_name, started_at, completed_at,
    churches_updated, churches_inserted, fields_populated, status, notes)
    VALUES ('manual','_clean_businesses.py',?,?,0,0,'deleted','completed',?)""",
    (datetime.datetime.now().isoformat(), datetime.datetime.now().isoformat(),
     f'Removed {total} secular business records (kept church schools)'))
conn.commit()
conn.close()
