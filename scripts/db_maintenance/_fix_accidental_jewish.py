"""
Fix remaining IRS records that were accidentally converted to Jewish.
These have religion_type='unknown'/'other'/NULL and need name-based classification.
"""
import sqlite3, datetime

DB = 'churches.db'
TS = datetime.datetime.now().isoformat()
conn = sqlite3.connect(DB, timeout=30)
c = conn.cursor()
total_fixed = 0

print("=== Fixing accidental Jewish conversions ===")

# 1. Clearly Christian names → Christian
c.execute("""
    UPDATE churches SET faith='Christian', faith_tradition='Christianity'
    WHERE country='US' AND source LIKE 'irs%' AND faith='Jewish'
      AND (religion_type IN ('unknown','other') OR religion_type IS NULL)
      AND (LOWER(name) LIKE '%church%' OR LOWER(name) LIKE '%ministry%'
           OR LOWER(name) LIKE '%fellowship%' OR LOWER(name) LIKE '%chapel%'
           OR LOWER(name) LIKE '%cathedral%' OR LOWER(name) LIKE '%basilica%'
           OR LOWER(name) LIKE '%gospel%' OR LOWER(name) LIKE '%jesus%'
           OR LOWER(name) LIKE '%christ%' OR LOWER(name) LIKE '%messiah%'
           OR LOWER(name) LIKE '%worship%' OR LOWER(name) LIKE '%pastor%'
           OR LOWER(name) LIKE '%rev%' OR LOWER(name) LIKE '%mission%'
           OR LOWER(name) LIKE '%evangel%' OR LOWER(name) LIKE '%bible%'
           OR LOWER(name) LIKE '%catholic%' OR LOWER(name) LIKE '%baptist%'
           OR LOWER(name) LIKE '%methodist%' OR LOWER(name) LIKE '%lutheran%'
           OR LOWER(name) LIKE '%presbyterian%' OR LOWER(name) LIKE '%episcopal%'
           OR LOWER(name) LIKE '%pentecostal%' OR LOWER(name) LIKE '%adventist%'
           OR LOWER(name) LIKE '%assemblies of god%' OR LOWER(name) LIKE '%assembly of god%'
           OR LOWER(name) LIKE '%christian%' OR LOWER(name) LIKE '%holiness%'
           OR LOWER(name) LIKE '%nazarene%' OR LOWER(name) LIKE '%reformed%')
""")
print(f"  Christian names → Christian: {c.rowcount}")
total_fixed += c.rowcount

# 2. Clearly Muslim names → Islam
c.execute("""
    UPDATE churches SET faith='Islam', faith_tradition='Islam'
    WHERE country='US' AND source LIKE 'irs%' AND faith='Jewish'
      AND (religion_type IN ('unknown','other') OR religion_type IS NULL)
      AND (LOWER(name) LIKE '%islam%' OR LOWER(name) LIKE '%muslim%'
           OR LOWER(name) LIKE '%mosque%' OR LOWER(name) LIKE '%masjid%'
           OR LOWER(name) LIKE '%quran%' OR LOWER(name) LIKE '%allah%'
           OR LOWER(name) LIKE '%mohammed%' OR LOWER(name) LIKE '%muhammad%')
""")
print(f"  Muslim names → Islam: {c.rowcount}")
total_fixed += c.rowcount

# 3. Hindu/Buddhist names → Hindu/Buddhist
c.execute("""
    UPDATE churches SET faith='Hindu', faith_tradition='Hinduism'
    WHERE country='US' AND source LIKE 'irs%' AND faith='Jewish'
      AND (religion_type IN ('unknown','other') OR religion_type IS NULL)
      AND (LOWER(name) LIKE '%hindu%' OR LOWER(name) LIKE '%temple%'
           OR LOWER(name) LIKE '%mandir%' OR LOWER(name) LIKE '%krishna%'
           OR LOWER(name) LIKE '%yoga%' OR LOWER(name) LIKE '%vedic%'
           OR LOWER(name) LIKE '%sikh%' OR LOWER(name) LIKE '%gurdwara%')
      AND LOWER(name) NOT LIKE '%jewish%' AND LOWER(name) NOT LIKE '%synagogue%'
      AND LOWER(name) NOT LIKE '%hebrew%'
""")
print(f"  Hindu names → Hindu: {c.rowcount}")
total_fixed += c.rowcount

c.execute("""
    UPDATE churches SET faith='Buddhist', faith_tradition='Buddhism'
    WHERE country='US' AND source LIKE 'irs%' AND faith='Jewish'
      AND (religion_type IN ('unknown','other') OR religion_type IS NULL)
      AND (LOWER(name) LIKE '%buddhist%' OR LOWER(name) LIKE '%buddha%'
           OR LOWER(name) LIKE '%zen%' OR LOWER(name) LIKE '%dharma%')
""")
print(f"  Buddhist names → Buddhist: {c.rowcount}")
total_fixed += c.rowcount

conn.commit()

# 4. Log
c.execute("""
    INSERT INTO provenance_log (source, script_name, started_at, completed_at,
        churches_updated, churches_inserted, fields_populated, status, notes)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
""", ('manual', '_fix_accidental_jewish.py', TS, TS,
      total_fixed, 0, 'faith,faith_tradition', 'completed',
      f'Fixed {total_fixed} accidentally-converted IRS records using name heuristics'))

conn.commit()

# Summary
print(f"\nTotal fixed: {total_fixed}")
print("\nIRS records — final faith:")
c.execute("SELECT faith, COUNT(*) FROM churches WHERE country='US' AND source LIKE 'irs%' GROUP BY faith ORDER BY COUNT(*) DESC")
for faith, cnt in c.fetchall():
    print(f"  {str(faith):<15} {cnt:>8,}")

conn.close()
print("\nDone!")
