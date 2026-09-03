"""Assess LDS data for structural linking plan."""
import sqlite3
conn = sqlite3.connect('churches.db')
c = conn.cursor()

# Temple distribution by state
print('=== TEMPLES BY STATE ===')
c.execute("SELECT COALESCE(state,'(none)'), COUNT(*) FROM lds_hierarchy WHERE lds_type='temple' GROUP BY state ORDER BY COUNT(*) DESC")
for row in c.fetchall():
    print(f"  {row[0]:>25}: {row[1]}")

# Stake houses by state
print('\n=== STAKE HOUSES BY STATE ===')
c.execute("SELECT COALESCE(state,'(none)'), COUNT(*) FROM lds_hierarchy WHERE lds_type='stake_house' GROUP BY state ORDER BY COUNT(*) DESC")
for row in c.fetchall():
    print(f"  {row[0]:>25}: {row[1]}")

# Meetinghouses by state (top 20)
print('\n=== MEETINGHOUSES BY STATE (top 20) ===')
c.execute("SELECT COALESCE(state,'(none)'), COUNT(*) FROM lds_hierarchy WHERE lds_type='meetinghouse' GROUP BY state ORDER BY COUNT(*) DESC LIMIT 20")
for row in c.fetchall():
    print(f"  {row[0]:>25}: {row[1]}")

# Meetinghouses sharing city with a stake house
c.execute("SELECT COUNT(*) FROM lds_hierarchy mh WHERE lds_type='meetinghouse' AND city IS NOT NULL AND city != '' AND EXISTS (SELECT 1 FROM lds_hierarchy sh WHERE sh.lds_type='stake_house' AND sh.city = mh.city AND sh.state = mh.state)")
print(f"\nMeetinghouses sharing city with a stake house: {c.fetchone()[0]:,}")

c.execute("SELECT COUNT(*) FROM lds_hierarchy mh WHERE lds_type='meetinghouse' AND city IS NOT NULL AND city != ''")
print(f"Meetinghouses with city populated: {c.fetchone()[0]:,}")

c.execute("SELECT COUNT(*) FROM lds_hierarchy mh WHERE lds_type='meetinghouse' AND (city IS NULL OR city = '')")
print(f"Meetinghouses WITHOUT city: {c.fetchone()[0]:,}")

# Meetinghouses with GPS
c.execute("SELECT COUNT(*) FROM lds_hierarchy mh WHERE lds_type='meetinghouse' AND lat IS NOT NULL")
print(f"Meetinghouses with GPS: {c.fetchone()[0]:,}")

# Stake houses with GPS
c.execute("SELECT COUNT(*) FROM lds_hierarchy mh WHERE lds_type='stake_house' AND lat IS NOT NULL")
print(f"Stake houses with GPS: {c.fetchone()[0]:,}")

# Temples with GPS
c.execute("SELECT COUNT(*) FROM lds_hierarchy mh WHERE lds_type='temple' AND lat IS NOT NULL")
print(f"Temples with GPS: {c.fetchone()[0]:,}")

# Special types
print('\n=== SPECIAL TYPES ===')
c.execute("SELECT lds_type, COUNT(*) FROM lds_hierarchy WHERE lds_type NOT IN ('temple','stake_house','meetinghouse','hq') GROUP BY lds_type ORDER BY COUNT(*) DESC")
for row in c.fetchall():
    print(f"  {row[0]:>25}: {row[1]}")

# Sample temple names
print('\n=== SAMPLE TEMPLE NAMES (10) ===')
c.execute("SELECT name, city, state, country FROM lds_hierarchy WHERE lds_type='temple' LIMIT 10")
for row in c.fetchall():
    print(f"  {row[0][:60]:>60} | {row[1] or '-'}, {row[2] or '-'}, {row[3] or '-'}")

# Sample stake house names (15)
print('\n=== SAMPLE STAKE HOUSE NAMES (15) ===')
c.execute("SELECT name, city, state, country FROM lds_hierarchy WHERE lds_type='stake_house' LIMIT 15")
for row in c.fetchall():
    print(f"  {row[0][:60]:>60} | {row[1] or '-'}, {row[2] or '-'}, {row[3] or '-'}")

# Check for state-based matching coverage
print('\n=== STATE MATCH COVERAGE ===')
c.execute("""
    SELECT 
        COUNT(DISTINCT mh.state) as mh_states,
        COUNT(DISTINCT sh.state) as sh_states,
        COUNT(DISTINCT tm.state) as tm_states
    FROM (SELECT DISTINCT state FROM lds_hierarchy WHERE lds_type='meetinghouse' AND state IS NOT NULL AND state != '') mh,
         (SELECT DISTINCT state FROM lds_hierarchy WHERE lds_type='stake_house' AND state IS NOT NULL AND state != '') sh,
         (SELECT DISTINCT state FROM lds_hierarchy WHERE lds_type='temple' AND state IS NOT NULL AND state != '') tm
""")
row = c.fetchone()
print(f"  Meetinghouse states: {row[0]}, Stake house states: {row[1]}, Temple states: {row[2]}")

# States that have meetinghouses but no stake houses
c.execute("""
    SELECT DISTINCT mh.state FROM lds_hierarchy mh 
    WHERE mh.lds_type='meetinghouse' AND mh.state IS NOT NULL AND mh.state != ''
    AND mh.state NOT IN (SELECT DISTINCT state FROM lds_hierarchy WHERE lds_type='stake_house' AND state IS NOT NULL AND state != '')
    ORDER BY mh.state
""")
print(f"States with MH but no stake house: {[r[0] for r in c.fetchall()]}")

# HQ record
print('\n=== HQ ===')
c.execute("SELECT id, name, city, state, country FROM lds_hierarchy WHERE lds_type='hq'")
for row in c.fetchall():
    print(f"  ID={row[0]}: {row[1]}, {row[2]}, {row[3]}, {row[4]}")

conn.close()
