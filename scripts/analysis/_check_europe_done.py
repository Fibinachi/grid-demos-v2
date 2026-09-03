"""Check if Europe scan completed by looking at DB/enrichment log."""
import sqlite3
conn = sqlite3.connect(r"E:\grid\churches.db")
c = conn.cursor()

# Check if provenance was logged
c.execute("SELECT id, churches_updated, notes FROM provenance_log WHERE script_name='scan_europe_jewish_deepseek'")
row = c.fetchone()
if row:
    print(f"Europe scan COMPLETED - provenance #{row[0]}: {row[1]} churches. {row[2]}")
else:
    print("Europe scan NOT completed - no provenance entry")

# Check enrichment log
c.execute("SELECT COUNT(*) FROM enrichment_change_log WHERE change_source='deepseek_europe_scan'")
n = c.fetchone()[0]
print(f"Enrichment log entries (deepseek_europe_scan): {n:,}")

# Count Europe entries
europe = [
    'AL','Albania','AD','Andorra','AT','Austria','BY','Belarus','BE','Belgium',
    'BA','Bosnia','BG','Bulgaria','HR','Croatia','CZ','Czech Republic',
    'DK','Denmark','EE','Estonia','FI','Finland','FR','France','DE','Germany',
    'GR','Greece','HU','Hungary','IS','Iceland','IE','Ireland','IT','Italy',
    'XK','Kosovo','LV','Latvia','LI','Liechtenstein','LT','Lithuania',
    'LU','Luxembourg','MT','Malta','MD','Moldova','MC','Monaco','ME','Montenegro',
    'NL','Netherlands','MK','North Macedonia','NO','Norway','PL','Poland',
    'PT','Portugal','RO','Romania','SM','San Marino','RS','Serbia',
    'SK','Slovakia','SI','Slovenia','ES','Spain','SE','Sweden','CH','Switzerland',
    'UA','Ukraine','GB','United Kingdom','VA','Vatican City',
    'GG','Guernsey','JE','Jersey','IM','Isle of Man','GI','Gibraltar',
    'England','Scotland','Wales','Northern Ireland'
]
ph = ','.join('?' for _ in europe)
c.execute(f"SELECT COUNT(*) FROM churches WHERE faith='Judaism' AND country IN ({ph})", europe)
print(f"Europe Judaism entries: {c.fetchone()[0]:,}")

c.execute(f"SELECT COALESCE(landmark_type,'NULL'), COUNT(*) FROM churches WHERE faith='Judaism' AND country IN ({ph}) GROUP BY landmark_type ORDER BY COUNT(*) DESC", europe)
print(f"\nBy type:")
for r in c.fetchall():
    marker = "  PROBLEM" if r[0] in ('church','chapel','cathedral','mosque','abbey','shrine','NULL','') else ""
    print(f"  {r[0]:25s} {r[1]:>5,}{marker}")

c.execute(f"SELECT COUNT(*) FROM churches WHERE faith='Judaism' AND country IN ({ph}) AND (landmark_type IS NULL OR landmark_type IN ('','church','chapel','cathedral','mosque','abbey','shrine'))", europe)
print(f"Problematic: {c.fetchone()[0]}")

# Check for chabad regression
c.execute(f"SELECT COUNT(*) FROM churches WHERE faith='Judaism' AND country IN ({ph}) AND landmark_type='chabad'", europe)
n = c.fetchone()[0]
print(f"\n'chabad' type (should be 0): {n}")

c.execute(f"SELECT COUNT(*) FROM churches WHERE faith='Judaism' AND country IN ({ph}) AND landmark_type='community center'", europe)
print(f"'community center' type (should be 0): {c.fetchone()[0]}")

if n:
    c.execute(f"UPDATE churches SET landmark_type='chabad_house' WHERE faith='Judaism' AND country IN ({ph}) AND landmark_type='chabad'", europe)
    print(f"Fixed chabad->chabad_house: {c.rowcount}")
    conn.commit()

conn.close()
