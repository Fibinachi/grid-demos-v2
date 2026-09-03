"""Deep check on the failed imports."""
import sys
sys.path.insert(0, r'E:\grid')
from gw_db import connect

conn = connect(r'E:\grid\churches.db')

# The id column - is it really NULL or just the query?
schema = conn.execute("PRAGMA table_info(churches)").fetchall()
for s in schema:
    if s[1] == 'id':
        print(f"id column: type={s[2]}, nullable={not s[3]}, pk={s[5]}, default={s[4]}")

# count records with id=NULL
null_count = conn.execute("SELECT COUNT(*) FROM churches WHERE id IS NULL").fetchone()[0]
print(f"\nRecords with id IS NULL: {null_count}")

# count all records
total = conn.execute("SELECT COUNT(*) FROM churches").fetchone()[0]
print(f"Total records: {total}")

# count by source
sources = conn.execute("SELECT source, COUNT(*) as cnt FROM churches GROUP BY source ORDER BY cnt DESC").fetchall()
print("\nBy source:")
for s in sources:
    print(f"  {s[0] or 'NULL'}: {s[1]}")

# Check if the ADAMS GEORGE record actually exists and has content
rows = conn.execute("SELECT id, name, faith, city, boston_pid FROM churches WHERE name LIKE '%ADAMS GEORGE%'").fetchall()
print(f"\nADAMS GEORGE records: {len(rows)}")
for r in rows:
    print(f"  row: id={r[0]} name={r[1][:40]} faith={r[2]} city={r[3]} pid={r[4]}")

# Try SELECT rowid
rows = conn.execute("SELECT rowid, id, name FROM churches WHERE name LIKE '%ADAMS GEORGE%'").fetchall()
for r in rows:
    print(f"  rowid={r[0]} id={r[1]} name={r[2][:40]}")

# Check church_contact_values for boston_pid
pid_count = conn.execute("SELECT COUNT(*) FROM church_contact_values WHERE contact_type = 'boston_pid'").fetchone()[0]
print(f"\nchurch_contact_values with boston_pid: {pid_count}")

conn.close()
