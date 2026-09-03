"""Quick check of current Europe state and move to Israel + BQ."""
import sqlite3
conn = sqlite3.connect(r"E:\grid\churches.db")
c = conn.cursor()

europe = ['AL','Albania','AD','Andorra','AT','Austria','BY','Belarus','BE','Belgium',
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
    'England','Scotland','Wales','Northern Ireland']
ph = ','.join('?' for _ in europe)

# Current Europe state
c.execute(f"SELECT COUNT(*) FROM churches WHERE faith='Judaism' AND country IN ({ph})", europe)
eu = c.fetchone()[0]
print(f"Europe Judaism: {eu:,}")

c.execute(f"SELECT COUNT(*) FROM churches WHERE faith='Judaism' AND country IN ({ph}) AND (landmark_type IS NULL OR landmark_type IN ('','church','chapel','cathedral','mosque','abbey','shrine'))", europe)
print(f"Problematic: {c.fetchone()[0]}")

c.execute(f"SELECT COALESCE(landmark_type,'NULL'), COUNT(*) FROM churches WHERE faith='Judaism' AND country IN ({ph}) GROUP BY landmark_type ORDER BY COUNT(*) DESC", europe)
for r in c.fetchall():
    print(f"  {r[0]:25s} {r[1]:>5,}")

# Check chabad regression
c.execute(f"SELECT COUNT(*) FROM churches WHERE faith='Judaism' AND country IN ({ph}) AND landmark_type='chabad'", europe)
print(f"\n'chabad' type: {c.fetchone()[0]}")

c.execute(f"SELECT COUNT(*) FROM churches WHERE faith='Judaism' AND country IN ({ph}) AND landmark_type='community center'", europe)
print(f"'community center' type: {c.fetchone()[0]}")

# Total worldwide
c.execute("SELECT COUNT(*) FROM churches WHERE faith='Judaism'")
total = c.fetchone()[0]
c.execute("SELECT COUNT(*) FROM churches WHERE faith='Judaism' AND country IN ('IL','Israel')")
il = c.fetchone()[0]
print(f"\nWorldwide: {total:,} (Israel: {il:,}, ex-Israel: {total-il:,})")

conn.close()
