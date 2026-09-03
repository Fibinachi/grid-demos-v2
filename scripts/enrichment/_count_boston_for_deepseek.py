"""Count Boston records needing DeepSeek classification."""
import sys; sys.path.insert(0, r'E:\grid')
import os
from gw_db import connect

conn = connect(r'E:\grid\churches.db')

# Total Boston area churches
total = conn.execute("""
    SELECT COUNT(*) FROM churches 
    WHERE state='MA' AND UPPER(city) IN ('BOSTON','ALLSTON','BRIGHTON','CHARLESTOWN','DORCHESTER',
        'EAST BOSTON','HYDE PARK','JAMAICA PLAIN','MATTAPAN','READVILLE','ROSLINDALE',
        'ROXBURY','ROXBURY CROSSING','SOUTH BOSTON','WEST ROXBURY')
""").fetchone()[0]
print(f"Total Boston area churches: {total}")

# Records from boston_property_assessment source
prop = conn.execute("SELECT COUNT(*) FROM churches WHERE source='boston_property_assessment'").fetchone()[0]
print(f"boston_property_assessment: {prop}")

# Records from boston_nonpublic_schools
schools = conn.execute("SELECT COUNT(*) FROM churches WHERE source='boston_nonpublic_schools'").fetchone()[0]
print(f"boston_nonpublic_schools: {schools}")

# Faith breakdown for property assessment records
print("\nFaith breakdown (boston_property_assessment):")
faiths = conn.execute("SELECT faith, COUNT(*) FROM churches WHERE source='boston_property_assessment' GROUP BY faith ORDER BY COUNT(*) DESC").fetchall()
for f in faiths:
    print(f"  {f[0]}: {f[1]}")

# All Christian Science records in Boston area
cs = conn.execute("""
    SELECT id, name, faith, denomination, source
    FROM churches 
    WHERE state='MA' AND UPPER(city)='BOSTON' AND UPPER(name) LIKE '%CHRIST SCIENTIST%'
""").fetchall()
print(f"\nChristian Science in Boston: {len(cs)}")
for c in cs[:5]:
    print(f"  #{c[0]}: {c[1][:50]} | {c[2]} | {c[3]} | {c[4]}")

# Check if DEEPSEEK_API_KEY is set
key = os.environ.get('DEEPSEEK_API_KEY', '')
print(f"\nDEEPSEEK_API_KEY set: {'YES' if key else 'NO'} ({len(key)} chars)")

conn.close()
