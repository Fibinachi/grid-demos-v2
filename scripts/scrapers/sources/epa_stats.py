"""Check EPA merge stats in RDS"""
import mysql.connector
c = mysql.connector.connect(
    host="grantwizard.csjiu2wagplc.us-east-1.rds.amazonaws.com",
    user="grantwizard", password="F3y6bBoQZeYPMJir",
    database="grantwizard"
)
cur = c.cursor()
cur.execute("SELECT COUNT(*) FROM churches WHERE source='shepherds_stream'")
ss = cur.fetchone()[0]
cur.execute("SELECT COUNT(*) FROM churches WHERE source='shepherds_stream' AND ein IS NOT NULL AND ein != ''")
ein = cur.fetchone()[0]
cur.execute("SELECT COUNT(*) FROM churches WHERE source='shepherds_stream' AND latitude IS NOT NULL")
lat = cur.fetchone()[0]
print(f"Shepherds Stream in RDS: {ss}")
if ss:
    print(f"  With EIN (EPA match): {ein} ({ein/ss*100:.1f}%)")
print(f"  With lat/lon: {lat}")
cur.close()
c.close()
