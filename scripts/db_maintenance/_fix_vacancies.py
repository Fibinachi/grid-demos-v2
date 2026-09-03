import sqlite3, re
conn = sqlite3.connect('churches.db')
c = conn.cursor()

updated = 0
for vac_id, title in c.execute("SELECT id, job_title FROM church_vacancies WHERE (church_name='' OR church_name IS NULL) AND (job_title LIKE '%-%' OR job_title LIKE '%' || char(8211) || '%')"):
    church = ''
    m = re.search(r'(?:–|-)\s*([A-Z][\w\s\'\.&(),-]{4,80}?)$', title or '')
    if m: church = m.group(1).strip()
    if not church:
        m = re.search(r'^([A-Z][\w\s\'\.&(),-]{4,80}?)\s*(?:–|-)', title or '')
        if m: church = m.group(1).strip()
    role_words = {'Pastor','Minister','Director','Leader','Coordinator','Teacher'}
    if church:
        words = set(church.split())
        # Only reject if every word is a role word (e.g., "Worship Pastor")
        if words.issubset(role_words):
            church = ''
    if church and len(church) >= 4:
        c.execute("UPDATE church_vacancies SET church_name=? WHERE id=?", (church[:200], vac_id))
        updated += 1
        if updated <= 30: print(f"  [{church[:50]}]")

conn.commit()
print(f"Dash titles: {updated}")

# Don't limit by LIKE - scan all with details
updated2 = 0
for vac_id, details in c.execute("SELECT id, details FROM church_vacancies WHERE (city='' OR city IS NULL) AND details IS NOT NULL AND details != ''"):
    m = re.search(r'\b([A-Z][a-z]+(?:\s[A-Z][a-z]+)?),\s*([A-Z]{2})\b', details or '')
    if m:
        c.execute("UPDATE church_vacancies SET city=?, state=? WHERE id=?", (m.group(1), m.group(2), vac_id))
        updated2 += 1
conn.commit()
print(f"City/state: {updated2}")

empty = c.execute("SELECT COUNT(1) FROM church_vacancies WHERE church_name='' OR church_name IS NULL").fetchone()[0]
names = c.execute("SELECT COUNT(DISTINCT church_name) FROM church_vacancies WHERE church_name!=''").fetchone()[0]
print(f"Empty: {empty}, Unique names: {names}")
print("\nSample:")
for r in c.execute("SELECT DISTINCT church_name FROM church_vacancies WHERE church_name!='' LIMIT 25"):
    print(f"  {r[0][:60]}")
conn.close()
