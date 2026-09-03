"""Fix remaining issues from Europe scan and log provenance."""
import sqlite3
from datetime import datetime, timezone
conn = sqlite3.connect(r"E:\grid\churches.db")
c = conn.cursor()

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

# 1. Fix community center normalization
c.execute(f"SELECT COUNT(*) FROM churches WHERE faith='Judaism' AND country IN ({ph}) AND landmark_type='community center'", europe)
n = c.fetchone()[0]
if n:
    c.execute(f"UPDATE churches SET landmark_type='community_center' WHERE faith='Judaism' AND country IN ({ph}) AND landmark_type='community center'", europe)
    print(f"Fixed 'community center'->'community_center': {c.rowcount}")
    conn.commit()

# 2. Fix the 3 problematic entries
c.execute(f"SELECT id, name, city, country, landmark_type, tradition FROM churches WHERE faith='Judaism' AND country IN ({ph}) AND (landmark_type IS NULL OR landmark_type IN ('','church','chapel','cathedral','mosque','abbey','shrine'))", europe)
for r in c.fetchall():
    new_type = 'synagogue'
    print(f"Fixing #{r[0]}: {r[1]}, {r[2]}, {r[3]} type={r[4]} -> {new_type}")
    c.execute("UPDATE churches SET landmark_type=? WHERE id=?", (new_type, r[0]))
    c.execute("INSERT INTO enrichment_change_log (church_id, field_name, old_value, new_value, change_source) VALUES (?, 'landmark_type', ?, ?, 'deepseek_europe_cleanup')",
              (r[0], r[4], new_type))
    conn.commit()

# 3. Log provenance for the scan
STARTED_AT = "2026-06-26T22:00:00+00:00"  # approximate
COMPLETED_AT = datetime.now(timezone.utc).isoformat()

c.execute("SELECT COUNT(*) FROM enrichment_change_log WHERE change_source='deepseek_europe_scan'")
changes = c.fetchone()[0]
c.execute("SELECT COUNT(DISTINCT church_id) FROM enrichment_change_log WHERE change_source='deepseek_europe_scan'")
churches = c.fetchone()[0]
c.execute("SELECT COUNT(*) FROM enrichment_change_log WHERE change_source='deepseek_europe_scan' AND field_name='faith'")
faith_moved = c.fetchone()[0]

c.execute("INSERT INTO provenance_log (source, script_name, started_at, completed_at, churches_updated, fields_populated, status, notes) VALUES (?, ?, ?, ?, ?, ?, 'completed', ?)",
          ('deepseek', 'scan_europe_jewish_deepseek', STARTED_AT, COMPLETED_AT,
           churches, 'faith,tradition,landmark_type',
           f'DeepSeek Europe Judaism scan: {faith_moved} moved out, {changes} total changes.'))
conn.commit()
print(f"\nProvenance logged: {changes} changes across {churches} churches ({faith_moved} faith moves)")

# 4. Final verification
c.execute(f"SELECT COUNT(*) FROM churches WHERE faith='Judaism' AND country IN ({ph})", europe)
print(f"\nTotal Europe Judaism: {c.fetchone()[0]:,}")

c.execute(f"SELECT COALESCE(landmark_type,'NULL'), COUNT(*) FROM churches WHERE faith='Judaism' AND country IN ({ph}) GROUP BY landmark_type ORDER BY COUNT(*) DESC", europe)
for r in c.fetchall():
    marker = "  PROBLEM" if r[0] in ('church','chapel','cathedral','mosque','abbey','shrine','NULL','') else ""
    print(f"  {r[0]:25s} {r[1]:>5,}{marker}")

c.execute(f"SELECT COUNT(*) FROM churches WHERE faith='Judaism' AND country IN ({ph}) AND (landmark_type IS NULL OR landmark_type IN ('','church','chapel','cathedral','mosque','abbey','shrine'))", europe)
print(f"Problematic: {c.fetchone()[0]}")

c.execute(f"SELECT landmark_type FROM churches WHERE faith='Judaism' AND country IN ({ph}) AND landmark_type LIKE '% %' GROUP BY landmark_type")
odd = c.fetchall()
if odd:
    print(f"\nOdd types with spaces:")
    for r in odd:
        print(f"  '{r[0]}'")

conn.close()
print("Done!")
