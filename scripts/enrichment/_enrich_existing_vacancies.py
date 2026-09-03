import sqlite3, re
conn = sqlite3.connect('churches.db')
c = conn.cursor()

updated = 0
for vac_id, title, details in c.execute("SELECT id, job_title, details FROM church_vacancies WHERE (church_name='' OR church_name IS NULL) AND job_title IS NOT NULL"):
    text = f"{title or ''}\n{details or ''}"
    church = ''
    
    # Pattern 1: "Role – Church Name" in title
    m = re.search(r'(?:–|-)\s*([A-Z][\w\s\'\.&()-]{4,80}?)$', title or '')
    if m:
        church = m.group(1).strip().rstrip('.').rstrip()
    
    # Pattern 2: "at Church Name" 
    if not church:
        m = re.search(r'(?:at|with)\s+([A-Z][\w\s\'\.&()-]{5,80}?)(?:,|\.|\n|\s+in\s|\s+is\s)', text)
        if m: church = m.group(1).strip()
    
    # Pattern 3: "Church Name is seeking" or "Name — "
    if not church:
        m = re.search(r'([A-Z][\w\s\'\.&()-]{5,80}?)\s+(?:is\s+(?:a\s+)?(?:seeking|looking)|—)', text)
        if m: church = m.group(1).strip()
    
    # Only reject obvious non-church junk
    junk = {'Privacy Policy', 'Site Map', 'Pricing', 'Showing', 'Us Privacy'}
    if church and len(church) >= 4 and church not in junk:
        c.execute("UPDATE church_vacancies SET church_name=? WHERE id=?", (church[:200], vac_id))
        updated += 1
        if updated <= 25: print(f"  [{church[:50]}]")

conn.commit()
print(f"Extracted: {updated}")

# City/state
updated2 = 0
for vac_id, details in c.execute("SELECT id, details FROM church_vacancies WHERE (city='' OR city IS NULL) AND details IS NOT NULL"):
    m = re.search(r'\b([A-Z][a-z]+(?:\s[A-Z][a-z]+)?),\s*([A-Z]{2})\b', details or '')
    if m:
        c.execute("UPDATE church_vacancies SET city=?, state=? WHERE id=?", (m.group(1), m.group(2), vac_id))
        updated2 += 1

conn.commit()
print(f"City/state: {updated2}")

empty = c.execute("SELECT COUNT(1) FROM church_vacancies WHERE church_name='' OR church_name IS NULL").fetchone()[0]
names = c.execute("SELECT COUNT(DISTINCT church_name) FROM church_vacancies WHERE church_name!=''").fetchone()[0]
have_city = c.execute("SELECT COUNT(1) FROM church_vacancies WHERE city!=''").fetchone()[0]
print(f"Empty: {empty}, Unique names: {names}, Have city: {have_city}")
conn.close()
