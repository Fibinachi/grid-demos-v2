"""Fix two CI entries misclassified as Jewish.

1. rowid=1805214: Église Cafm, Riviera Palmeraie — "Église" = Church in French, clearly Christian
2. rowid=2844002: JERUSALEM (COUVANT) — "Couvent" = Convent in French, clearly Christian
"""
import sqlite3
import datetime

conn = sqlite3.connect('E:/grid/churches.db')
c = conn.cursor()

fixes = [
    {
        'rowid': 1805214,
        'name': "Église Cafm, Riviera Palmeraie",
        'reason': "Name contains 'Église' (Church in French) — Christian church misclassified as Jewish"
    },
    {
        'rowid': 2844002,
        'name': "JERUSALEM (COUVANT)",
        'reason': "Name contains 'Couvent' (Convent in French) — Catholic convent misclassified as Jewish"
    }
]

for fix in fixes:
    rid = fix['rowid']
    # Check current state
    c.execute("SELECT faith, faith_tradition FROM churches WHERE rowid=?", (rid,))
    row = c.fetchone()
    if not row:
        print(f'rowid={rid}: NOT FOUND')
        continue
    old_faith, old_ft = row
    
    # Update faith
    c.execute("UPDATE churches SET faith='Christian', faith_tradition='Christian' WHERE rowid=?", (rid,))
    
    # Log in enrichment_change_log (per-field per-church)
    now = datetime.datetime.now().isoformat()
    c.execute("INSERT INTO enrichment_change_log (church_id, field_name, old_value, new_value, change_source, changed_at) VALUES (?, ?, ?, ?, ?, ?)",
              (rid, 'faith', old_faith, 'Christian', '_fix_ci_jewish.py', now))
    c.execute("INSERT INTO enrichment_change_log (church_id, field_name, old_value, new_value, change_source, changed_at) VALUES (?, ?, ?, ?, ?, ?)",
              (rid, 'faith_tradition', old_ft, 'Christian', '_fix_ci_jewish.py', now))
    
    print(f'rowid={rid}: {fix["name"][:50]:50s} | {old_faith}→Christian | {old_ft}→Christian | Logged')

# Also log run-level entry in provenance_log
c.execute("INSERT INTO provenance_log (source, script_name, started_at, completed_at, churches_updated, fields_populated, status, notes) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
          ('manual', '_fix_ci_jewish.py', now, datetime.datetime.now().isoformat(),
           2, 'faith, faith_tradition', 'completed',
           'Fixed 2 CI entries misclassified as Jewish'))

conn.commit()
conn.close()

print()
print('Done! 2 CI entries fixed.')
