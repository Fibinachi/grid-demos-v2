"""Revert incorrect faith changes made by _fix_irs_jewish_nonprofits.py.

The changes were:
  religion_type=christian + faith=Jewish → faith=Christian (2773)
  religion_type=muslim + faith=Jewish → faith=Islam (40)
  religion_type=hindu + faith=Jewish → faith=Hindu (183)
  religion_type=buddhist + faith=Jewish → faith=Buddhist (237)
  religion_type=sikh + faith=Jewish → faith=Sikh (4)
  religion_type=humanist + faith=Jewish → faith=Hindu (12)
  religion_type=other/unknown + Christian name → Christian (51)
  'Ministries' → Christian (111)
  'Fellowship' → Christian (3)

The religion_type column was meant for subsidiary classification within
Jewish parent orgs, NOT the actual faith. Revert faith back to Jewish.
"""
import sqlite3, datetime

DB = 'churches.db'
TS = datetime.datetime.now().isoformat()
conn = sqlite3.connect(DB, timeout=30)
c = conn.cursor()

total_reverted = 0

# Revert ALL faith changes where source is IRS and we changed faith from Jewish
# Strategy: find IRS records where religion_type is set but faith was changed
# away from Jewish, and revert faith back to Jewish

c.execute("""
    UPDATE churches SET faith='Jewish', faith_tradition='Judaism'
    WHERE country='US' AND source LIKE 'irs%'
      AND faith != 'Jewish'
      AND religion_type IN ('jewish', 'synagogue', 'jewish_org', 'christian', 
                             'muslim', 'hindu', 'buddhist', 'sikh', 'humanist',
                             'other', 'unknown')
""")
reverted = c.rowcount
total_reverted += reverted
print(f"Reverted faith→Jewish (by religion_type): {reverted}")

# Also revert any remaining IRS records that were changed via ministries/fellowship
c.execute("""
    UPDATE churches SET faith='Jewish', faith_tradition='Judaism'
    WHERE country='US' AND source LIKE 'irs%'
      AND faith != 'Jewish'
""")
reverted2 = c.rowcount
total_reverted += reverted2
print(f"Reverted remaining faith→Jewish: {reverted2}")

conn.commit()

# Log
c.execute("""
    INSERT INTO provenance_log (source, script_name, started_at, completed_at,
        churches_updated, churches_inserted, fields_populated, status, notes)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
""", ('manual', '_revert_irs_faith.py', TS, TS,
      total_reverted, 0, 'faith,faith_tradition', 'completed',
      f'Reverted {total_reverted} IRS records faith back to Jewish (religion_type is for subsidiary classification, not faith)'))

conn.commit()

# Summary
print(f"\nTotal reverted: {total_reverted}")
print("\nIRS records — faith breakdown:")
c.execute("SELECT faith, COUNT(*) FROM churches WHERE country='US' AND source LIKE 'irs%' GROUP BY faith ORDER BY COUNT(*) DESC")
for faith, cnt in c.fetchall():
    print(f"  {faith:<15} {cnt:>8,}")

print("\nIRS Jewish records — religion_type breakdown:")
c.execute("SELECT religion_type, COUNT(*) FROM churches WHERE country='US' AND source LIKE 'irs%' AND faith='Jewish' GROUP BY religion_type ORDER BY COUNT(*) DESC")
for rt, cnt in c.fetchall():
    print(f"  {str(rt):<20} {cnt:>6,}")

conn.close()
print("\nDone!")
