"""Analyze Jewish name patterns for classifier building."""
import sqlite3
c = sqlite3.connect(r'E:\grid\churches.db')

print("=== FAITH_TRADITION distribution ===")
for r in c.execute("SELECT faith_tradition, COUNT(*) FROM churches WHERE faith='Jewish' GROUP BY faith_tradition ORDER BY COUNT(*) DESC"):
    print(f"  {str(r[0]):20s} {r[1]:>8}")

print("\n=== DENOMINATION distribution ===")
for r in c.execute("SELECT denomination, COUNT(*) FROM churches WHERE faith='Jewish' GROUP BY denomination ORDER BY COUNT(*) DESC LIMIT 30"):
    print(f"  {str(r[0]):40s} {r[1]:>8}")

print("\n=== LANDMARK_TYPE distribution ===")
for r in c.execute("SELECT landmark_type, COUNT(*) FROM churches WHERE faith='Jewish' GROUP BY landmark_type ORDER BY COUNT(*) DESC"):
    print(f"  {str(r[0]):20s} {r[1]:>8}")

print("\n=== Chabad entries ===")
for r in c.execute("SELECT rowid, name, source, faith_tradition, country FROM churches WHERE faith='Jewish' AND (denomination LIKE '%Chabad%' OR name LIKE '%chabad%' OR name LIKE '%habad%') ORDER BY country LIMIT 30"):
    print(f"  rowid={r[0]:>8}  trad={str(r[3] or '-'):15s}  cnt={r[4]:2s}  src={str(r[2])[:25]:25s}  {r[1][:60]:60s}")

print("\n=== Hasidic entries ===")
for r in c.execute("SELECT rowid, name, source, faith_tradition, country FROM churches WHERE faith='Jewish' AND (name LIKE '%hasidic%' OR name LIKE '%hassidic%' OR name LIKE '%hasid%' OR name LIKE '%satmar%' OR name LIKE '%lubavitch%' OR name LIKE '%belz%' OR name LIKE '%gur%' OR name LIKE '%breslov%' OR name LIKE '%vizhnitz%' OR name LIKE '%munkacs%' OR name LIKE '%stolin%' OR name LIKE '%skver%' OR name LIKE '%bobov%' OR name LIKE '%monsey%' OR name LIKE '%williamsburg%') ORDER BY country LIMIT 20"):
    print(f"  rowid={r[0]:>8}  trad={str(r[3] or '-'):15s}  cnt={r[4]:2s}  src={str(r[2])[:25]:25s}  {r[1][:60]:60s}")

print("\n=== Sephardi/Mizrahi entries ===")
for r in c.execute("SELECT rowid, name, source, faith_tradition, country FROM churches WHERE faith='Jewish' AND (name LIKE '%sephard%' OR name LIKE '%mizrah%' OR name LIKE '%spanish%' OR name LIKE '%portuguese%' OR name LIKE '%marrano%' OR name LIKE '%converso%' OR name LIKE '%aleppo%' OR name LIKE '%baghdadi%' OR name LIKE '%bucharian%' OR name LIKE '%yemenite%' OR name LIKE '%ethiopian%' OR name LIKE '%beta israel%') ORDER BY country LIMIT 30"):
    print(f"  rowid={r[0]:>8}  trad={str(r[3] or '-'):15s}  cnt={r[4]:2s}  src={str(r[2])[:25]:25s}  {r[1][:60]:60s}")

print("\n=== Reform/Conservative entries ===")
for r in c.execute("SELECT rowid, name, source, faith_tradition, country FROM churches WHERE faith='Jewish' AND (name LIKE '%reform%' OR name LIKE '%conservative%' OR name LIKE '%liberal%' OR name LIKE '%progressive%' OR name LIKE '%temple%' OR name LIKE '%reconstructionist%' OR name LIKE '%humanistic%' OR name LIKE '%emmanuel%' OR name LIKE '%b\'nai%' OR name LIKE '%temple%') AND country='US' AND source='holy_sites_import' LIMIT 30"):
    print(f"  rowid={r[0]:>8}  trad={str(r[3] or '-'):15s}  cnt={r[4]:2s}  src={str(r[2])[:25]:25s}  {r[1][:60]:60s}")

print("\n=== Yeshiva entries ===")
for r in c.execute("SELECT rowid, name, source, faith_tradition, country FROM churches WHERE faith='Jewish' AND (name LIKE '%yeshiva%' OR name LIKE '%yeshivah%' OR name LIKE '%kollel%' OR name LIKE '%seminary%' OR name LIKE '%mesivta%' OR name LIKE '%beis medrash%' OR name LIKE '%beth midrash%' OR name LIKE '%talmud%') ORDER BY country LIMIT 20"):
    print(f"  rowid={r[0]:>8}  trad={str(r[3] or '-'):15s}  cnt={r[4]:2s}  src={str(r[2])[:25]:25s}  {r[1][:60]:60s}")

print("\n=== Christian-faith entries still tagged faith=Jewish ===")
for r in c.execute("SELECT rowid, name, source, faith_tradition, denomination, country FROM churches WHERE faith='Jewish' AND faith_tradition IN ('Christian','Baptist','Lutheran','Catholic','Pentecostal','Methodist','Anglican','Presbyterian') ORDER BY faith_tradition, country LIMIT 40"):
    print(f"  rowid={r[0]:>8}  trad={str(r[3] or '-'):15s}  denom={str(r[4] or '-'):30s}  cnt={r[5]:2s}  src={str(r[2])[:20]:20s}  {r[1][:55]:55s}")

print("\n=== Orthodox entries ===")
for r in c.execute("SELECT rowid, name, source, faith_tradition, country FROM churches WHERE faith='Jewish' AND (name LIKE '%orthodox%' OR name LIKE '%young israel%' OR name LIKE '%ou \' OR name LIKE '%union of orthodox%') ORDER BY country LIMIT 20"):
    print(f"  rowid={r[0]:>8}  trad={str(r[3] or '-'):15s}  cnt={r[4]:2s}  src={str(r[2])[:25]:25s}  {r[1][:60]:60s}")

c.close()
