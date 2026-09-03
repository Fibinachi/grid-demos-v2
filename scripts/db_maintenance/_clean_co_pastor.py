"""Check and clean C/O PASTOR records."""
import sqlite3
conn = sqlite3.connect('churches.db', timeout=30)
c = conn.cursor()

c.execute("SELECT id, name, city, state FROM churches WHERE UPPER(name) LIKE '%C/O PASTOR%' OR UPPER(name) LIKE '%C O PASTOR%'")
rows = c.fetchall()
print(f"Total C/O PASTOR records: {len(rows)}\n")
for rid, name, city, state in rows[:30]:
    print(f"  ID={rid} {str(name)[:85]:<85} | {str(city or ''):<15} | {str(state or ''):<4}")

# Clean: "CHURCH NAME C/O PASTOR NAME" → "CHURCH NAME"
c.execute("""UPDATE churches SET name = TRIM(SUBSTR(name, 1, INSTR(UPPER(name), 'C/O PASTOR') - 1))
WHERE UPPER(name) LIKE '%C/O PASTOR%'""")
print(f"\nCleaned 'C/O PASTOR...': {c.rowcount}")

c.execute("""UPDATE churches SET name = TRIM(SUBSTR(name, 1, INSTR(UPPER(name), 'C O PASTOR') - 1))
WHERE UPPER(name) LIKE '%C O PASTOR%'""")
print(f"Cleaned 'C O PASTOR...': {c.rowcount}")

# Also: "CHURCH NAME C/O REV ...", "CHURCH NAME C/O REVEREND ..."
c.execute("""UPDATE churches SET name = TRIM(SUBSTR(name, 1, INSTR(UPPER(name), 'C/O REV') - 1))
WHERE UPPER(name) LIKE '%C/O REV%'""")
print(f"Cleaned 'C/O REV...': {c.rowcount}")

c.execute("""UPDATE churches SET name = TRIM(SUBSTR(name, 1, INSTR(UPPER(name), 'C/O FR ') - 1))
WHERE UPPER(name) LIKE '%C/O FR %'""")
print(f"Cleaned 'C/O FR...': {c.rowcount}")

c.execute("""UPDATE churches SET name = TRIM(SUBSTR(name, 1, INSTR(UPPER(name), 'C/O BISHOP') - 1))
WHERE UPPER(name) LIKE '%C/O BISHOP%'""")
print(f"Cleaned 'C/O BISHOP...': {c.rowcount}")

conn.commit()
conn.close()
