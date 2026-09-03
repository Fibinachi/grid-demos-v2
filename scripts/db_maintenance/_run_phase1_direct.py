"""Run Phase 1 directly without gw_db, using raw sqlite3 with long timeout."""
import sqlite3
import os

db_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'churches.db')
conn = sqlite3.connect(db_path, timeout=120)
conn.execute("PRAGMA busy_timeout=120000")
conn.execute("PRAGMA journal_mode=WAL")
conn.execute("PRAGMA synchronous=NORMAL")
cur = conn.cursor()

phases = [
    ("Name ends with School/Academy/Seminary", """
        AND (name LIKE '% School' OR name LIKE '% Academy' OR name LIKE '% Seminary'
             OR name LIKE '% Yeshiva' OR name LIKE '% Madrasah' OR name LIKE '% Preschool'
             OR name LIKE '% Kindergarten' OR name LIKE '% Lyceum')
        AND name NOT LIKE '%Church%' AND name NOT LIKE '%Church %'
        AND name NOT LIKE '%Chapel%' AND name NOT LIKE '%Parish%'
        AND name NOT LIKE '%Congregation%' AND name NOT LIKE '%Ministry%'
        AND name NOT LIKE '%Fellowship%' AND name NOT LIKE '%Tabernacle%'
    """),
    ("Catholic School / Catholic Academy", """
        AND (name LIKE '%Catholic School%' OR name LIKE '%Catholic Academy%')
    """),
    ("LA Catholic Schools source", """
        AND source LIKE '%la_catholic_schools%'
    """),
    ("Seminary/Yeshiva/Madrasah", """
        AND (name LIKE '%Seminary%' OR name LIKE '%Yeshiva%'
             OR name LIKE '%Madrasah%' OR name LIKE '%Madrasa%')
        AND name NOT LIKE '%Seminary Baptist%'
        AND name NOT LIKE '%Seminary Church%'
        AND name NOT LIKE '%Seminary Chapel%'
        AND name NOT LIKE '%Seminary Parish%'
    """),
    ("'School' in name, no church keywords", """
        AND name LIKE '%School%'
        AND name NOT LIKE '%Church%' AND name NOT LIKE '%Church %'
        AND name NOT LIKE '%Chapel%' AND name NOT LIKE '%Parish%'
        AND name NOT LIKE '%Congregation%' AND name NOT LIKE '%Ministry%'
        AND name NOT LIKE '%Fellowship%'
        AND name NOT LIKE '%Sunday School%' AND name NOT LIKE '%Bible School%'
        AND name NOT LIKE '%Sabbath School%' AND name NOT LIKE '%Church School%'
    """),
    ("PSS merge targets (exact name)", """
        AND id IN (SELECT c.id FROM pss_schools ps
                   JOIN churches c ON ps.merge_target_id = c.id
                   WHERE UPPER(ps.pinst) = UPPER(c.name))
    """),
]

total_all = 0
for phase_name, extra_where in phases:
    print(f"PHASE: {phase_name}")
    where = "WHERE (landmark_type IS NULL OR landmark_type = '' OR landmark_type = 'church')" + extra_where
    cur.execute(f"SELECT COUNT(*) FROM churches {where}")
    count = cur.fetchone()[0]
    print(f"  Candidates: {count}")
    if count == 0:
        continue
    try:
        cur.execute(f"UPDATE churches SET landmark_type = 'school' {where}")
        updated = cur.rowcount
        conn.commit()
        total_all += updated
        print(f"  Fixed: {updated}")
    except Exception as e:
        print(f"  ERROR: {e}")
        conn.rollback()
        break

cur.execute("SELECT COUNT(*) FROM churches WHERE landmark_type = 'school'")
total = cur.fetchone()[0]
print(f"\nTOTAL fixed: {total_all}")
print(f"TOTAL schools now: {total}")
conn.close()
