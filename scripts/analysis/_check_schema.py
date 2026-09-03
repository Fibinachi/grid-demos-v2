"""Check classification column coverage in churches table."""
import sqlite3

db = sqlite3.connect('E:\\grid\\churches.db')
c = db.cursor()
c.execute('PRAGMA table_info(churches)')
cols = c.fetchall()

print('=== ALL CLASSIFICATION COLUMNS ===')
total = 3398616
for col in cols:
    name = col[1]
    dtype = col[2]
    # Focus on classification, identity, denomination columns
    keywords = ['faith', 'tradition', 'denom', 'religion', 'landmark', 
                'liturgical', 'muslim', 'jewish', 'sikh', 'buddhist', 'hindu',
                'church_', 'service_', 'staff_', 'parent_', 'taxonomy',
                'classification', 'confidence', 'ntee', 'family',
                'diocese', 'archdioc', 'deanery', 'synod', 'conference',
                'district', 'presbytery', 'association', 'province',
                'rite', 'canonical']
    if any(k in name.lower() for k in keywords):
        c2 = db.cursor()
        try:
            c2.execute(f'SELECT COUNT(*) FROM churches WHERE "{name}" IS NOT NULL AND "{name}" != ""')
            cnt = c2.fetchone()[0]
            pct = cnt / total * 100
            print(f'  {name:40s} {dtype:12s}  {cnt:>10,}  ({pct:5.1f}%)')
        except Exception as e:
            print(f'  {name:40s} {dtype:12s}  ERROR: {e}')

db.close()
