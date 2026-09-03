"""Audit Jewish entries in Indonesia."""
import sqlite3
conn = sqlite3.connect(r"E:\grid\churches.db")
c = conn.cursor()

# All Jewish entries in Indonesia
print("=== INDONESIA Judaism entries ===")
c.execute("""
    SELECT id, name, name_transliterated, tradition, city, state, landmark_type, latitude, longitude
    FROM churches
    WHERE country='ID' AND faith='Judaism'
    ORDER BY name
""")
rows = c.fetchall()
print(f"Total: {len(rows)}\n")
for r in rows:
    print(f"  {r[0]:>8d} | {str(r[1] or '')[:50]:50s} | {str(r[2] or '')[:30]:30s} | {str(r[3] or ''):20s} | {str(r[4] or ''):20s} | {str(r[5] or ''):15s} | {str(r[6] or ''):15s} | {r[7] or '?'}, {r[8] or '?'}")

# All faiths in ID
print("\n\nAll faiths in ID:")
c.execute("SELECT faith, COUNT(*) FROM churches WHERE country='ID' GROUP BY faith ORDER BY COUNT(*) DESC")
for r in c.fetchall():
    print(f"  {r[0]:15s}: {r[1]:,}")

# Check for "synagogue" or "jewish" named entries not under Judaism
print("\n\n=== Possible Jewish sites NOT under Judaism ===")
c.execute("""
    SELECT id, name, faith, tradition, city, state
    FROM churches
    WHERE country='ID' 
    AND (LOWER(name) LIKE '%synagogue%' OR LOWER(name) LIKE '%jewish%' 
         OR LOWER(name) LIKE '%yahudi%' OR LOWER(name) LIKE '%sinagoga%'
         OR LOWER(name) LIKE '%chabad%' OR LOWER(name) LIKE '%yuda%')
""")
for r in c.fetchall():
    print(f"  {r[0]:>8d} | {str(r[1] or '')[:50]:50s} | {r[2] or ''} | {r[3] or ''} | {r[4] or ''} | {r[5] or ''}")

# Check Jakarta specifically for synagogues
print("\n\n=== Jakarta - anything synagogue/chabad related ===")
c.execute("""
    SELECT id, name, faith, tradition, landmark_type, city, latitude, longitude
    FROM churches
    WHERE country='ID' AND LOWER(city) LIKE '%jakarta%'
    AND (LOWER(name) LIKE '%synagogue%' OR LOWER(name) LIKE '%jewish%' 
         OR LOWER(name) LIKE '%yahudi%' OR LOWER(name) LIKE '%sinagoga%'
         OR LOWER(name) LIKE '%chabad%' OR LOWER(name) LIKE '%ibrani%')
""")
for r in c.fetchall():
    print(f"  {r[0]:>8d} | {str(r[1] or '')[:50]:50s} | {r[2] or ''} | {r[3] or ''} | {r[4] or ''} | {r[5] or ''} | {r[6]},{r[7]}")

# Look for suspicious patterns in ID Judaism
print("\n\n=== Suspicious patterns in ID Judaism ===")
c.execute("""
    SELECT id, name, faith, tradition
    FROM churches
    WHERE country='ID' AND faith='Judaism'
    AND (LOWER(name) LIKE '%church%' OR LOWER(name) LIKE '%masjid%' OR LOWER(name) LIKE '%mosque%'
         OR LOWER(name) LIKE '%pura%' OR LOWER(name) LIKE '%vihara%'
         OR LOWER(name) LIKE '%pendeta%' OR LOWER(name) LIKE '%gereja%'
         OR LOWER(name) LIKE '%kristen%' OR LOWER(name) LIKE '%mesias%'
         OR LOWER(name) LIKE '%almasih%')
""")
for r in c.fetchall():
    print(f"  {r[0]:>8d} | {str(r[1] or '')[:50]:50s} | {r[2] or ''} | {r[3] or ''}")

# The famous Jakarta synagogue: Sha'ar Hashamayim / Beith Shalom Synagogue in Tangerang
# Let me search for it
print("\n\n=== Looking for Jakarta synagogue (Sha'ar Hashamayim / Beith Shalom) ===")
c.execute("""
    SELECT id, name, faith, tradition, city, state, country, latitude, longitude
    FROM churches
    WHERE LOWER(name) LIKE '%hashamayim%' OR LOWER(name) LIKE '%beith shalom%'
    OR LOWER(name) LIKE '%bet shalom%' OR LOWER(name) LIKE '%shaar%'
    OR LOWER(name) LIKE '%shalom%jakarta%'
""")
for r in c.fetchall():
    print(f"  {r[0]:>8d} | {str(r[1] or '')[:50]:50s} | {r[2] or ''} | {r[3] or ''} | {r[4] or ''} | {r[5] or ''} | {r[6] or ''} | {r[7]},{r[8]}")

# Also search for "Sinagoge" (Indonesian spelling)
print("\n\n=== Sinagoge searches ===")
c.execute("""
    SELECT id, name, faith, tradition, city, country
    FROM churches
    WHERE LOWER(name) LIKE '%sinagoge%' OR LOWER(name) LIKE '%sinagoga%'
""")
for r in c.fetchall():
    print(f"  {r[0]:>8d} | {str(r[1] or '')[:50]:50s} | {r[2] or ''} | {r[3] or ''} | {r[4] or ''} | {r[5] or ''}")

conn.close()
