"""Fix the remaining 110 NULL-faith monasteries."""
import sqlite3
conn = sqlite3.connect('churches.db', timeout=30)
c = conn.cursor()
fixes = 0

# Christian signals
c.execute("""UPDATE churches SET faith='Christian', faith_tradition='Christianity'
WHERE (faith IS NULL OR faith='') AND LOWER(name) LIKE '%monastery%'
AND (LOWER(name) LIKE '%saint%' OR LOWER(name) LIKE '%st.%' OR LOWER(name) LIKE '%st %'
  OR LOWER(name) LIKE '%holy%' OR LOWER(name) LIKE '%blessed%'
  OR LOWER(name) LIKE '%immaculate%' OR LOWER(name) LIKE '%annunciation%'
  OR LOWER(name) LIKE '%ascension%' OR LOWER(name) LIKE '%transfiguration%'
  OR LOWER(name) LIKE '%archangel%' OR LOWER(name) LIKE '%carmel%'
  OR LOWER(name) LIKE '%chartreuse%' OR LOWER(name) LIKE '%salvatorian%'
  OR LOWER(name) LIKE '%marianhill%' OR LOWER(name) LIKE '%sava%'
  OR LOWER(name) LIKE '%gregory%sinai%' OR LOWER(name) LIKE '%paisius%'
  OR LOWER(name) LIKE '%isaac%nineveh%' OR LOWER(name) LIKE '%sacred monastery%'
  OR LOWER(name) LIKE '%deb%' OR LOWER(name) LIKE '%monk monastery%'
  OR LOWER(name) LIKE '%new creation%')""")
print(f"Christian signals: {c.rowcount}"); fixes+=c.rowcount

# Tibetan → Buddhist
c.execute("""UPDATE churches SET faith='Buddhist', faith_tradition='Buddhism'
WHERE (faith IS NULL OR faith='') AND LOWER(name) LIKE '%monastery%' AND LOWER(name) LIKE '%tibetan%'""")
print(f"Tibetan Buddhist: {c.rowcount}"); fixes+=c.rowcount

# Jain → Hindu
c.execute("""UPDATE churches SET faith='Hindu', faith_tradition='Hinduism'
WHERE (faith IS NULL OR faith='') AND LOWER(name) LIKE '%monastery%' AND LOWER(name) LIKE '%jain%'""")
print(f"Jain → Hindu: {c.rowcount}"); fixes+=c.rowcount

# Remaining monasteries → Christian (conservative default)
c.execute("""UPDATE churches SET faith='Christian', faith_tradition='Christianity'
WHERE (faith IS NULL OR faith='') AND LOWER(name) LIKE '%monastery%'""")
print(f"Remaining → Christian: {c.rowcount}"); fixes+=c.rowcount

conn.commit()
c.execute("SELECT COUNT(*) FROM churches WHERE (faith IS NULL OR faith='') AND LOWER(name) LIKE '%monastery%'")
print(f"Still NULL: {c.fetchone()[0]}")
print(f"Total fixes: {fixes}")
conn.close()
